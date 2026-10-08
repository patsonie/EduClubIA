from rest_framework import permissions

from utilisateurs.perimetre import peut_gerer_club


class EstEncadreurOuAdminOuLectureSeule(permissions.BasePermission):
    """
    Lecture : tout utilisateur authentifié.
    Écriture : administrateur et proviseur (tous clubs) ; encadreur uniquement
    pour les activités de ses propres clubs.
    """

    # Lecture : tout utilisateur connecté ; écriture : gestionnaires.
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return (
            request.user and request.user.is_authenticated
            and request.user.role in ['administrateur', 'proviseur', 'encadreur']
        )

    # Sur une activité précise : l'encadreur doit gérer le club de l'activité.
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return peut_gerer_club(request.user, obj.club)
