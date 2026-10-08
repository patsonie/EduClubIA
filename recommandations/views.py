# Imports : vues DRF, modèles, moteur de recommandation et pipeline d'entraînement IA.
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


# === Recommandations de clubs : /api/recommandations/ ===
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

        # Consultation pour un autre élève : réservée aux gestionnaires et aux parents de cet élève.
        eleve_id = request.query_params.get('eleve_id')
        if eleve_id:
            from utilisateurs.models import Utilisateur
            try:
                eleve_cible = Utilisateur.objects.get(id=eleve_id, role='eleve')
            except Utilisateur.DoesNotExist:
                return Response({"error": "Élève introuvable."}, status=status.HTTP_404_NOT_FOUND)

            est_gestionnaire = request.user.role in ['administrateur', 'proviseur']
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

        # Calcul hybride (contenu + collaboratif + centres d'intérêt), voir services.py.
        resultats = calculer_recommandations_hybrides(eleve)

        recommandations_sauvegardees = []
        # Supprime les recommandations obsolètes de cet élève (club plus recommandé / plus actif).
        Recommandation.objects.filter(eleve=eleve).exclude(
            club_id__in=[r["club"].id for r in resultats]
        ).delete()
        # Sauvegarde ou mise à jour de chaque recommandation calculée.
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
    
# Permission : administrateur uniquement.
class EstAdministrateur(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'administrateur'


# === Réentraînement des modèles IA depuis l'interface ===
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
        if type_declenchement not in HistoriqueEntrainement.TypeDeclenchement.values:
            return Response(
                {"error": f"type_declenchement invalide. Valeurs : {HistoriqueEntrainement.TypeDeclenchement.values}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        debut = time.time()
        resultats = {}

        # Entraînement puis validation de chacun des trois modèles.
        try:
            resultats['content_based'] = entrainer_modele_content_based()
            resultats['validation_content_based'] = valider_modele_content_based()

            resultats['collaboratif'] = entrainer_modele_collaboratif()
            resultats['validation_collaboratif'] = valider_modele_collaboratif()

            resultats['participation'] = entrainer_modele_participation()
            resultats['validation_participation'] = valider_modele_participation()

            duree = round(time.time() - debut, 2)

            # Statut global : échec seulement si aucun modèle n'a pu être entraîné.
            entrainements = [resultats['content_based'], resultats['collaboratif'], resultats['participation']]
            echecs = [k for k in ('content_based', 'collaboratif', 'participation')
                      if resultats[k].get('statut') == 'echec']
            statut = (
                HistoriqueEntrainement.Statut.ECHEC if len(echecs) == len(entrainements)
                else HistoriqueEntrainement.Statut.SUCCES
            )
            historique = HistoriqueEntrainement.objects.create(
                type_declenchement=type_declenchement,
                statut=statut,
                metriques=json.dumps(resultats, default=str),
                message_erreur=(f"Modèles non entraînés : {', '.join(echecs)}" if echecs else None),
                declenche_par=request.user if request.user.is_authenticated else None,
                duree_secondes=duree,
            )

            return Response({
                "message": (
                    "Entraînement des modèles IA terminé avec succès."
                    if not echecs else f"Entraînement terminé, modèles non entraînés (données insuffisantes) : {', '.join(echecs)}."
                ),
                "modeles_non_entraines": echecs,
                "duree_secondes": duree,
                "resultats": resultats,
                "historique_id": historique.id,
            }, status=status.HTTP_200_OK)

        # Erreur inattendue : trace dans les journaux et dans l'historique.
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


# === Les 20 derniers entraînements ===
class HistoriqueEntrainementView(generics.ListAPIView):
    """GET /api/ia/historique-entrainement/ — historique des exécutions du pipeline."""
    serializer_class = HistoriqueEntrainementSerializer
    permission_classes = [EstAdministrateur]
    queryset = HistoriqueEntrainement.objects.select_related('declenche_par').all()
    pagination_class = None

    def get_queryset(self):
        return super().get_queryset()[:20]
