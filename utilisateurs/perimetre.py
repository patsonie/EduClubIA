"""Aides de périmètre : quels clubs un utilisateur gère-t-il ?"""
from clubs.models import Club

ROLES_GESTION_GLOBALE = ('administrateur', 'proviseur')


def est_gestion_globale(user):
    return user.role in ROLES_GESTION_GLOBALE


def clubs_geres(user):
    """Clubs sur lesquels l'utilisateur peut agir : tous (admin/proviseur) ou ceux qu'il encadre."""
    if est_gestion_globale(user):
        return Club.objects.all()
    if user.role == 'encadreur':
        return Club.objects.filter(responsable=user)
    return Club.objects.none()


def peut_gerer_club(user, club):
    if est_gestion_globale(user):
        return True
    return user.role == 'encadreur' and club is not None and club.responsable_id == user.id
