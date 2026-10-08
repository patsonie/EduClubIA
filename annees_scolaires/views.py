from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import ProtectedError
from .models import AnneeScolaire
from .serializers import AnneeScolaireSerializer


# Lecture pour tout utilisateur connecté ; écriture pour administrateur et RP.
class EstAdminOuProviseur(permissions.BasePermission):
    """Seuls administrateurs et proviseurs peuvent gérer les années scolaires."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return (
            request.user and request.user.is_authenticated
            and request.user.role in ['administrateur', 'proviseur']
        )


# === API des années scolaires : /api/annees-scolaires/ ===
class AnneeScolaireViewSet(viewsets.ModelViewSet):
    queryset = AnneeScolaire.objects.all()
    serializer_class = AnneeScolaireSerializer
    permission_classes = [EstAdminOuProviseur]

    # Activer une année : la rend active et archive les inscriptions des années précédentes.
    @action(detail=True, methods=['post'])
    def activer(self, request, pk=None):
        """
        POST /api/annees-scolaires/{id}/activer/
        Active cette année scolaire et archive automatiquement
        les inscriptions des années précédentes.
        """
        from .services import archiver_inscriptions_annee_precedente

        annee = self.get_object()
        with transaction.atomic():
            annee.est_active = True
            annee.save()
            archiver_inscriptions_annee_precedente(annee)

        return Response(
            {"message": f"Année scolaire {annee.libelle} activée. Inscriptions précédentes archivées."},
            status=status.HTTP_200_OK,
        )

    # Désactiver l'année active : plus aucune année active, donc les inscriptions aux clubs sont fermées.
    # Les inscriptions existantes sont conservées (rien n'est archivé).
    @action(detail=True, methods=['post'])
    def desactiver(self, request, pk=None):
        """POST /api/annees-scolaires/{id}/desactiver/"""
        annee = self.get_object()
        if not annee.est_active:
            return Response({"error": "Cette année scolaire n'est pas active."}, status=status.HTTP_400_BAD_REQUEST)
        annee.est_active = False
        annee.save(update_fields=['est_active'])
        return Response(
            {"message": f"Année scolaire {annee.libelle} désactivée. Les inscriptions aux clubs sont fermées."},
            status=status.HTTP_200_OK,
        )

    # Suppression impossible si des inscriptions y sont rattachées (réponse 409).
    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"error": "Cette année scolaire contient des inscriptions et ne peut pas être supprimée."},
                status=status.HTTP_409_CONFLICT,
            )
