"""Aides de périmètre : quels clubs un utilisateur gère-t-il ?"""
from clubs.models import Club
from django.db import transaction
from django.db.models import Q

# Rôles qui gèrent tous les clubs de l'établissement.
ROLES_GESTION_GLOBALE = ('administrateur', 'proviseur')


# Vrai pour l'administrateur et le responsable pédagogique.
def est_gestion_globale(user):
    return user.role in ROLES_GESTION_GLOBALE


def clubs_geres(user):
    """Clubs sur lesquels l'utilisateur peut agir : tous (admin/proviseur) ou ceux qu'il encadre."""
    if est_gestion_globale(user):
        return Club.objects.all()
    if user.role == 'encadreur':
        return Club.objects.filter(responsable=user)
    return Club.objects.none()


# Vrai si l'utilisateur a le droit d'agir sur ce club précis.
def peut_gerer_club(user, club):
    if est_gestion_globale(user):
        return True
    return user.role == 'encadreur' and club is not None and club.responsable_id == user.id


def clubs_disponibles_pour_encadreur(encadreur=None):
    """
    Clubs qu'un encadreur peut choisir : non archivés et sans responsable
    (plus, le cas échéant, le club qu'il encadre déjà).
    """
    libres = Q(responsable__isnull=True)
    if encadreur is not None:
        libres |= Q(responsable=encadreur)
    return Club.objects.exclude(statut=Club.Statut.ARCHIVE).filter(libres)


def affecter_club_encadreur(encadreur, club):
    """
    Un encadreur encadre un et un seul club, et un club n'a qu'un encadreur.
    Libère l'ancien club et prend le nouveau dans une même transaction ; le verrou
    sur le club évite que deux encadreurs le réservent en même temps.
    Lève ValueError si le club est déjà pris par un autre encadreur.
    """
    with transaction.atomic():
        # Verrou sur la ligne du club pour éviter que deux encadreurs le prennent en même temps.
        club = Club.objects.select_for_update().get(pk=club.pk)
        if club.responsable_id not in (None, encadreur.pk):
            raise ValueError("Ce club est déjà encadré par un autre encadreur.")
        if club.statut == Club.Statut.ARCHIVE:
            raise ValueError("Ce club est archivé.")
        # Libère l'ancien club de l'encadreur, puis lui attribue le nouveau.
        Club.objects.filter(responsable=encadreur).exclude(pk=club.pk).update(responsable=None)
        if club.responsable_id != encadreur.pk:
            club.responsable = encadreur
            club.save(update_fields=['responsable'])
        # Garde aussi le nom du club dans le profil (champ texte historique).
        encadreur.club_souhaite = club.nom
        encadreur.save(update_fields=['club_souhaite'])
    return club
