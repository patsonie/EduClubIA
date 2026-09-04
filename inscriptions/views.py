from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from .models import Inscription, HistoriqueInscription
from .serializers import InscriptionSerializer
from .permissions import EstProprietaireOuGestionnaire
from notifications.services import (
    notifier_validation_inscription, notifier_refus_inscription,
    notifier_parents_validation_inscription,
)


class InscriptionViewSet(viewsets.ModelViewSet):
    """
    CRUD des inscriptions.
    Un élève voit uniquement ses inscriptions ; les gestionnaires voient tout.
    Filtre : ?club=1&statut=en_attente&annee_scolaire=1
    Actions : POST /api/inscriptions/{id}/valider/, /refuser/, /se_desinscrire/
    """
    serializer_class = InscriptionSerializer
    permission_classes = [EstProprietaireOuGestionnaire]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['club', 'statut', 'annee_scolaire', 'eleve']
    ordering_fields = ['date_inscription']

    def get_queryset(self):
        user = self.request.user
        if user.role in ['administrateur', 'proviseur', 'encadreur']:
            return Inscription.objects.all()
        if user.role == 'parent':
            return Inscription.objects.filter(eleve__in=user.enfants)
        return Inscription.objects.filter(eleve=user)
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        return context

    def perform_create(self, serializer):
        # Un élève s'inscrit toujours lui-même. Les gestionnaires peuvent agir
        # pour le compte d'un élève ; les parents ne peuvent pas créer de lien.
        if self.request.user.role == 'eleve':
            inscription = serializer.save(eleve=self.request.user)
        elif self.request.user.role in ['administrateur', 'proviseur', 'encadreur']:
            inscription = serializer.save()
        else:
            raise PermissionDenied("Vous n'êtes pas autorisé à créer une inscription.")

        HistoriqueInscription.objects.create(
            inscription=inscription,
            ancien_statut=None,
            nouveau_statut=inscription.statut,
            modifie_par=self.request.user,
            commentaire="Création de l'inscription",
        )

    def _changer_statut(self, request, pk, nouveau_statut, commentaire):
        inscription = self.get_object()
        ancien_statut = inscription.statut
        inscription.statut = nouveau_statut
        inscription.date_traitement = timezone.now()
        inscription.traite_par = request.user
        inscription.save()

        HistoriqueInscription.objects.create(
            inscription=inscription,
            ancien_statut=ancien_statut,
            nouveau_statut=nouveau_statut,
            modifie_par=request.user,
            commentaire=commentaire,
        )
        
        if nouveau_statut == Inscription.Statut.VALIDEE:
            notifier_validation_inscription(inscription)
            notifier_parents_validation_inscription(inscription)
        elif nouveau_statut == Inscription.Statut.REFUSEE:
            notifier_refus_inscription(inscription)
        return Response(InscriptionSerializer(inscription).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        """Réservé aux gestionnaires (vérifié via has_object_permission)."""
        if request.user.role not in ['administrateur', 'proviseur', 'encadreur']:
            raise PermissionDenied("Seuls les gestionnaires peuvent valider une inscription.")
        return self._changer_statut(request, pk, Inscription.Statut.VALIDEE, "Inscription validée")

    @action(detail=True, methods=['post'])
    def refuser(self, request, pk=None):
        if request.user.role not in ['administrateur', 'proviseur', 'encadreur']:
            raise PermissionDenied("Seuls les gestionnaires peuvent refuser une inscription.")
        return self._changer_statut(request, pk, Inscription.Statut.REFUSEE, "Inscription refusée")

    @action(detail=True, methods=['post'])
    def se_desinscrire(self, request, pk=None):
        """L'élève peut se désinscrire lui-même de son propre club."""
        inscription = self.get_object()
        if (
            request.user.role not in ['administrateur', 'proviseur', 'encadreur']
            and inscription.eleve_id != request.user.id
        ):
            raise PermissionDenied("Vous ne pouvez désinscrire que votre propre compte.")
        return self._changer_statut(request, pk, Inscription.Statut.ANNULEE, "Désinscription")

    def update(self, request, *args, **kwargs):
        if request.user.role not in ['administrateur', 'proviseur', 'encadreur']:
            raise PermissionDenied("Utilisez l'action de désinscription pour annuler votre inscription.")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if request.user.role not in ['administrateur', 'proviseur', 'encadreur']:
            raise PermissionDenied("Vous n'êtes pas autorisé à supprimer une inscription.")
        return super().destroy(request, *args, **kwargs)
