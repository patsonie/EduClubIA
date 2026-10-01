"""Tests : profil, centres d'intérêt, recommandations IA et inscription en une seule page."""
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status

from clubs.models import Club
from recommandations.services import calculer_recommandations_hybrides
from utilisateurs.models import CentreInteret, Utilisateur

from .tests_securite import BaseDonnees, creer_utilisateur


# Sans collectstatic (tests), le stockage Manifest ne connaît aucun fichier : on le remplace par le simple.
STOCKAGE_STATIQUE_SIMPLE = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


def centre(nom):
    return CentreInteret.objects.get(nom=nom)


class ProfilTest(BaseDonnees):
    @override_settings(STORAGES=STOCKAGE_STATIQUE_SIMPLE)
    def test_page_profil_s_affiche_sans_erreur_500(self):
        # Régression : {% static 'images/avatar-defaut.png' %} visait un fichier inexistant ; avec le
        # stockage Manifest de production, cela levait une ValueError (HTTP 500).
        r = self.client.get('/profil/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertContains(r, 'conteneur-interets')
        self.assertNotContains(r, 'avatar-defaut')

    def test_profil_api_pour_tous_les_cas(self):
        nouveau = creer_utilisateur("neuf@t.cm", Utilisateur.Role.ELEVE)           # sans rien
        incomplet = creer_utilisateur("inc@t.cm", Utilisateur.Role.ELEVE, classe="2nde")
        complet = creer_utilisateur("comp@t.cm", Utilisateur.Role.ELEVE, classe="2nde", filiere="C",
                                    telephone="600000000", centres_interet="lecture")
        complet.interets.set([centre("Informatique")])
        for utilisateur in (nouveau, incomplet, complet, self.admin, self.parent, self.enc1):
            self.auth(utilisateur)
            r = self.client.get('/api/auth/profil/')
            self.assertEqual(r.status_code, status.HTTP_200_OK, utilisateur.email)
            self.assertIn('interets', r.data)
        self.assertEqual(r.data['interets'], [])

    def test_preferences_de_notification_accessibles_depuis_le_profil(self):
        # Régression : « preferences/ » était capturé par le routeur (404), l'onglet ne chargeait rien.
        self.auth(self.eleve1)
        r = self.client.get('/api/notifications/preferences/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        r = self.client.put('/api/notifications/preferences/', {'notifications_email': False}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertFalse(r.data['notifications_email'])

    def test_centres_actifs_listes_publiquement(self):
        inactif = CentreInteret.objects.create(nom="Inactif", actif=False)
        r = self.client.get('/api/auth/interets/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        noms = [c['nom'] for c in r.data]
        self.assertIn("Informatique", noms)
        self.assertNotIn(inactif.nom, noms)


class ProfilCompletTest(BaseDonnees):
    def test_libelle_du_role_et_champs_par_role(self):
        self.enc1.fonction, self.enc1.type_encadreur = "Coach", Utilisateur.TypeEncadreur.VACATAIRE
        self.enc1.save()
        self.auth(self.enc1)
        r = self.client.get('/api/auth/profil/')
        self.assertEqual(r.data['role_libelle'], "Encadreur")
        self.assertEqual(r.data['fonction'], "Coach")
        self.assertEqual(r.data['type_encadreur_libelle'], "Encadreur vacataire")
        self.auth(self.eleve1)
        r = self.client.get('/api/auth/profil/')
        self.assertEqual(r.data['role_libelle'], "Élève")
        self.assertEqual(r.data['matricule'], "M1")
        self.assertIsNone(r.data['type_encadreur_libelle'])

    def test_identite_validee_et_moyenne_non_modifiables(self):
        self.auth(self.eleve1)
        r = self.client.patch('/api/auth/profil/', {
            'matricule': 'PIRATE', 'etablissement': 'Autre lycée', 'moyenne_generale': '20',
            'role': 'administrateur', 'email': 'pirate@t.cm', 'telephone': '699000000', 'fonction': 'Chef',
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.eleve1.refresh_from_db()
        self.assertEqual(self.eleve1.matricule, "M1")
        self.assertIsNone(self.eleve1.moyenne_generale)
        self.assertEqual(self.eleve1.role, Utilisateur.Role.ELEVE)
        self.assertEqual(self.eleve1.email, "el1@t.cm")
        self.assertEqual(self.eleve1.telephone, "699000000")  # champ réellement modifiable

    def test_modification_des_champs_professionnels(self):
        self.auth(self.enc1)
        r = self.client.patch('/api/auth/profil/', {
            'fonction': 'Entraîneur', 'domaine_competence': 'Sport', 'date_naissance': '1990-05-04',
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.enc1.refresh_from_db()
        self.assertEqual((self.enc1.fonction, self.enc1.domaine_competence), ('Entraîneur', 'Sport'))
        self.assertEqual(str(self.enc1.date_naissance), '1990-05-04')

    def test_envoi_de_photo_en_multipart(self):
        import io
        import tempfile
        from PIL import Image
        tampon = io.BytesIO()
        Image.new('RGB', (20, 20), (120, 80, 200)).save(tampon, 'PNG')
        with tempfile.TemporaryDirectory() as dossier, override_settings(MEDIA_ROOT=dossier):
            self.auth(self.eleve1)
            fichier = SimpleUploadedFile('moi.png', tampon.getvalue(), content_type='image/png')
            r = self.client.patch('/api/auth/profil/', {'photo': fichier}, format='multipart')
            self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
            self.assertIn('utilisateurs/photos/', r.data['photo'])
            faux = SimpleUploadedFile('virus.exe', b'MZ', content_type='application/octet-stream')
            r = self.client.patch('/api/auth/profil/', {'photo': faux}, format='multipart')
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class InteretsProfilTest(BaseDonnees):
    def test_eleve_ajoute_plusieurs_centres(self):
        self.auth(self.eleve1)
        ids = [centre("Informatique").id, centre("Football").id, centre("Lecture").id]
        r = self.client.patch('/api/auth/profil/', {'interets': ids}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(set(self.eleve1.interets.values_list('id', flat=True)), set(ids))
        self.assertEqual(len(r.data['interets_details']), 3)

    def test_eleve_retire_un_centre(self):
        self.eleve1.interets.set([centre("Informatique"), centre("Football")])
        self.auth(self.eleve1)
        r = self.client.patch('/api/auth/profil/', {'interets': [centre("Football").id]}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(list(self.eleve1.interets.all()), [centre("Football")])

    def test_modifier_son_profil_ne_touche_pas_un_autre_eleve(self):
        self.eleve2.interets.set([centre("Musique")])
        self.auth(self.eleve1)
        # Un id ou eleve_id injecté dans la requête est ignoré : seul le profil connecté est modifié.
        r = self.client.patch('/api/auth/profil/', {
            'id': self.eleve2.id, 'eleve_id': self.eleve2.id, 'interets': [centre("Football").id],
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(list(self.eleve2.interets.all()), [centre("Musique")])
        self.assertEqual(list(self.eleve1.interets.all()), [centre("Football")])

    def test_centre_inactif_ou_inexistant_refuse(self):
        inactif = CentreInteret.objects.create(nom="Ancien", actif=False)
        self.auth(self.eleve1)
        for valeur in ([inactif.id], [999999]):
            r = self.client.patch('/api/auth/profil/', {'interets': valeur}, format='json')
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_eleve_ne_peut_pas_definir_d_interets(self):
        self.auth(self.parent)
        r = self.client.patch('/api/auth/profil/', {'interets': [centre("Sciences").id]}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anonyme_ne_peut_pas_modifier_le_profil(self):
        r = self.client.patch('/api/auth/profil/', {'interets': []}, format='json')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)


class InteretsRecommandationsTest(BaseDonnees):
    def setUp(self):
        super().setUp()
        self.eleve3 = creer_utilisateur("el3@t.cm", Utilisateur.Role.ELEVE, matricule="M3")
        self.club_sport = Club.objects.create(
            nom="Club Football", description="matchs", objectifs="équipe",
            categorie=Club.Categorie.SPORTIF, responsable=self.enc2,
            nombre_max_membres=20, statut=Club.Statut.ACTIF,
        )

    def test_eleve_sans_interet_obtient_des_recommandations(self):
        self.auth(self.eleve3)
        r = self.client.get('/api/recommandations/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(len(r.data) > 0)  # repli sur les clubs populaires

    def test_les_interets_orientent_les_recommandations(self):
        self.eleve3.interets.set([centre("Football")])
        resultats = calculer_recommandations_hybrides(self.eleve3)
        self.assertEqual(resultats[0]["club"], self.club_sport)
        self.assertIn("Football", resultats[0]["explication"])  # explication fondée sur l'intérêt réel

        self.eleve3.interets.set([centre("Informatique")])
        resultats = calculer_recommandations_hybrides(self.eleve3)
        self.assertEqual(resultats[0]["club"].categorie, Club.Categorie.TECHNOLOGIQUE)

    def test_interet_inactif_ignore(self):
        self.eleve3.interets.set([centre("Football")])
        CentreInteret.objects.filter(nom="Football").update(actif=False)
        resultats = calculer_recommandations_hybrides(self.eleve3)
        for r in resultats:
            self.assertNotIn("correspond à vos centres d'intérêt", r["explication"])


class InscriptionUnePageTest(BaseDonnees):
    def donnees(self, **extra):
        base = {
            'email': 'nouveau@t.cm', 'nom': 'Nouveau', 'prenom': 'Eleve', 'role': 'eleve',
            'telephone': '600000000', 'date_naissance': '2010-01-01', 'genre': 'M',
            'matricule': 'MX1', 'classe': '2nde A',
            'password': 'Motdepasse123', 'password2': 'Motdepasse123',
        }
        base.update(extra)
        return base

    @override_settings(STORAGES=STOCKAGE_STATIQUE_SIMPLE)
    def test_page_inscription_unique(self):
        r = self.client.get('/inscription/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertContains(r, 'section-interets')
        self.assertNotContains(r, 'btn-etape-suivante')

    def test_inscription_cree_compte_et_interets(self):
        ids = [centre("Informatique").id, centre("Football").id]
        r = self.client.post('/api/auth/register/', self.donnees(interets=ids), format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        utilisateur = Utilisateur.objects.get(email='nouveau@t.cm')
        self.assertEqual(set(utilisateur.interets.values_list('id', flat=True)), set(ids))
        self.assertTrue(utilisateur.check_password('Motdepasse123'))

    def test_inscription_sans_interet(self):
        r = self.client.post('/api/auth/register/', self.donnees(), format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(Utilisateur.objects.get(email='nouveau@t.cm').interets.count(), 0)

    def test_inscription_invalide_ne_cree_rien(self):
        r = self.client.post('/api/auth/register/', self.donnees(interets=[999999]), format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        r = self.client.post('/api/auth/register/', self.donnees(password2='Autre12345'), format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Utilisateur.objects.filter(email='nouveau@t.cm').exists())

    def test_creation_atomique_si_une_etape_echoue(self):
        donnees = {
            'email': 'parent2@t.cm', 'nom': 'Parent', 'prenom': 'Deux', 'role': 'parent',
            'telephone': '600000001', 'date_naissance': '1980-01-01', 'genre': 'F',
            'type_lien_eleve': 'Mère', 'matricule_enfant': 'M1',
            'password': 'Motdepasse123', 'password2': 'Motdepasse123',
        }
        with mock.patch('utilisateurs.models.RelationParentEleve.objects.get_or_create',
                        side_effect=RuntimeError("panne")):
            with self.assertRaises(RuntimeError):
                self.client.post('/api/auth/register/', donnees, format='json')
        self.assertFalse(Utilisateur.objects.filter(email='parent2@t.cm').exists())
