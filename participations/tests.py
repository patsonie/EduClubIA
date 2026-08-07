from datetime import date, time
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from utilisateurs.models import Utilisateur
from clubs.models import Club
from activites.models import Activite
from annees_scolaires.models import AnneeScolaire
from inscriptions.models import Inscription
from .models import Participation


class ParticipationSetupMixin:
    """Prépare les objets communs à tous les tests de cette app."""

    def creer_contexte(self):
        eleve = Utilisateur.objects.create_user(
            email="eleve8@lycee.cm", password="motdepasse123",
            nom="Zang", prenom="Bella", role=Utilisateur.Role.ELEVE,
        )
        admin = Utilisateur.objects.create_user(
            email="admin6@lycee.cm", password="motdepasse123",
            nom="Admin", prenom="Six", role=Utilisateur.Role.ADMINISTRATEUR,
        )
        club = Club.objects.create(
            nom="Club Chant", description="Club de chant",
            categorie=Club.Categorie.ARTISTIQUE, objectifs="Chanter", nombre_max_membres=10,
        )
        annee = AnneeScolaire.objects.create(
            libelle="2025-2026", date_debut="2025-09-01", date_fin="2026-07-31", est_active=True,
        )
        inscription = Inscription.objects.create(
            eleve=eleve, club=club, annee_scolaire=annee, statut=Inscription.Statut.VALIDEE,
        )
        activite = Activite.objects.create(
            club=club, titre="Concert de fin d'année", description="Test",
            date=date(2026, 6, 1), heure=time(18, 0), lieu="Salle des fêtes", budget=0,
        )
        return eleve, admin, inscription, activite


class ParticipationModelTest(ParticipationSetupMixin, APITestCase):
    """Test 1 : création d'une participation et contrainte d'unicité."""

    def test_creation_participation(self):
        _, _, inscription, activite = self.creer_contexte()
        participation = Participation.objects.create(
            inscription=inscription, activite=activite, statut=Participation.Statut.PRESENT,
        )
        self.assertEqual(participation.statut, "present")


class ParticipationAPITest(ParticipationSetupMixin, APITestCase):
    """Tests 2 et 3 : enregistrement via API et calcul du rapport individuel."""

    def test_enregistrement_participation_par_admin(self):
        eleve, admin, inscription, activite = self.creer_contexte()
        self.client.force_authenticate(user=admin)
        url = reverse('participation-list')
        data = {"inscription": inscription.id, "activite": activite.id, "statut": "present"}
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Participation.objects.filter(inscription=inscription, activite=activite).exists())

    def test_rapport_individuel(self):
        eleve, admin, inscription, activite = self.creer_contexte()
        Participation.objects.create(
            inscription=inscription, activite=activite, statut=Participation.Statut.PRESENT,
        )
        self.client.force_authenticate(user=admin)
        url = reverse('participation-rapport-individuel')
        response = self.client.get(url, {'eleve_id': eleve.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_activites'], 1)
        self.assertEqual(response.data['taux_participation'], 100.0)