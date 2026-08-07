from rest_framework import permissions


class EstAdminOuProviseurOuLectureSeule(permissions.BasePermission):
    """
    Autorise la lecture à tous les utilisateurs authentifiés.
    Autorise la création/modification/suppression uniquement aux
    administrateurs et proviseurs.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return (
            request.user and request.user.is_authenticated
            and request.user.role in ['administrateur', 'proviseur']
        )