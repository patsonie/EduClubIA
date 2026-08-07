from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from utilisateurs.models import Utilisateur
from clubs.models import Club
from annees_scolaires.models import AnneeScolaire
from .models import Inscription


class InscriptionModelTest(APITestCase):
    """Test 1 : contrainte d'unicité par année scolaire."""

    def setUp(self):
        self.eleve = Utilisateur.objects.create_user(
            email="eleve6@lycee.cm", password="motdepasse123",
            nom="Kamga", prenom="Alice", role=Utilisateur.Role.ELEVE,
        )
        self.club = Club.objects.create(
            nom="Club Danse", description="Club de danse",
            categorie=Club.Categorie.ARTISTIQUE, objectifs="Danser",
            nombre_max_membres=10,
        )
        self.annee = AnneeScolaire.objects.create(
            libelle="2025-2026", date_debut="2025-09-01", date_fin="2026-07-31", est_active=True,
        )

    def test_creation_inscription(self):
        inscription = Inscription.objects.create(
            eleve=self.eleve, club=self.club, annee_scolaire=self.annee,
        )
        self.assertEqual(inscription.statut, Inscription.Statut.EN_ATTENTE)


class InscriptionAPITest(APITestCase):
    """Tests 2 et 3 : inscription via API, double inscription refusée, et validation."""

    def setUp(self):
        self.eleve = Utilisateur.objects.create_user(
            email="eleve7@lycee.cm", password="motdepasse123",
            nom="Fouda", prenom="Eric", role=Utilisateur.Role.ELEVE,
        )
        self.admin = Utilisateur.objects.create_user(
            email="admin5@lycee.cm", password="motdepasse123",
            nom="Admin", prenom="Cinq", role=Utilisateur.Role.ADMINISTRATEUR,
        )
        self.club = Club.objects.create(
            nom="Club Lecture", description="Club de lecture",
            categorie=Club.Categorie.CULTUREL, objectifs="Lire", nombre_max_membres=10,
        )
        self.annee = AnneeScolaire.objects.create(
            libelle="2025-2026", date_debut="2025-09-01", date_fin="2026-07-31", est_active=True,
        )

    def test_double_inscription_refusee(self):
        self.client.force_authenticate(user=self.eleve)
        url = reverse('inscription-list')
        data = {"club": self.club.id, "annee_scolaire": self.annee.id}

        response1 = self.client.post(url, data, format='json')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        response2 = self.client.post(url, data, format='json')
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validation_inscription_par_admin(self):
        inscription = Inscription.objects.create(
            eleve=self.eleve, club=self.club, annee_scolaire=self.annee,
        )
        self.client.force_authenticate(user=self.admin)
        url = reverse('inscription-valider', args=[inscription.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        inscription.refresh_from_db()
        self.assertEqual(inscription.statut, Inscription.Statut.VALIDEE)
        self.assertEqual(inscription.historique.count(), 1)