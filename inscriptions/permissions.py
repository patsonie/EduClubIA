from rest_framework import permissions


class EstProprietaireOuGestionnaire(permissions.BasePermission):
    """
    Un élève ne peut voir/gérer que ses propres inscriptions.
    Administrateurs, proviseurs et encadreurs peuvent tout voir et valider/refuser.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.role in ['administrateur', 'proviseur', 'encadreur']:
            return True
        return obj.eleve == request.user