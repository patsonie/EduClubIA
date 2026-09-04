from rest_framework import status, permissions, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Recommandation
from .serializers import RecommandationSerializer
from .services import calculer_recommandations_content_based
from .services import calculer_recommandations_hybrides
import json
import logging
import time
from django.utils import timezone
from .models import HistoriqueEntrainement
from .serializers import HistoriqueEntrainementSerializer
from .ml_pipeline import (
    entrainer_modele_content_based, valider_modele_content_based,
    entrainer_modele_collaboratif, valider_modele_collaboratif,
)
from analytics.ml_pipeline import entrainer_modele_participation, valider_modele_participation

logger = logging.getLogger(__name__)


class RecommandationListeView(APIView):
    """
    GET /api/recommandations/
    Calcule (ou recalcule) les recommandations content-based pour l'élève connecté,
    les stocke en base, et retourne la liste triée par score décroissant.

    GET /api/recommandations/?eleve_id=5  (réservé aux gestionnaires, pour consulter
    les recommandations d'un élève donné)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        eleve = request.user

        eleve_id = request.query_params.get('eleve_id')
        if eleve_id:
            from utilisateurs.models import Utilisateur
            try:
                eleve_cible = Utilisateur.objects.get(id=eleve_id, role='eleve')
            except Utilisateur.DoesNotExist:
                return Response({"error": "Élève introuvable."}, status=status.HTTP_404_NOT_FOUND)

            est_gestionnaire = request.user.role in ['administrateur', 'proviseur', 'encadreur']
            est_parent_de_cet_eleve = (
                request.user.role == 'parent'
                and request.user.enfants.filter(id=eleve_cible.id).exists()
            )

            if not (est_gestionnaire or est_parent_de_cet_eleve):
                return Response(
                    {"error": "Vous n'êtes pas autorisé à consulter les recommandations de cet élève."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            eleve = eleve_cible
        elif eleve.role != 'eleve':
            return Response(
                {"error": "Le paramètre eleve_id est requis pour ce rôle."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        resultats = calculer_recommandations_hybrides(eleve)

        recommandations_sauvegardees = []
        for resultat in resultats:
            recommandation, _ = Recommandation.objects.update_or_create(
                eleve=eleve,
                club=resultat["club"],
                defaults={
                    "score": resultat["score"],
                    "explication": resultat["explication"],
                },
            )
            recommandations_sauvegardees.append(recommandation)

        serializer = RecommandationSerializer(recommandations_sauvegardees, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class EstAdministrateur(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'administrateur'


class ReentrainementIAView(APIView):
    """
    POST /api/ia/reentrainement/  body optionnel: {"type_declenchement": "manuel"}
    Déclenche le pipeline complet : entraînement puis validation, pour les
    3 modèles (content-based, collaboratif, prédiction de participation).
    Réservé aux administrateurs.
    """
    permission_classes = [EstAdministrateur]

    def post(self, request):
        type_declenchement = request.data.get('type_declenchement', 'manuel')
        debut = time.time()
        resultats = {}

        try:
            resultats['content_based'] = entrainer_modele_content_based()
            resultats['validation_content_based'] = valider_modele_content_based()

            resultats['collaboratif'] = entrainer_modele_collaboratif()
            resultats['validation_collaboratif'] = valider_modele_collaboratif()

            resultats['participation'] = entrainer_modele_participation()
            resultats['validation_participation'] = valider_modele_participation()

            duree = round(time.time() - debut, 2)

            historique = HistoriqueEntrainement.objects.create(
                type_declenchement=type_declenchement,
                statut=HistoriqueEntrainement.Statut.SUCCES,
                metriques=json.dumps(resultats, default=str),
                declenche_par=request.user if request.user.is_authenticated else None,
                duree_secondes=duree,
            )

            return Response({
                "message": "Entraînement des modèles IA terminé avec succès.",
                "duree_secondes": duree,
                "resultats": resultats,
                "historique_id": historique.id,
            }, status=status.HTTP_200_OK)

        except Exception:
            logger.exception("Échec de l'entraînement des modèles IA")
            duree = round(time.time() - debut, 2)
            HistoriqueEntrainement.objects.create(
                type_declenchement=type_declenchement,
                statut=HistoriqueEntrainement.Statut.ECHEC,
                message_erreur="Erreur interne lors de l'entraînement. Consultez les journaux serveur.",
                declenche_par=request.user if request.user.is_authenticated else None,
                duree_secondes=duree,
            )
            return Response(
                {"error": "Échec de l'entraînement. Consultez les journaux serveur."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class HistoriqueEntrainementView(generics.ListAPIView):
    """GET /api/ia/historique-entrainement/ — historique des exécutions du pipeline."""
    serializer_class = HistoriqueEntrainementSerializer
    permission_classes = [EstAdministrateur]
    queryset = HistoriqueEntrainement.objects.all()[:20]
