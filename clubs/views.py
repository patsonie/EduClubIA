from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Club
from .serializers import ClubSerializer, ClubListeSerializer
from .permissions import EstAdminOuProviseurOuLectureSeule
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status


class ClubViewSet(viewsets.ModelViewSet):
    """
    ViewSet complet pour les clubs : list, retrieve, create, update, destroy.
    Recherche : ?search=robotique
    Filtre : ?categorie=scientifique&statut=actif
    """
    queryset = Club.objects.all()
    permission_classes = [EstAdminOuProviseurOuLectureSeule]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['categorie', 'statut', 'responsable']
    search_fields = ['nom', 'description', 'objectifs']
    ordering_fields = ['nom', 'date_creation', 'nombre_max_membres']

    def get_serializer_class(self):
        if self.action == 'list':
            return ClubListeSerializer
        return ClubSerializer
    
    @action(detail=True, methods=['get'])
    def membres(self, request, pk=None):
        """GET /api/clubs/{id}/membres/ — liste des élèves inscrits validés dans ce club."""
        from inscriptions.models import Inscription
        club = self.get_object()
        inscriptions = Inscription.objects.filter(
            club=club, statut=Inscription.Statut.VALIDEE
        ).select_related('eleve')

        membres = [
            {
                "id": i.eleve.id,
                "nom_complet": i.eleve.nom_complet,
                "classe": i.eleve.classe,
                "date_inscription": i.date_inscription,
            }
            for i in inscriptions
        ]
        return Response(membres, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def statistiques(self, request, pk=None):
        """GET /api/clubs/{id}/statistiques/ — statistiques agrégées du club."""
        from activites.models import Activite
        from participations.models import Participation
        
    @action(detail=True, methods=['post'])
    def retirer_membre(self, request, pk=None):
        """POST /api/clubs/{id}/retirer_membre/  body: {"eleve_id": <id>}"""
        from inscriptions.models import Inscription

        club = self.get_object()
        eleve_id = request.data.get('eleve_id')

        inscription = Inscription.objects.filter(
            club=club, eleve_id=eleve_id, statut=Inscription.Statut.VALIDEE
        ).first()

        if not inscription:
            return Response({"error": "Ce membre n'est pas inscrit à ce club."}, status=status.HTTP_404_NOT_FOUND)

        inscription.statut = Inscription.Statut.ANNULEE
        inscription.save()

        from inscriptions.models import HistoriqueInscription
        HistoriqueInscription.objects.create(
            inscription=inscription, ancien_statut=Inscription.Statut.VALIDEE,
            nouveau_statut=Inscription.Statut.ANNULEE, modifie_par=request.user,
            commentaire="Retiré du club par un gestionnaire",
        )

        return Response({"message": "Membre retiré du club."}, status=status.HTTP_200_OK)

        club = self.get_object()
        activites = Activite.objects.filter(club=club)
        participations = Participation.objects.filter(inscription__club=club)
        total_participations = participations.count()
        presences = participations.filter(statut='present').count()
        taux_moyen = round((presences / total_participations * 100), 1) if total_participations else 0

        return Response({
            "nombre_activites": activites.count(),
            "activites_terminees": activites.filter(statut=Activite.Statut.TERMINEE).count(),
            "activites_a_venir": activites.filter(statut__in=['planifiee', 'validee']).count(),
            "taux_participation_moyen": taux_moyen,
            "nombre_membres": club.nombre_membres_actuels,
        }, status=status.HTTP_200_OK)