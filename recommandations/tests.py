from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from utilisateurs.models import Utilisateur
from clubs.models import Club
from .services import calculer_recommandations_content_based
from .models import Recommandation


class MoteurRecommandationTest(APITestCase):
    """Test 1 : le moteur content-based retourne des scores cohérents."""

    def setUp(self):
        self.eleve = Utilisateur.objects.create_user(
            email="eleve9@lycee.cm", password="motdepasse123",
            nom="Talla", prenom="Yves", role=Utilisateur.Role.ELEVE,
            centres_interet="informatique, robotique, programmation",
        )
        self.club_tech = Club.objects.create(
            nom="Club Robotique", description="Construction et programmation de robots",
            categorie=Club.Categorie.TECHNOLOGIQUE,
            objectifs="Initier les élèves à la robotique et à la programmation",
            nombre_max_membres=20, statut='actif',
        )
        self.club_sport = Club.objects.create(
            nom="Club Football", description="Entraînement et matchs de football",
            categorie=Club.Categorie.SPORTIF,
            objectifs="Pratiquer le sport collectif",
            nombre_max_membres=20, statut='actif',
        )

    def test_club_technologique_mieux_score_que_club_sportif(self):
        resultats = calculer_recommandations_content_based(self.eleve)
        scores = {r["club"].id: r["score"] for r in resultats}

        self.assertIn(self.club_tech.id, scores)
        self.assertIn(self.club_sport.id, scores)
        self.assertGreater(scores[self.club_tech.id], scores[self.club_sport.id])

    def test_eleve_sans_profil_ne_genere_pas_de_recommandation(self):
        eleve_vide = Utilisateur.objects.create_user(
            email="eleve10@lycee.cm", password="motdepasse123",
            nom="Sans", prenom="Profil", role=Utilisateur.Role.ELEVE,
        )
        resultats = calculer_recommandations_content_based(eleve_vide)
        self.assertEqual(resultats, [])


class RecommandationAPITest(APITestCase):
    """Test 2 : l'API calcule et sauvegarde les recommandations en base."""

    def setUp(self):
        self.eleve = Utilisateur.objects.create_user(
            email="eleve11@lycee.cm", password="motdepasse123",
            nom="Mvondo", prenom="Ida", role=Utilisateur.Role.ELEVE,
            centres_interet="théâtre, musique, chant",
        )
        Club.objects.create(
            nom="Club Théâtre 3", description="Ateliers de théâtre et d'improvisation",
            categorie=Club.Categorie.ARTISTIQUE,
            objectifs="Développer l'expression théâtrale",
            nombre_max_membres=15, statut='actif',
        )

    def test_recommandations_sauvegardees_en_base(self):
        self.client.force_authenticate(user=self.eleve)
        url = reverse('recommandation-liste')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0)
        self.assertTrue(Recommandation.objects.filter(eleve=self.eleve).exists())