from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
import django_filters
from .models import Activite, HistoriqueActivite
from .serializers import ActiviteSerializer, ActiviteListeSerializer
from .permissions import EstEncadreurOuAdminOuLectureSeule
from rest_framework.exceptions import PermissionDenied
from utilisateurs.perimetre import est_gestion_globale, peut_gerer_club
from notifications.services import notifier_nouvelle_activite, notifier_parents_nouvelle_activite


class ActiviteFilterSet(django_filters.FilterSet):
    """
    FilterSet personnalisé : le filtre 'club' utilise un NumberFilter plutôt que
    le ModelChoiceFilter généré automatiquement par django-filter pour les FK,
    afin qu'un ID de club inexistant renvoie simplement une liste vide (200)
    plutôt qu'une erreur 400 "choix invalide".
    """
    club = django_filters.NumberFilter(field_name='club_id')

    class Meta:
        model = Activite
        fields = ['club', 'statut', 'responsable']


class ActiviteViewSet(viewsets.ModelViewSet):
   
    queryset = Activite.objects.select_related('club', 'responsable').all()
    permission_classes = [EstEncadreurOuAdminOuLectureSeule]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ActiviteFilterSet
    search_fields = ['titre', 'description', 'lieu']
    ordering_fields = ['date', 'heure', 'budget']

    def get_serializer_class(self):
        if self.action == 'list':
            return ActiviteListeSerializer
        return ActiviteSerializer

    def perform_create(self, serializer):
        if not peut_gerer_club(self.request.user, serializer.validated_data['club']):
            raise PermissionDenied("Vous ne gérez pas ce club.")
        activite = serializer.save()
        HistoriqueActivite.objects.create(
            activite=activite,
            ancien_statut=None,
            nouveau_statut=activite.statut,
            modifie_par=self.request.user,
            commentaire="Création de l'activité",
        )

        notifier_nouvelle_activite(activite)
        notifier_parents_nouvelle_activite(activite)

    def perform_update(self, serializer):
        ancien_statut = serializer.instance.statut
        nouveau_club = serializer.validated_data.get('club')
        if nouveau_club and not peut_gerer_club(self.request.user, nouveau_club):
            raise PermissionDenied("Vous ne gérez pas ce club.")
        activite = serializer.save()
        if ancien_statut != activite.statut:
            HistoriqueActivite.objects.create(
                activite=activite,
                ancien_statut=ancien_statut,
                nouveau_statut=activite.statut,
                modifie_par=self.request.user,
                commentaire="Modification du statut",
            )

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        """Validation rapide d'une activité planifiée (administrateur / responsable pédagogique)."""
        if not est_gestion_globale(request.user):
            raise PermissionDenied("Seul un responsable pédagogique ou un administrateur peut valider une activité.")
        activite = self.get_object()
        ancien_statut = activite.statut
        activite.statut = Activite.Statut.VALIDEE
        activite.save()

        HistoriqueActivite.objects.create(
            activite=activite,
            ancien_statut=ancien_statut,
            nouveau_statut=activite.statut,
            modifie_par=request.user,
            commentaire="Validation de l'activité",
        )

        return Response(ActiviteSerializer(activite, context={'request': request}).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def participants_attendus(self, request, pk=None):
        """
        Liste les élèves inscrits (validés) au club organisateur, avec leur statut
        de présence déjà enregistré pour cette activité (s'il existe).
        """
        from inscriptions.models import Inscription
        from participations.models import Participation

        activite = self.get_object()
        inscriptions = Inscription.objects.filter(
            club=activite.club, statut=Inscription.Statut.VALIDEE
        ).select_related('eleve')

        participations_existantes = {
            p.inscription_id: p for p in Participation.objects.filter(activite=activite)
        }

        resultats = []
        for inscription in inscriptions:
            participation = participations_existantes.get(inscription.id)
            resultats.append({
                "inscription_id": inscription.id,
                "eleve_nom": inscription.eleve.nom_complet,
                "classe": inscription.eleve.classe,
                "participation_id": participation.id if participation else None,
                "statut": participation.statut if participation else None,
            })

        return Response(resultats, status=status.HTTP_200_OK)