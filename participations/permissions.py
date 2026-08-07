from rest_framework import permissions


class EstGestionnaireOuLectureSeule(permissions.BasePermission):
    """
    Lecture : tout utilisateur authentifié (un élève verra ses propres participations
    via le filtre côté vue).
    Écriture : administrateur, proviseur, encadreur (enregistrement des présences).
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return (
            request.user and request.user.is_authenticated
            and request.user.role in ['administrateur', 'proviseur', 'encadreur']
        )