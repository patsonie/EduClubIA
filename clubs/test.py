from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from utilisateurs.models import Utilisateur
from .models import Club


class ClubModelTest(APITestCase):
    """Test 1 : création d'un club et propriétés calculées."""

    def setUp(self):
        self.encadreur = Utilisateur.objects.create_user(
            email="encadreur@lycee.cm",
            password="motdepasse123",
            nom="Biya",
            prenom="Paul",
            role=Utilisateur.Role.ENCADREUR,
        )

    def test_creation_club(self):
        club = Club.objects.create(
            nom="Club Informatique",
            description="Apprentissage de la programmation",
            categorie=Club.Categorie.TECHNOLOGIQUE,
            objectifs="Initier au développement web",
            responsable=self.encadreur,
            nombre_max_membres=20,
            statut=Club.Statut.ACTIF,
        )
        self.assertEqual(club.nom, "Club Informatique")
        self.assertEqual(club.nombre_membres_actuels, 0)
        self.assertEqual(club.places_disponibles, 20)


class ClubAPITest(APITestCase):
    """Tests 2 et 3 : accès et permissions sur l'API des clubs."""

    def setUp(self):
        self.admin = Utilisateur.objects.create_user(
            email="admin2@lycee.cm",
            password="motdepasse123",
            nom="Admin",
            prenom="Test",
            role=Utilisateur.Role.ADMINISTRATEUR,
        )
        self.eleve = Utilisateur.objects.create_user(
            email="eleve@lycee.cm",
            password="motdepasse123",
            nom="Eleve",
            prenom="Test",
            role=Utilisateur.Role.ELEVE,
        )
        self.club = Club.objects.create(
            nom="Club Théâtre",
            description="Club artistique",
            categorie=Club.Categorie.ARTISTIQUE,
            objectifs="Développer l'expression scénique",
            nombre_max_membres=15,
        )

    def test_liste_clubs_accessible_a_tous_les_authentifies(self):
        self.client.force_authenticate(user=self.eleve)
        url = reverse('club-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']) if 'results' in response.data else len(response.data), 1)

    def test_eleve_ne_peut_pas_creer_club(self):
        self.client.force_authenticate(user=self.eleve)
        url = reverse('club-list')
        data = {
            "nom": "Club Musique",
            "description": "Test",
            "categorie": "artistique",
            "objectifs": "Test",
            "nombre_max_membres": 10,
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_peut_creer_club(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('club-list')
        data = {
            "nom": "Club Musique",
            "description": "Club de musique",
            "categorie": "artistique",
            "objectifs": "Apprendre un instrument",
            "nombre_max_membres": 10,
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Club.objects.filter(nom="Club Musique").exists())