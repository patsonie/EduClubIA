from rest_framework import permissions


class EstAdminOuProviseur(permissions.BasePermission):
    """Seuls administrateurs et proviseurs peuvent gérer les comptes parents."""

    def has_permission(self, request, view):
        return (
            request.user and request.user.is_authenticated
            and request.user.role in ['administrateur', 'proviseur']
        )
        
from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Limite les tentatives de connexion à 5 par minute par adresse IP, contre le brute-force."""
    scope = 'login'