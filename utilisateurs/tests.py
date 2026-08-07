from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Utilisateur, JournalActivite


class UtilisateurModelTest(TestCase):
    """Test 1 : création d'un utilisateur via le manager personnalisé."""

    def test_creation_utilisateur_avec_email(self):
        utilisateur = Utilisateur.objects.create_user(
            email="test@lycee.cm",
            password="motdepasse123",
            nom="Test",
            prenom="Utilisateur",
            role=Utilisateur.Role.ELEVE,
        )
        self.assertEqual(utilisateur.email, "test@lycee.cm")
        self.assertTrue(utilisateur.check_password("motdepasse123"))
        self.assertEqual(utilisateur.role, "eleve")
        self.assertTrue(utilisateur.is_active)
        self.assertFalse(utilisateur.is_staff)

    def test_creation_superuser(self):
        admin = Utilisateur.objects.create_superuser(
            email="admin@lycee.cm",
            password="adminpass123",
            nom="Admin",
            prenom="Super",
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.role, "administrateur")


class InscriptionAPITest(APITestCase):
    """Test 2 : inscription via l'endpoint /api/auth/register/."""

    def test_inscription_reussie(self):
            url = reverse('inscription')
            data = {
                "email": "eleve2@lycee.cm",
                "nom": "Mballa",
                "prenom": "Jean",
                "password": "motdepasse123",
                "password2": "motdepasse123",
                "role": "eleve",
                "matricule": "MAT2024001",
            }
            response = self.client.post(url, data, format='json')

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertTrue(Utilisateur.objects.filter(email="eleve2@lycee.cm").exists())
            self.assertEqual(response.data['statut_validation'], 'en_attente')
        
    def test_inscription_mots_de_passe_differents(self):
        url = reverse('inscription')
        data = {
            "email": "eleve3@lycee.cm",
            "nom": "Fotso",
            "prenom": "Marie",
            "password": "motdepasse123",
            "password2": "autremotdepasse",
            "role": "eleve",
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ConnexionAPITest(APITestCase):
    """Test 3 : connexion via l'endpoint /api/auth/login/."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            email="connexion@lycee.cm",
            password="motdepasse123",
            nom="Ngono",
            prenom="Paul",
            role=Utilisateur.Role.ENCADREUR,
        )

    def test_connexion_reussie(self):
        url = reverse('connexion')
        data = {"email": "connexion@lycee.cm", "password": "motdepasse123"}
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertEqual(response.data['utilisateur']['email'], "connexion@lycee.cm")

    def test_connexion_mot_de_passe_incorrect(self):
        url = reverse('connexion')
        data = {"email": "connexion@lycee.cm", "password": "mauvaismotdepasse"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
from .models import RelationParentEleve, CodeInvitation


class RelationParentEleveTest(APITestCase):
    """Test : lien parent-enfant et propriétés .enfants / .parents."""

    def setUp(self):
        self.parent = Utilisateur.objects.create_user(
            email="parenttest1@lycee.cm", password="motdepasse123",
            nom="Fouda", prenom="Marcelline", role=Utilisateur.Role.PARENT,
        )
        self.eleve = Utilisateur.objects.create_user(
            email="elevetest1@lycee.cm", password="motdepasse123",
            nom="Fouda", prenom="Junior", role=Utilisateur.Role.ELEVE,
        )

    def test_creation_relation_et_proprietes(self):
        RelationParentEleve.objects.create(parent=self.parent, enfant=self.eleve)

        self.assertEqual(self.parent.enfants.count(), 1)
        self.assertEqual(self.parent.enfants.first(), self.eleve)
        self.assertEqual(self.eleve.parents.count(), 1)
        self.assertEqual(self.eleve.parents.first(), self.parent)

    def test_eleve_sans_lien_a_liste_parents_vide(self):
        autre_eleve = Utilisateur.objects.create_user(
            email="elevetest2@lycee.cm", password="motdepasse123",
            nom="Sans", prenom="Parent", role=Utilisateur.Role.ELEVE,
        )
        self.assertEqual(autre_eleve.parents.count(), 0)

    def test_contrainte_unicite_relation(self):
        RelationParentEleve.objects.create(parent=self.parent, enfant=self.eleve)
        with self.assertRaises(Exception):
            RelationParentEleve.objects.create(parent=self.parent, enfant=self.eleve)


class InscriptionParentAPITest(APITestCase):
    """Test : inscription publique avec rôle parent (actif immédiatement, sans validation)."""

    def test_inscription_parent_reussie_et_statut_valide(self):
        url = reverse('inscription')
        data = {
            "email": "parentapi@lycee.cm", "nom": "Essomba", "prenom": "Rita",
            "password": "motdepasse123", "password2": "motdepasse123",
            "role": "parent", "type_lien_eleve": "Mère",
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', response.data)  # actif immédiatement, contrairement aux autres rôles
        utilisateur = Utilisateur.objects.get(email="parentapi@lycee.cm")
        self.assertEqual(utilisateur.statut_validation, Utilisateur.StatutValidation.VALIDE)

    def test_inscription_parent_sans_lien_eleve_refusee(self):
        url = reverse('inscription')
        data = {
            "email": "parentsanslien@lycee.cm", "nom": "Test", "prenom": "Test",
            "password": "motdepasse123", "password2": "motdepasse123", "role": "parent",
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class InscriptionEleveEtEncadreurStatutTest(APITestCase):
    """Test : les rôles élève/encadreur/proviseur passent en_attente à la création."""

    def test_inscription_eleve_statut_en_attente(self):
        url = reverse('inscription')
        data = {
            "email": "eleveattente@lycee.cm", "nom": "Test", "prenom": "Eleve",
            "password": "motdepasse123", "password2": "motdepasse123",
            "role": "eleve", "matricule": "MAT001",
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn('access', response.data)  # pas de token, compte non actif
        utilisateur = Utilisateur.objects.get(email="eleveattente@lycee.cm")
        self.assertEqual(utilisateur.statut_validation, Utilisateur.StatutValidation.EN_ATTENTE)

    def test_inscription_eleve_sans_matricule_refusee(self):
        url = reverse('inscription')
        data = {
            "email": "eleveinvalide@lycee.cm", "nom": "Test", "prenom": "Eleve",
            "password": "motdepasse123", "password2": "motdepasse123", "role": "eleve",
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inscription_administrateur_interdite(self):
        url = reverse('inscription')
        data = {
            "email": "adminpublic@lycee.cm", "nom": "Test", "prenom": "Admin",
            "password": "motdepasse123", "password2": "motdepasse123", "role": "administrateur",
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inscription_proviseur_sans_code_refusee(self):
        url = reverse('inscription')
        data = {
            "email": "provtest@lycee.cm", "nom": "Test", "prenom": "Proviseur",
            "password": "motdepasse123", "password2": "motdepasse123", "role": "proviseur",
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inscription_proviseur_avec_code_valide_reussie(self):
        CodeInvitation.objects.create(code="CODE123", role_cible=CodeInvitation.RoleCible.RESPONSABLE_PEDAGOGIQUE)
        url = reverse('inscription')
        data = {
            "email": "provvalide@lycee.cm", "nom": "Test", "prenom": "Proviseur",
            "password": "motdepasse123", "password2": "motdepasse123", "role": "proviseur",
            "code_invitation": "CODE123", "fonction": "Direction des études",
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        code = CodeInvitation.objects.get(code="CODE123")
        self.assertTrue(code.utilise)


class ConnexionCompteEnAttenteTest(APITestCase):
    """Test : la connexion est bloquée pour un compte non validé."""

    def setUp(self):
        self.eleve_en_attente = Utilisateur.objects.create_user(
            email="bloque@lycee.cm", password="motdepasse123",
            nom="Bloque", prenom="Test", role=Utilisateur.Role.ELEVE,
            statut_validation=Utilisateur.StatutValidation.EN_ATTENTE,
        )
        self.eleve_refuse = Utilisateur.objects.create_user(
            email="refuse@lycee.cm", password="motdepasse123",
            nom="Refuse", prenom="Test", role=Utilisateur.Role.ELEVE,
            statut_validation=Utilisateur.StatutValidation.REFUSE,
        )

    def test_connexion_compte_en_attente_refusee(self):
        url = reverse('connexion')
        response = self.client.post(url, {"email": "bloque@lycee.cm", "password": "motdepasse123"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_connexion_compte_refuse_refusee(self):
        url = reverse('connexion')
        response = self.client.post(url, {"email": "refuse@lycee.cm", "password": "motdepasse123"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ParentViewSetAPITest(APITestCase):
    """Test : gestion admin des parents (CRUD + lier_enfant/delier_enfant)."""

    def setUp(self):
        self.admin = Utilisateur.objects.create_user(
            email="adminparent@lycee.cm", password="motdepasse123",
            nom="Admin", prenom="Test", role=Utilisateur.Role.ADMINISTRATEUR,
        )
        self.parent = Utilisateur.objects.create_user(
            email="parentgere@lycee.cm", password="motdepasse123",
            nom="Gere", prenom="Parent", role=Utilisateur.Role.PARENT,
        )
        self.eleve = Utilisateur.objects.create_user(
            email="enfantgere@lycee.cm", password="motdepasse123",
            nom="Gere", prenom="Enfant", role=Utilisateur.Role.ELEVE,
        )

    def test_admin_peut_lister_parents(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(reverse('parent-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_admin_ne_peut_pas_lister_parents(self):
        self.client.force_authenticate(user=self.eleve)
        response = self.client.get(reverse('parent-list'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_lier_enfant_a_parent(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('parent-lier-enfant', args=[self.parent.id])
        response = self.client.post(url, {"enfant": self.eleve.id}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(RelationParentEleve.objects.filter(parent=self.parent, enfant=self.eleve).exists())

    def test_delier_enfant_de_parent(self):
        RelationParentEleve.objects.create(parent=self.parent, enfant=self.eleve)
        self.client.force_authenticate(user=self.admin)
        url = reverse('parent-delier-enfant', args=[self.parent.id])
        response = self.client.post(url, {"enfant": self.eleve.id}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(RelationParentEleve.objects.filter(parent=self.parent, enfant=self.eleve).exists())


class MesEnfantsEtDashboardParentTest(APITestCase):
    """Test : endpoints self-service du parent (mes-enfants, dashboard-parent)."""

    def setUp(self):
        self.parent = Utilisateur.objects.create_user(
            email="parentdash@lycee.cm", password="motdepasse123",
            nom="Dash", prenom="Parent", role=Utilisateur.Role.PARENT,
        )
        self.eleve = Utilisateur.objects.create_user(
            email="enfantdash@lycee.cm", password="motdepasse123",
            nom="Dash", prenom="Enfant", role=Utilisateur.Role.ELEVE,
        )
        RelationParentEleve.objects.create(parent=self.parent, enfant=self.eleve)

    def test_mes_enfants_retourne_uniquement_ses_enfants(self):
        self.client.force_authenticate(user=self.parent)
        response = self.client.get(reverse('mes_enfants'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['email'], "enfantdash@lycee.cm")

    def test_eleve_ne_peut_pas_utiliser_mes_enfants(self):
        self.client.force_authenticate(user=self.eleve)
        response = self.client.get(reverse('mes_enfants'))
        self.assertEqual(len(response.data), 0)  # queryset vide, pas d'erreur

    def test_dashboard_parent_structure(self):
        self.client.force_authenticate(user=self.parent)
        response = self.client.get(reverse('dashboard_parent'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nombre_enfants'], 1)
        self.assertEqual(len(response.data['enfants']), 1)

    def test_dashboard_parent_refuse_a_un_non_parent(self):
        self.client.force_authenticate(user=self.eleve)
        response = self.client.get(reverse('dashboard_parent'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ComptesEnAttenteEtValidationTest(APITestCase):
    """Test : liste des comptes en attente, validation et refus par un admin."""

    def setUp(self):
        self.admin = Utilisateur.objects.create_user(
            email="adminvalid@lycee.cm", password="motdepasse123",
            nom="Admin", prenom="Valid", role=Utilisateur.Role.ADMINISTRATEUR,
        )
        self.eleve_attente = Utilisateur.objects.create_user(
            email="attentevalid@lycee.cm", password="motdepasse123",
            nom="Attente", prenom="Test", role=Utilisateur.Role.ELEVE,
            statut_validation=Utilisateur.StatutValidation.EN_ATTENTE,
        )

    def test_liste_comptes_en_attente(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(reverse('comptes_en_attente'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_valider_compte(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('valider_compte', args=[self.eleve_attente.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.eleve_attente.refresh_from_db()
        self.assertEqual(self.eleve_attente.statut_validation, Utilisateur.StatutValidation.VALIDE)
        self.assertEqual(self.eleve_attente.valide_par, self.admin)

    def test_refuser_compte_avec_motif(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('refuser_compte', args=[self.eleve_attente.id])
        response = self.client.post(url, {"motif": "Matricule invalide"}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.eleve_attente.refresh_from_db()
        self.assertEqual(self.eleve_attente.statut_validation, Utilisateur.StatutValidation.REFUSE)
        self.assertEqual(self.eleve_attente.motif_refus, "Matricule invalide")


class UtilisateurAdminViewSetTest(APITestCase):
    """Test : gestion complète des utilisateurs (recherche, filtre, suspendre/réactiver)."""

    def setUp(self):
        self.admin = Utilisateur.objects.create_user(
            email="adminlist@lycee.cm", password="motdepasse123",
            nom="Admin", prenom="Liste", role=Utilisateur.Role.ADMINISTRATEUR,
        )
        self.eleve = Utilisateur.objects.create_user(
            email="elevesuspend@lycee.cm", password="motdepasse123",
            nom="Suspend", prenom="Test", role=Utilisateur.Role.ELEVE,
        )

    def test_liste_utilisateurs_filtre_par_role(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(reverse('utilisateur-admin-list'), {'role': 'eleve'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_suspendre_et_reactiver_utilisateur(self):
        self.client.force_authenticate(user=self.admin)

        url_suspendre = reverse('utilisateur-admin-suspendre', args=[self.eleve.id])
        response = self.client.post(url_suspendre)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.eleve.refresh_from_db()
        self.assertEqual(self.eleve.statut_validation, Utilisateur.StatutValidation.SUSPENDU)

        url_reactiver = reverse('utilisateur-admin-reactiver', args=[self.eleve.id])
        response = self.client.post(url_reactiver)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.eleve.refresh_from_db()
        self.assertEqual(self.eleve.statut_validation, Utilisateur.StatutValidation.VALIDE)