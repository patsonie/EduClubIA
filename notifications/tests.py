from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from utilisateurs.models import Utilisateur
from clubs.models import Club
from annees_scolaires.models import AnneeScolaire
from inscriptions.models import Inscription
from .models import Notification
from .services import notifier_validation_inscription


class NotificationServiceTest(APITestCase):
    """Test 1 : la validation d'une inscription déclenche bien une notification."""

    def setUp(self):
        self.eleve = Utilisateur.objects.create_user(
            email="eleve15@lycee.cm", password="motdepasse123",
            nom="Owona", prenom="Cedric", role=Utilisateur.Role.ELEVE,
        )
        self.club = Club.objects.create(
            nom="Club Echecs", description="Club d'échecs",
            categorie=Club.Categorie.SCIENTIFIQUE, objectifs="Jouer aux échecs",
            nombre_max_membres=15,
        )
        self.annee = AnneeScolaire.objects.create(
            libelle="2025-2026", date_debut="2025-09-01", date_fin="2026-07-31", est_active=True,
        )
        self.inscription = Inscription.objects.create(
            eleve=self.eleve, club=self.club, annee_scolaire=self.annee,
        )

    def test_notification_creee_apres_validation(self):
        notifier_validation_inscription(self.inscription)
        self.assertTrue(
            Notification.objects.filter(
                destinataire=self.eleve,
                type_notification=Notification.TypeNotification.VALIDATION_INSCRIPTION,
            ).exists()
        )


class NotificationAPITest(APITestCase):
    """Tests 2 et 3 : consultation et marquage comme lu via l'API."""

    def setUp(self):
        self.eleve = Utilisateur.objects.create_user(
            email="eleve16@lycee.cm", password="motdepasse123",
            nom="Bikoro", prenom="Sonia", role=Utilisateur.Role.ELEVE,
        )
        self.notification = Notification.objects.create(
            destinataire=self.eleve,
            type_notification=Notification.TypeNotification.AUTRE,
            titre="Test",
            message="Ceci est un test.",
        )

    def test_liste_notifications_utilisateur(self):
        self.client.force_authenticate(user=self.eleve)
        url = reverse('notification-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_marquer_notification_comme_lue(self):
        self.client.force_authenticate(user=self.eleve)
        url = reverse('notification-marquer-lu', args=[self.notification.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.lu)