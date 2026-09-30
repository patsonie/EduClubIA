"""Tests transverses : permissions par objet, périmètres, règles métier critiques."""
from datetime import date, time

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from activites.models import Activite
from annees_scolaires.models import AnneeScolaire
from clubs.models import Club
from inscriptions.models import Inscription
from messagerie.models import SalonDiscussion
from participations.models import Participation
from recommandations.services import calculer_recommandations_hybrides
from utilisateurs.models import RelationParentEleve, Utilisateur


def creer_utilisateur(email, role, **extra):
    return Utilisateur.objects.create_user(
        email=email, password="motdepasse123", nom=email.split('@')[0], prenom="Test", role=role, **extra
    )


class BaseDonnees(APITestCase):
    def setUp(self):
        self.admin = creer_utilisateur("a@t.cm", Utilisateur.Role.ADMINISTRATEUR)
        self.proviseur = creer_utilisateur("p@t.cm", Utilisateur.Role.PROVISEUR, etablissement="Lycée")
        self.enc1 = creer_utilisateur("enc1@t.cm", Utilisateur.Role.ENCADREUR)
        self.enc2 = creer_utilisateur("enc2@t.cm", Utilisateur.Role.ENCADREUR)
        self.eleve1 = creer_utilisateur("el1@t.cm", Utilisateur.Role.ELEVE, matricule="M1")
        self.eleve2 = creer_utilisateur("el2@t.cm", Utilisateur.Role.ELEVE, matricule="M2")
        self.parent = creer_utilisateur("par@t.cm", Utilisateur.Role.PARENT)
        RelationParentEleve.objects.create(parent=self.parent, enfant=self.eleve1)

        self.annee = AnneeScolaire.objects.create(
            libelle="2025-2026", date_debut="2025-09-01", date_fin="2026-07-31", est_active=True,
        )
        self.club1 = Club.objects.create(
            nom="Club 1", description="robotique informatique", objectifs="coder",
            categorie=Club.Categorie.TECHNOLOGIQUE, responsable=self.enc1,
            nombre_max_membres=2, statut=Club.Statut.ACTIF,
        )
        self.club2 = Club.objects.create(
            nom="Club 2", description="théâtre", objectifs="jouer",
            categorie=Club.Categorie.CULTUREL, responsable=self.enc2,
            nombre_max_membres=5, statut=Club.Statut.ACTIF,
        )
        self.ins1 = Inscription.objects.create(
            eleve=self.eleve1, club=self.club1, annee_scolaire=self.annee,
            statut=Inscription.Statut.VALIDEE,
        )
        self.act1 = Activite.objects.create(
            club=self.club1, titre="A1", description="d", date=date(2026, 1, 10),
            heure=time(10, 0), lieu="Salle",
        )

    def auth(self, user):
        self.client.force_authenticate(user)


class ParticipationsSecuriteTest(BaseDonnees):
    def test_rapport_individuel_refuse_a_un_autre_eleve(self):
        Participation.objects.create(inscription=self.ins1, activite=self.act1)
        self.auth(self.eleve2)
        r = self.client.get('/api/participations/rapport_individuel/', {'eleve_id': self.eleve1.id})
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_rapport_individuel_autorise_pour_le_parent_lie(self):
        Participation.objects.create(inscription=self.ins1, activite=self.act1)
        self.auth(self.parent)
        r = self.client.get('/api/participations/rapport_individuel/', {'eleve_id': self.eleve1.id})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['total_activites'], 1)

    def test_enregistrer_lot_valide_les_entrees(self):
        self.auth(self.enc1)
        r = self.client.post('/api/participations/enregistrer_lot/', {
            'activite': self.act1.id, 'presences': [{'inscription': self.ins1.id, 'statut': 'nimporte'}],
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_enregistrer_lot_ok_et_notifie_parent(self):
        self.auth(self.enc1)
        r = self.client.post('/api/participations/enregistrer_lot/', {
            'activite': self.act1.id, 'presences': [{'inscription': self.ins1.id, 'statut': 'absent'}],
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(self.parent.notifications.filter(titre="Absence enregistrée").exists())

    def test_enregistrer_lot_refuse_a_un_encadreur_dun_autre_club(self):
        self.auth(self.enc2)
        r = self.client.post('/api/participations/enregistrer_lot/', {
            'activite': self.act1.id, 'presences': [{'inscription': self.ins1.id, 'statut': 'present'}],
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class InscriptionsRegles(BaseDonnees):
    def test_encadreur_autre_club_ne_peut_pas_valider(self):
        ins = Inscription.objects.create(eleve=self.eleve2, club=self.club1, annee_scolaire=self.annee)
        self.auth(self.enc2)
        r = self.client.post(f'/api/inscriptions/{ins.id}/valider/')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_transition_invalide_refusee(self):
        self.auth(self.enc1)
        r = self.client.post(f'/api/inscriptions/{self.ins1.id}/valider/')  # déjà validée
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validation_refusee_si_club_complet(self):
        Inscription.objects.create(
            eleve=self.eleve2, club=self.club1, annee_scolaire=self.annee, statut=Inscription.Statut.VALIDEE,
        )
        eleve3 = creer_utilisateur("el3@t.cm", Utilisateur.Role.ELEVE, matricule="M3")
        ins = Inscription.objects.create(eleve=eleve3, club=self.club1, annee_scolaire=self.annee)
        self.auth(self.enc1)
        r = self.client.post(f'/api/inscriptions/{ins.id}/valider/')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reinscription_apres_desinscription(self):
        self.auth(self.eleve2)
        r = self.client.post('/api/inscriptions/', {'club': self.club2.id, 'annee_scolaire': self.annee.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        ins_id = r.data['id']
        self.assertEqual(self.client.post(f'/api/inscriptions/{ins_id}/se_desinscrire/').status_code, 200)
        r = self.client.post('/api/inscriptions/', {'club': self.club2.id, 'annee_scolaire': self.annee.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Inscription.objects.filter(eleve=self.eleve2, club=self.club2).count(), 1)

    def test_inscription_refusee_pour_club_inactif(self):
        self.club2.statut = Club.Statut.INACTIF
        self.club2.save()
        self.auth(self.eleve2)
        r = self.client.post('/api/inscriptions/', {'club': self.club2.id, 'annee_scolaire': self.annee.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class ClubsEtActivitesPerimetre(BaseDonnees):
    def test_membres_masques_aux_non_membres(self):
        self.auth(self.eleve2)
        self.assertEqual(self.client.get(f'/api/clubs/{self.club1.id}/membres/').status_code, 403)
        self.auth(self.parent)
        self.assertEqual(self.client.get(f'/api/clubs/{self.club1.id}/membres/').status_code, 403)
        self.auth(self.eleve1)
        self.assertEqual(self.client.get(f'/api/clubs/{self.club1.id}/membres/').status_code, 200)

    def test_encadreur_ne_modifie_pas_activite_dun_autre_club(self):
        self.auth(self.enc2)
        r = self.client.patch(f'/api/activites/{self.act1.id}/', {'titre': 'Piraté'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_encadreur_ne_valide_pas_une_activite(self):
        self.auth(self.enc1)
        r = self.client.post(f'/api/activites/{self.act1.id}/valider/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_budget_masque_pour_l_eleve(self):
        self.auth(self.eleve1)
        r = self.client.get(f'/api/activites/{self.act1.id}/')
        self.assertNotIn('budget', r.data)


class ComptesSuspendus(BaseDonnees):
    def test_jeton_dun_compte_suspendu_est_refuse(self):
        client = APIClient()
        access = str(RefreshToken.for_user(self.eleve1).access_token)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        self.assertEqual(client.get('/api/auth/profil/').status_code, 200)

        self.auth(self.admin)
        self.assertEqual(self.client.post(f'/api/auth/utilisateurs/{self.eleve1.id}/suspendre/').status_code, 200)
        self.assertEqual(client.get('/api/auth/profil/').status_code, 401)


class MessagerieAcces(BaseDonnees):
    def test_acces_aux_salons(self):
        salon1 = SalonDiscussion.objects.get(club=self.club1)
        self.auth(self.enc2)
        self.assertEqual(self.client.get(f'/api/messagerie/salons/{salon1.id}/messages/').status_code, 404)
        self.auth(self.enc1)
        self.assertEqual(self.client.get(f'/api/messagerie/salons/{salon1.id}/messages/').status_code, 200)
        self.auth(self.eleve2)
        self.assertEqual(self.client.get(f'/api/messagerie/salons/{salon1.id}/messages/').status_code, 404)
        self.auth(self.parent)
        self.assertEqual(self.client.get('/api/messagerie/salons/').data, [])

    def test_salon_prive_reserve_aux_participants(self):
        prive = SalonDiscussion.objects.create(type_salon=SalonDiscussion.TypeSalon.PRIVE)
        prive.participants.add(self.parent, self.enc1)
        self.auth(self.admin)
        ids = [s['id'] for s in self.client.get('/api/messagerie/salons/').data]
        self.assertNotIn(prive.id, ids)
        self.auth(self.parent)
        self.assertEqual(self.client.get(f'/api/messagerie/salons/{prive.id}/messages/').status_code, 200)


class AnneesScolaires(BaseDonnees):
    def test_est_active_non_modifiable_par_patch(self):
        autre = AnneeScolaire.objects.create(
            libelle="2026-2027", date_debut="2026-09-01", date_fin="2027-07-31", est_active=False,
        )
        self.auth(self.admin)
        self.client.patch(f'/api/annees-scolaires/{autre.id}/', {'est_active': True}, format='json')
        autre.refresh_from_db()
        self.assertFalse(autre.est_active)
        self.assertEqual(self.client.post(f'/api/annees-scolaires/{autre.id}/activer/').status_code, 200)
        self.annee.refresh_from_db()
        self.assertFalse(self.annee.est_active)

    def test_suppression_annee_avec_inscriptions_donne_409(self):
        self.auth(self.admin)
        r = self.client.delete(f'/api/annees-scolaires/{self.annee.id}/')
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)


class RecommandationsRegles(BaseDonnees):
    def test_pas_de_club_inactif_recommande(self):
        self.club2.statut = Club.Statut.ARCHIVE
        self.club2.save()
        self.eleve2.centres_interet = "théâtre, informatique"
        self.eleve2.save()
        ids = [r['club'].id for r in calculer_recommandations_hybrides(self.eleve2)]
        self.assertNotIn(self.club2.id, ids)
        self.assertIn(self.club1.id, ids)

    def test_cold_start_retourne_des_clubs_populaires(self):
        resultats = calculer_recommandations_hybrides(self.eleve2)
        self.assertTrue(resultats)


class ValidateursFichiers(TestCase):
    def test_contenu_ne_correspondant_pas_a_l_extension_est_refuse(self):
        from django.core.exceptions import ValidationError
        from utilisateurs.validators import valider_extension_justificatif
        faux = SimpleUploadedFile("a.pdf", b"MZ\x90\x00 pas un pdf")
        with self.assertRaises(ValidationError):
            valider_extension_justificatif(faux)
        vrai = SimpleUploadedFile("a.pdf", b"%PDF-1.4 contenu")
        valider_extension_justificatif(vrai)


class MediaPublique(TestCase):
    def test_seuls_photos_et_logos_sont_publics(self):
        self.assertEqual(self.client.get('/media/messagerie/fichiers/secret.pdf').status_code, 404)
        self.assertEqual(self.client.get('/media/utilisateurs/justificatifs/acte.pdf').status_code, 404)


class AuthentificationDurcie(BaseDonnees):
    def setUp(self):
        super().setUp()
        from django.core.cache import cache
        cache.clear()

    def test_blocage_apres_echecs_repetes(self):
        client = APIClient()
        for _ in range(5):
            r = client.post('/api/auth/login/', {'email': 'el1@t.cm', 'password': 'mauvais-mdp'}, format='json')
            self.assertEqual(r.status_code, 400)
        r = client.post('/api/auth/login/', {'email': 'el1@t.cm', 'password': 'motdepasse123'}, format='json')
        self.assertEqual(r.status_code, 429)

    def test_connexion_normale_reinitialise_le_compteur(self):
        client = APIClient()
        for _ in range(3):
            client.post('/api/auth/login/', {'email': 'el1@t.cm', 'password': 'faux'}, format='json')
        r = client.post('/api/auth/login/', {'email': 'el1@t.cm', 'password': 'motdepasse123'}, format='json')
        self.assertEqual(r.status_code, 200)

    def test_mot_de_passe_courant_refuse_a_l_inscription(self):
        r = APIClient().post('/api/auth/register/', {
            'email': 'n@t.cm', 'nom': 'N', 'prenom': 'N', 'role': 'parent', 'type_lien_eleve': 'Père',
            'password': 'password', 'password2': 'password',
        }, format='json')
        self.assertEqual(r.status_code, 400)

    def test_changement_de_mot_de_passe_revoque_les_refresh_tokens(self):
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
        refresh = RefreshToken.for_user(self.eleve1)
        self.auth(self.eleve1)
        r = self.client.post('/api/auth/changer-mot-de-passe/', {
            'ancien_mot_de_passe': 'motdepasse123', 'nouveau_mot_de_passe': 'NouveauSecret-2026',
        }, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(BlacklistedToken.objects.filter(token__jti=refresh['jti']).exists())

    def test_pas_de_lien_de_reinitialisation_pour_un_compte_suspendu(self):
        from django.core import mail
        self.eleve1.statut_validation = Utilisateur.StatutValidation.SUSPENDU
        self.eleve1.save()
        r = APIClient().post('/api/auth/mot-de-passe-oublie/', {'email': 'el1@t.cm'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_justificatif_expose_via_vue_authentifiee(self):
        self.proviseur.justificatif = SimpleUploadedFile("acte.pdf", b"%PDF-1.4 x")
        self.proviseur.statut_validation = Utilisateur.StatutValidation.CODE_VALIDE
        self.proviseur.save()
        self.auth(self.admin)
        r = self.client.get('/api/auth/comptes-en-attente/')
        ligne = [c for c in r.data if c['id'] == self.proviseur.id][0]
        self.assertEqual(ligne['justificatif'], f'/api/auth/justificatif/{self.proviseur.id}/')


class RecommandationsAcces(BaseDonnees):
    def test_matrice_recommandations(self):
        url = '/api/recommandations/'
        cible = {'eleve_id': self.eleve1.id}
        self.auth(self.enc1)
        self.assertEqual(self.client.get(url, cible).status_code, 403)     # encadreur : non
        self.auth(self.eleve2)
        self.assertEqual(self.client.get(url, cible).status_code, 403)     # autre élève : non
        self.auth(self.parent)
        self.assertEqual(self.client.get(url, cible).status_code, 200)     # parent lié : oui
        self.auth(self.proviseur)
        self.assertEqual(self.client.get(url, cible).status_code, 200)
        self.auth(self.eleve1)
        self.assertEqual(self.client.get(url).status_code, 200)            # soi-même


class TicketWebSocket(BaseDonnees):
    def setUp(self):
        super().setUp()
        from django.core.cache import cache
        cache.clear()

    def test_ticket_a_usage_unique(self):
        from messagerie.tickets import consommer_ticket
        self.auth(self.eleve1)
        r = self.client.post('/api/messagerie/ticket/')
        self.assertEqual(r.status_code, 200)
        ticket = r.data['ticket']
        self.assertEqual(consommer_ticket(ticket), self.eleve1.id)
        self.assertIsNone(consommer_ticket(ticket))          # déjà utilisé
        self.assertIsNone(consommer_ticket('falsifie'))

    def test_ticket_exige_l_authentification(self):
        self.assertEqual(APIClient().post('/api/messagerie/ticket/').status_code, 401)


class AccesNonAuthentifie(TestCase):
    def test_endpoints_proteges_sans_jeton(self):
        client = APIClient()
        for url in ['/api/clubs/', '/api/activites/', '/api/inscriptions/', '/api/participations/',
                    '/api/notifications/', '/api/messagerie/salons/', '/api/recommandations/',
                    '/api/predictions/statistiques-globales/', '/api/auth/utilisateurs/',
                    '/api/auth/parents/', '/api/auth/profil/', '/api/annees-scolaires/']:
            self.assertEqual(client.get(url).status_code, 401, url)


class ValidationRattachements(BaseDonnees):
    def setUp(self):
        super().setUp()
        self.parent2 = creer_utilisateur("par2@t.cm", Utilisateur.Role.PARENT, type_lien_eleve="Mère", telephone="699000000")
        self.demande = RelationParentEleve.objects.create(
            parent=self.parent2, enfant=self.eleve2, statut=RelationParentEleve.Statut.EN_ATTENTE,
        )

    def test_liste_des_demandes_reservee_aux_gestionnaires(self):
        url = '/api/auth/parents/demandes_rattachement/'
        self.auth(self.proviseur)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]['enfant_matricule'], 'M2')
        self.assertEqual(r.data[0]['type_lien_eleve'], 'Mère')
        for user in (self.enc1, self.eleve1, self.parent):
            self.auth(user)
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_validation_donne_acces_et_notifie(self):
        self.assertEqual(self.parent2.enfants.count(), 0)
        self.auth(self.admin)
        r = self.client.post(f'/api/auth/parents/{self.parent2.id}/lier_enfant/', {'enfant': self.eleve2.id}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.parent2.enfants.count(), 1)
        self.assertTrue(self.parent2.notifications.filter(titre="Rattachement validé").exists())
        self.assertEqual(self.client.get('/api/auth/parents/demandes_rattachement/').data, [])

    def test_refus_supprime_la_demande_et_notifie(self):
        self.auth(self.proviseur)
        r = self.client.post(f'/api/auth/parents/{self.parent2.id}/refuser_rattachement/', {'enfant': self.eleve2.id}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(RelationParentEleve.objects.filter(pk=self.demande.pk).exists())
        self.assertEqual(self.parent2.enfants.count(), 0)
        self.assertTrue(self.parent2.notifications.filter(titre="Rattachement refusé").exists())

    def test_refus_impossible_sur_un_lien_deja_valide(self):
        self.auth(self.admin)
        r = self.client.post(f'/api/auth/parents/{self.parent.id}/refuser_rattachement/', {'enfant': self.eleve1.id}, format='json')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.parent.enfants.count(), 1)

    def test_le_parent_voit_sa_demande_en_attente(self):
        self.auth(self.parent2)
        r = self.client.get('/api/auth/dashboard-parent/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['nombre_enfants'], 0)
        self.assertEqual(r.data['demandes_en_attente'], [self.eleve2.nom_complet])


class ListeOfficielleMatricules(BaseDonnees):
    def _inscrire(self, matricule, nom="Mballa", prenom="Jean", email="nouveau@t.cm", **extra):
        return APIClient().post('/api/auth/register/', {
            'email': email, 'nom': nom, 'prenom': prenom, 'role': 'eleve', 'matricule': matricule,
            'password': 'Secret-Solide-2026', 'password2': 'Secret-Solide-2026', **extra,
        }, format='json')

    def test_sans_liste_importee_l_inscription_reste_libre(self):
        self.assertEqual(self._inscrire("LIBRE01").status_code, 201)

    def test_avec_liste_matricule_inconnu_refuse(self):
        from utilisateurs.models import MatriculeOfficiel
        MatriculeOfficiel.objects.create(matricule="OFF001", nom="Mballa", prenom="Jean")
        r = self._inscrire("INCONNU")
        self.assertEqual(r.status_code, 400)
        self.assertIn('matricule', r.data)

    def test_avec_liste_mauvaise_identite_refusee(self):
        from utilisateurs.models import MatriculeOfficiel
        MatriculeOfficiel.objects.create(matricule="OFF001", nom="Mballa", prenom="Jean")
        r = self._inscrire("OFF001", nom="Usurpateur", prenom="Paul")
        self.assertEqual(r.status_code, 400)
        # même message qu'un matricule inconnu : pas d'oracle sur l'existence du matricule
        self.assertEqual(r.data['matricule'], self._inscrire("INCONNU", email="x@t.cm").data['matricule'])

    def test_identite_tolerante_accents_casse_et_prenom_compose(self):
        from utilisateurs.models import MatriculeOfficiel
        MatriculeOfficiel.objects.create(matricule="OFF002", nom="Éboué", prenom="Marie Claire", classe="3ème A")
        r = self._inscrire("off002", nom="EBOUE", prenom="marie", email="m@t.cm")
        self.assertEqual(r.status_code, 201)
        eleve = Utilisateur.objects.get(email="m@t.cm")
        self.assertEqual(eleve.matricule, "OFF002")   # orthographe officielle
        self.assertEqual(eleve.classe, "3ème A")      # classe reprise de la liste

    def test_liste_des_encadreurs_independante_de_celle_des_eleves(self):
        from utilisateurs.models import MatriculeOfficiel
        MatriculeOfficiel.objects.create(matricule="ENC001", role='encadreur', nom="Kamga", prenom="Luc")
        self.assertEqual(self._inscrire("LIBRE02", email="e2@t.cm").status_code, 201)  # liste élèves vide
        r = APIClient().post('/api/auth/register/', {
            'email': 'enc@t.cm', 'nom': 'Faux', 'prenom': 'Nom', 'role': 'encadreur',
            'type_encadreur': 'professionnel', 'matricule': 'ENC001',
            'password': 'Secret-Solide-2026', 'password2': 'Secret-Solide-2026',
        }, format='json')
        self.assertEqual(r.status_code, 400)

    def test_import_csv_reserve_a_l_administrateur(self):
        contenu = "matricule;nom;prenom;classe\nM100;Ngo;Rose;2nde C\nM101;Tala;Paul;\n"
        fichier = SimpleUploadedFile("eleves.csv", contenu.encode('utf-8'), content_type="text/csv")
        self.auth(self.proviseur)
        self.assertEqual(self.client.post('/api/auth/matricules/importer/', {'fichier': fichier}, format='multipart').status_code, 403)

        self.auth(self.admin)
        fichier = SimpleUploadedFile("eleves.csv", contenu.encode('utf-8'), content_type="text/csv")
        r = self.client.post('/api/auth/matricules/importer/', {'fichier': fichier, 'role': 'eleve'}, format='multipart')
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data['crees'], r.data['mis_a_jour'], r.data['erreurs']), (2, 0, []))

        fichier = SimpleUploadedFile("eleves.csv", contenu.encode('utf-8'), content_type="text/csv")
        r = self.client.post('/api/auth/matricules/importer/', {'fichier': fichier}, format='multipart')
        self.assertEqual((r.data['crees'], r.data['mis_a_jour']), (0, 2))   # réimport idempotent

    def test_import_csv_signale_les_lignes_invalides(self):
        contenu = "matricule,nom,prenom\nM200,Ngo,Rose\n,Sans,Matricule\nM200,Doublon,Ligne\n"
        self.auth(self.admin)
        fichier = SimpleUploadedFile("e.csv", contenu.encode('utf-8'), content_type="text/csv")
        r = self.client.post('/api/auth/matricules/importer/', {'fichier': fichier}, format='multipart')
        self.assertEqual(r.data['crees'], 1)
        self.assertEqual(len(r.data['erreurs']), 2)

    def test_import_csv_colonnes_manquantes(self):
        self.auth(self.admin)
        fichier = SimpleUploadedFile("e.csv", b"code,nom\nM1,Ngo\n", content_type="text/csv")
        r = self.client.post('/api/auth/matricules/importer/', {'fichier': fichier}, format='multipart')
        self.assertEqual(r.status_code, 400)

    def test_consultation_de_la_liste(self):
        from utilisateurs.models import MatriculeOfficiel
        MatriculeOfficiel.objects.create(matricule="M1", nom="Ngo", prenom="Rose")
        MatriculeOfficiel.objects.create(matricule="M2", nom="Tala", prenom="Paul")  # M2 = eleve2 (compte créé)
        self.auth(self.proviseur)
        r = self.client.get('/api/auth/matricules/')
        self.assertEqual(r.status_code, 200)
        etat = {m['matricule']: m['compte_cree'] for m in r.data}
        self.assertEqual(etat, {"M1": True, "M2": True})   # M1, M2 utilisés par eleve1/eleve2 (BaseDonnees)
        self.auth(self.eleve1)
        self.assertEqual(self.client.get('/api/auth/matricules/').status_code, 403)
        self.auth(self.proviseur)
        self.assertEqual(self.client.delete(f'/api/auth/matricules/{r.data[0]["id"]}/').status_code, 403)
