from rest_framework import permissions


class EstGestionnaireOuLectureSeule(permissions.BasePermission):
    """
    Lecture : tout utilisateur authentifié (un élève verra ses propres participations
    via le filtre côté vue).
    Écriture : administrateur, proviseur, encadreur (enregistrement des présences).
    """

    # Lecture : tout utilisateur connecté (le filtrage se fait dans la vue) ; écriture : gestionnaires.
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return (
            request.user and request.user.is_authenticated
            and request.user.role in ['administrateur', 'proviseur', 'encadreur']
        )

    # Sur une présence précise : il faut gérer le club de l'activité.
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        from utilisateurs.perimetre import peut_gerer_club
        return peut_gerer_club(request.user, obj.activite.club)
