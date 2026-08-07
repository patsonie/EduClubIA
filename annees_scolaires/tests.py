from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from utilisateurs.models import Utilisateur
from .models import AnneeScolaire


class AnneeScolaireModelTest(APITestCase):
    """Test 1 : une seule année scolaire peut être active à la fois."""

    def test_activation_desactive_les_autres(self):
        annee1 = AnneeScolaire.objects.create(
            libelle="2024-2025", date_debut="2024-09-01", date_fin="2025-07-31",
            est_active=True,
        )
        annee2 = AnneeScolaire.objects.create(
            libelle="2025-2026", date_debut="2025-09-01", date_fin="2026-07-31",
            est_active=True,
        )
        annee1.refresh_from_db()
        self.assertFalse(annee1.est_active)
        self.assertTrue(annee2.est_active)


class AnneeScolaireAPITest(APITestCase):
    """Tests 2 et 3 : permissions et création via l'API."""

    def setUp(self):
        self.admin = Utilisateur.objects.create_user(
            email="admin4@lycee.cm", password="motdepasse123",
            nom="Admin", prenom="Quatre", role=Utilisateur.Role.ADMINISTRATEUR,
        )
        self.eleve = Utilisateur.objects.create_user(
            email="eleve5@lycee.cm", password="motdepasse123",
            nom="Eleve", prenom="Cinq", role=Utilisateur.Role.ELEVE,
        )

    def test_eleve_ne_peut_pas_creer_annee_scolaire(self):
        self.client.force_authenticate(user=self.eleve)
        url = reverse('annee-scolaire-list')
        data = {
            "libelle": "2026-2027", "date_debut": "2026-09-01",
            "date_fin": "2027-07-31", "est_active": False,
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_peut_creer_et_valider_dates(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('annee-scolaire-list')
        data = {
            "libelle": "2026-2027", "date_debut": "2027-09-01",
            "date_fin": "2026-07-31", "est_active": False,
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)