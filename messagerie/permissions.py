from rest_framework import permissions
from inscriptions.models import Inscription


class EstMembreDuSalon(permissions.BasePermission):
    """
    Autorise l'accès à un salon uniquement aux gestionnaires (admin/proviseur/encadreur)
    ou aux élèves validés du club concerné par le salon.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role in ['administrateur', 'proviseur', 'encadreur']:
            return True

        club = obj.club or (obj.activite.club if obj.activite else None)
        if not club:
            return False

        return Inscription.objects.filter(
            eleve=user, club=club, statut=Inscription.Statut.VALIDEE
        ).exists()