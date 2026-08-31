from rest_framework import permissions


class EstGestionnaire(permissions.BasePermission):
    """
    Autorise l'accès aux fonctionnalités de gestion et d'analyse aux :
    - Administrateur
    - Responsable pédagogique (rôle technique 'proviseur')
    - Encadreur
    - Parent d'élève (nécessaire pour consulter les données de ses propres enfants
      dans risques-desengagement ; le filtrage aux seuls enfants du parent est fait
      dans la vue elle-même, cette permission ne fait que l'authentification de rôle)
    """

    ROLES_AUTORISES = ['administrateur', 'proviseur', 'encadreur', 'parent']

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in self.ROLES_AUTORISES
        )


class EstGestionnaireStrict(permissions.BasePermission):
    """
    Version stricte réservée aux seuls gestionnaires (administrateur, responsable
    pédagogique, encadreur) — sans le parent. À utiliser pour les vues qui n'ont
    pas de logique de filtrage par enfant
    """

    ROLES_AUTORISES = ['administrateur', 'proviseur', 'encadreur']

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in self.ROLES_AUTORISES
        )