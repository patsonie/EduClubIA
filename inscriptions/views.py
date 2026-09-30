from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from clubs.models import Club
from django_filters.rest_framework import DjangoFilterBackend
from .models import Inscription, HistoriqueInscription
from .serializers import InscriptionSerializer
from .permissions import EstProprietaireOuGestionnaire
from utilisateurs.perimetre import est_gestion_globale, clubs_geres, peut_gerer_club
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
        base = Inscription.objects.select_related('eleve', 'club', 'annee_scolaire')
        if est_gestion_globale(user):
            return base
        if user.role == 'encadreur':
            return base.filter(club__in=clubs_geres(user))
        if user.role == 'parent':
            return base.filter(eleve__in=user.enfants)
        return base.filter(eleve=user)

    def perform_create(self, serializer):
        # Un élève s'inscrit toujours lui-même. Les gestionnaires peuvent agir
        # pour le compte d'un élève ; les parents ne peuvent pas créer de lien.
        user = self.request.user
        if user.role == 'eleve':
            eleve = user
        elif user.role in ['administrateur', 'proviseur', 'encadreur']:
            if not peut_gerer_club(user, serializer.validated_data['club']):
                raise PermissionDenied("Vous ne gérez pas ce club.")
            eleve = serializer.validated_data.get('eleve') or user
        else:
            raise PermissionDenied("Vous n'êtes pas autorisé à créer une inscription.")

        with transaction.atomic():
            # Verrou sur le club : la vérification de capacité et la création sont sérialisées.
            club = Club.objects.select_for_update().get(pk=serializer.validated_data['club'].pk)
            if club.places_disponibles <= 0:
                raise ValidationError({"club": f"Le club {club.nom} a atteint son nombre maximal de membres."})

            # Une ancienne inscription annulée est réactivée (contrainte d'unicité eleve/club/année).
            ancienne = Inscription.objects.filter(
                eleve=eleve, club=club,
                annee_scolaire=serializer.validated_data['annee_scolaire'],
                statut=Inscription.Statut.ANNULEE,
            ).first()
            if ancienne:
                ancienne.statut = Inscription.Statut.EN_ATTENTE
                ancienne.date_traitement = None
                ancienne.traite_par = None
                ancienne.save()
                serializer.instance = ancienne
                inscription = ancienne
            else:
                inscription = serializer.save(eleve=eleve)

        HistoriqueInscription.objects.create(
            inscription=inscription,
            ancien_statut=None,
            nouveau_statut=inscription.statut,
            modifie_par=self.request.user,
            commentaire="Création de l'inscription",
        )

    TRANSITIONS = {
        Inscription.Statut.VALIDEE: [Inscription.Statut.EN_ATTENTE],
        Inscription.Statut.REFUSEE: [Inscription.Statut.EN_ATTENTE],
        Inscription.Statut.ANNULEE: [Inscription.Statut.EN_ATTENTE, Inscription.Statut.VALIDEE],
    }

    @transaction.atomic
    def _changer_statut(self, request, pk, nouveau_statut, commentaire):
        inscription = self.get_object()
        inscription = Inscription.objects.select_for_update().get(pk=inscription.pk)
        ancien_statut = inscription.statut
        if ancien_statut not in self.TRANSITIONS.get(nouveau_statut, []):
            raise ValidationError(
                {"statut": f"Transition impossible : {ancien_statut} → {nouveau_statut}."}
            )
        if nouveau_statut == Inscription.Statut.VALIDEE:
            club = Club.objects.select_for_update().get(pk=inscription.club_id)
            if club.places_disponibles <= 0:
                raise ValidationError({"club": "Le club a atteint son nombre maximal de membres."})
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
