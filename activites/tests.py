from datetime import date, time
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from utilisateurs.models import Utilisateur
from clubs.models import Club
from .models import Activite, HistoriqueActivite


class ActiviteModelTest(APITestCase):
    """Test 1 : création d'une activité et vérification des champs."""

    def setUp(self):
        self.encadreur = Utilisateur.objects.create_user(
            email="encadreur2@lycee.cm", password="motdepasse123",
            nom="Ateba", prenom="Marc", role=Utilisateur.Role.ENCADREUR,
        )
        self.club = Club.objects.create(
            nom="Club Sciences", description="Club scientifique",
            categorie=Club.Categorie.SCIENTIFIQUE, objectifs="Expériences",
            nombre_max_membres=20,
        )

    def test_creation_activite(self):
        activite = Activite.objects.create(
            club=self.club,
            titre="Expo-sciences",
            description="Exposition annuelle",
            date=date(2026, 10, 1),
            heure=time(14, 0),
            lieu="Amphithéâtre",
            budget=50000,
            responsable=self.encadreur,
        )
        self.assertEqual(activite.statut, Activite.Statut.PLANIFIEE)
        self.assertEqual(activite.club, self.club)


class ActiviteAPITest(APITestCase):
    """Tests 2 et 3 : création via API et action de validation avec historique."""

    def setUp(self):
        self.admin = Utilisateur.objects.create_user(
            email="admin3@lycee.cm", password="motdepasse123",
            nom="Admin", prenom="Trois", role=Utilisateur.Role.ADMINISTRATEUR,
        )
        self.eleve = Utilisateur.objects.create_user(
            email="eleve4@lycee.cm", password="motdepasse123",
            nom="Eleve", prenom="Quatre", role=Utilisateur.Role.ELEVE,
        )
        self.club = Club.objects.create(
            nom="Club Théâtre 2", description="Club artistique",
            categorie=Club.Categorie.ARTISTIQUE, objectifs="Expression scénique",
            nombre_max_membres=15,
        )

    def test_creation_activite_via_api(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('activite-list')
        data = {
            "club": self.club.id,
            "titre": "Pièce de théâtre",
            "description": "Représentation de fin d'année",
            "date": "2026-11-20",
            "heure": "18:00:00",
            "lieu": "Salle polyvalente",
            "budget": 30000,
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(HistoriqueActivite.objects.count(), 1)

    def test_eleve_ne_peut_pas_creer_activite(self):
        self.client.force_authenticate(user=self.eleve)
        url = reverse('activite-list')
        data = {
            "club": self.club.id, "titre": "Test", "description": "Test",
            "date": "2026-11-20", "heure": "18:00:00", "lieu": "Test", "budget": 0,
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_validation_activite(self):
        self.client.force_authenticate(user=self.admin)
        activite = Activite.objects.create(
            club=self.club, titre="Répétition", description="Test",
            date=date(2026, 11, 25), heure=time(17, 0), lieu="Salle B", budget=0,
        )
        url = reverse('activite-valider', args=[activite.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        activite.refresh_from_db()
        self.assertEqual(activite.statut, Activite.Statut.VALIDEE)
        self.assertEqual(activite.historique.count(), 1)