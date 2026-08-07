from datetime import date, time
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from utilisateurs.models import Utilisateur
from clubs.models import Club
from activites.models import Activite
from annees_scolaires.models import AnneeScolaire
from inscriptions.models import Inscription
from participations.models import Participation
from .services import calculer_risque_desengagement, determiner_niveau_risque, predire_nombre_participants


class RisqueDesengagementTest(APITestCase):
    """Test 1 : un élève sans participation récente a un risque élevé."""

    def setUp(self):
        self.eleve = Utilisateur.objects.create_user(
            email="eleve12@lycee.cm", password="motdepasse123",
            nom="Essomba", prenom="Rita", role=Utilisateur.Role.ELEVE,
        )
        self.club = Club.objects.create(
            nom="Club Debat", description="Club de débat",
            categorie=Club.Categorie.CULTUREL, objectifs="Débattre",
            nombre_max_membres=15,
        )
        self.annee = AnneeScolaire.objects.create(
            libelle="2025-2026", date_debut="2025-09-01", date_fin="2026-07-31", est_active=True,
        )
        self.inscription = Inscription.objects.create(
            eleve=self.eleve, club=self.club, annee_scolaire=self.annee,
            statut=Inscription.Statut.VALIDEE,
        )

    def test_eleve_sans_participation_a_risque_neutre(self):
        score = calculer_risque_desengagement(self.inscription)
        self.assertEqual(score, 30.0)
        self.assertEqual(determiner_niveau_risque(score), 'moyen')

    def test_eleve_toujours_absent_a_risque_eleve(self):
        for i in range(5):
            activite = Activite.objects.create(
                club=self.club, titre=f"Séance {i}", description="Test",
                date=date(2026, 1, i + 1), heure=time(15, 0), lieu="Salle A", budget=0,
            )
            Participation.objects.create(
                inscription=self.inscription, activite=activite, statut=Participation.Statut.ABSENT,
            )

        score = calculer_risque_desengagement(self.inscription)
        self.assertGreaterEqual(score, 60)
        self.assertEqual(determiner_niveau_risque(score), 'eleve')


class PredictionParticipationTest(APITestCase):
    """Test 2 : prédiction basée sur la moyenne des activités passées."""

    def setUp(self):
        self.club = Club.objects.create(
            nom="Club Photo", description="Club de photographie",
            categorie=Club.Categorie.ARTISTIQUE, objectifs="Photographier",
            nombre_max_membres=20,
        )
        self.eleve = Utilisateur.objects.create_user(
            email="eleve13@lycee.cm", password="motdepasse123",
            nom="Biloa", prenom="Serge", role=Utilisateur.Role.ELEVE,
        )
        self.annee = AnneeScolaire.objects.create(
            libelle="2025-2026", date_debut="2025-09-01", date_fin="2026-07-31", est_active=True,
        )
        self.inscription = Inscription.objects.create(
            eleve=self.eleve, club=self.club, annee_scolaire=self.annee,
            statut=Inscription.Statut.VALIDEE,
        )

    def test_prediction_sans_historique_se_base_sur_membres_actuels(self):
        activite_future = Activite.objects.create(
            club=self.club, titre="Sortie photo", description="Test",
            date=date(2026, 12, 1), heure=time(10, 0), lieu="Parc", budget=0,
        )
        prediction = predire_nombre_participants(activite_future)
        self.assertGreaterEqual(prediction, 1)


class RisqueDesengagementAPITest(APITestCase):
    """Test 3 : accès restreint aux gestionnaires pour l'API de risque de désengagement."""

    def setUp(self):
        self.eleve = Utilisateur.objects.create_user(
            email="eleve14@lycee.cm", password="motdepasse123",
            nom="Ndjock", prenom="Léa", role=Utilisateur.Role.ELEVE,
        )
        self.admin = Utilisateur.objects.create_user(
            email="admin7@lycee.cm", password="motdepasse123",
            nom="Admin", prenom="Sept", role=Utilisateur.Role.ADMINISTRATEUR,
        )

    def test_eleve_ne_peut_pas_acceder_aux_risques(self):
        self.client.force_authenticate(user=self.eleve)
        url = reverse('risques-desengagement')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_peut_acceder_aux_risques(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('risques-desengagement')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)