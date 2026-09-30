from rest_framework import permissions


class EstAdminOuProviseur(permissions.BasePermission):
    """Seuls administrateurs et proviseurs peuvent gérer les comptes parents."""

    def has_permission(self, request, view):
        return (
            request.user and request.user.is_authenticated
            and request.user.role in ['administrateur', 'proviseur']
        )


class EstAdministrateur(permissions.BasePermission):
    """Réservé aux administrateurs."""

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role == 'administrateur'
        )


from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Limite les tentatives de connexion à 5 par minute par adresse IP, contre le brute-force."""
    scope = 'login'


class ChangementMotDePasseThrottle(UserRateThrottle):
    """Limite les essais d'ancien mot de passe depuis une session (jeton volé)."""
    scope = 'password_change'
