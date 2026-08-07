from annees_scolaires.models import AnneeScolaire
from inscriptions.models import Inscription


class RetirerMembreClubTest(APITestCase):
    """Test : retrait d'un membre d'un club via l'action dédiée."""

    def setUp(self):
        self.admin = Utilisateur.objects.create_user(
            email="adminretrait@lycee.cm", password="motdepasse123",
            nom="Admin", prenom="Retrait", role=Utilisateur.Role.ADMINISTRATEUR,
        )
        self.eleve = Utilisateur.objects.create_user(
            email="eleveretrait@lycee.cm", password="motdepasse123",
            nom="Retrait", prenom="Eleve", role=Utilisateur.Role.ELEVE,
        )
        self.club = Club.objects.create(
            nom="Club Retrait Test", description="Test", categorie=Club.Categorie.AUTRE,
            objectifs="Test", nombre_max_membres=10, statut='actif',
        )
        self.annee = AnneeScolaire.objects.create(
            libelle="2025-2026", date_debut="2025-09-01", date_fin="2026-07-31", est_active=True,
        )
        self.inscription = Inscription.objects.create(
            eleve=self.eleve, club=self.club, annee_scolaire=self.annee,
            statut=Inscription.Statut.VALIDEE,
        )

    def test_retirer_membre_reussi(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('club-retirer-membre', args=[self.club.id])
        response = self.client.post(url, {"eleve_id": self.eleve.id}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.inscription.refresh_from_db()
        self.assertEqual(self.inscription.statut, Inscription.Statut.ANNULEE)
        self.assertEqual(self.club.nombre_membres_actuels, 0)

    def test_retirer_membre_non_inscrit_echoue(self):
        autre_eleve = Utilisateur.objects.create_user(
            email="autreeleve@lycee.cm", password="motdepasse123",
            nom="Autre", prenom="Eleve", role=Utilisateur.Role.ELEVE,
        )
        self.client.force_authenticate(user=self.admin)
        url = reverse('club-retirer-membre', args=[self.club.id])
        response = self.client.post(url, {"eleve_id": autre_eleve.id}, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_eleve_ne_peut_pas_retirer_un_membre(self):
        self.client.force_authenticate(user=self.eleve)
        url = reverse('club-retirer-membre', args=[self.club.id])
        response = self.client.post(url, {"eleve_id": self.eleve.id}, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)