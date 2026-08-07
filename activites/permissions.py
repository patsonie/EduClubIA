from rest_framework import permissions


class EstEncadreurOuAdminOuLectureSeule(permissions.BasePermission):
    """
    Lecture : tout utilisateur authentifié.
    Écriture (création/modification/suppression) : administrateur, proviseur, encadreur.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return (
            request.user and request.user.is_authenticated
            and request.user.role in ['administrateur', 'proviseur', 'encadreur']
        )