from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Participation
from .serializers import ParticipationSerializer, RapportIndividuelSerializer
from .permissions import EstGestionnaireOuLectureSeule
from notifications.services import notifier_parents_absence


class ParticipationViewSet(viewsets.ModelViewSet):
    """
    CRUD des participations (présences).
    Un élève voit uniquement ses propres participations ; gestionnaires voient tout.
    Filtre : ?activite=1&statut=present&inscription=2
    Action : GET /api/participations/rapport_individuel/?eleve_id=3
    """
    serializer_class = ParticipationSerializer
    permission_classes = [EstGestionnaireOuLectureSeule]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['activite', 'statut', 'inscription', 'inscription__eleve']
    ordering_fields = ['date_enregistrement']


    def get_queryset(self):
        user = self.request.user
        if user.role in ['administrateur', 'proviseur', 'encadreur']:
            return Participation.objects.all()
        if user.role == 'parent':
            return Participation.objects.filter(inscription__eleve__in=user.enfants)
        return Participation.objects.filter(inscription__eleve=user)

    def perform_create(self, serializer):
        participation = serializer.save(enregistre_par=self.request.user)
        notifier_parents_absence(participation)

    @action(detail=False, methods=['get'])
    def rapport_individuel(self, request):
        """
        GET /api/participations/rapport_individuel/?eleve_id=3
        Calcule le taux de participation d'un élève sur l'ensemble de ses activités.
        """
        eleve_id = request.query_params.get('eleve_id')
        if not eleve_id:
            return Response(
                {"error": "Le paramètre eleve_id est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
            
    @action(detail=False, methods=['post'])
    def enregistrer_lot(self, request):
        """
        POST /api/participations/enregistrer_lot/
        body: {"activite": <id>, "presences": [{"inscription": <id>, "statut": "present"}, ...]}
        Crée ou met à jour en une seule requête les présences de toute une activité.
        """
        activite_id = request.data.get('activite')
        presences = request.data.get('presences', [])

        resultats = []
        for entree in presences:
            participation, _ = Participation.objects.update_or_create(
                inscription_id=entree['inscription'],
                activite_id=activite_id,
                defaults={'statut': entree['statut'], 'enregistre_par': request.user},
            )
            resultats.append(participation.id)

        return Response(
            {"message": f"{len(resultats)} présence(s) enregistrée(s).", "ids": resultats},
            status=status.HTTP_200_OK,
        )

        participations = Participation.objects.filter(inscription__eleve_id=eleve_id)
        total = participations.count()
        presences = participations.filter(statut=Participation.Statut.PRESENT).count()
        taux = round((presences / total * 100), 2) if total > 0 else 0.0

        premiere = participations.first()
        eleve_nom = premiere.inscription.eleve.nom_complet if premiere else ""

        data = {
            "eleve_id": int(eleve_id),
            "eleve_nom": eleve_nom,
            "total_activites": total,
            "total_presences": presences,
            "taux_participation": taux,
        }
        serializer = RapportIndividuelSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)