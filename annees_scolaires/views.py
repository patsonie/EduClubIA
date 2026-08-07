from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import AnneeScolaire
from .serializers import AnneeScolaireSerializer


class EstAdminOuProviseur(permissions.BasePermission):
    """Seuls administrateurs et proviseurs peuvent gérer les années scolaires."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return (
            request.user and request.user.is_authenticated
            and request.user.role in ['administrateur', 'proviseur']
        )


class AnneeScolaireViewSet(viewsets.ModelViewSet):
    queryset = AnneeScolaire.objects.all()
    serializer_class = AnneeScolaireSerializer
    permission_classes = [EstAdminOuProviseur]

    @action(detail=True, methods=['post'])
    def activer(self, request, pk=None):
        """
        POST /api/annees-scolaires/{id}/activer/
        Active cette année scolaire et archive automatiquement
        les inscriptions des années précédentes.
        """
        from .services import archiver_inscriptions_annee_precedente

        annee = self.get_object()
        annee.est_active = True
        annee.save()

        archiver_inscriptions_annee_precedente(annee)

        return Response(
            {"message": f"Année scolaire {annee.libelle} activée. Inscriptions précédentes archivées."},
            status=status.HTTP_200_OK,
        )