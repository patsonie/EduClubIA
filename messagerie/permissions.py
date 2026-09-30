from rest_framework import permissions
from inscriptions.models import Inscription


def salon_club(salon):
    return salon.club or (salon.activite.club if salon.activite else None)


def utilisateur_a_acces_salon(user, salon):
    """
    Règles d'accès à un salon :
    - compte actif et validé obligatoire ;
    - salon privé : uniquement ses participants ;
    - administrateur / responsable pédagogique : tous les salons de club et d'activité ;
    - encadreur : salons des clubs qu'il encadre ;
    - élève : salons des clubs où son inscription est validée.
    """
    if not user.is_authenticated or not user.is_active or user.statut_validation != 'valide':
        return False

    if salon.type_salon == salon.TypeSalon.PRIVE:
        return salon.participants.filter(id=user.id).exists()

    club = salon_club(salon)
    if not club:
        return False

    if user.role in ['administrateur', 'proviseur']:
        return True
    if user.role == 'encadreur':
        return club.responsable_id == user.id
    if user.role == 'eleve':
        return Inscription.objects.filter(
            eleve=user, club=club, statut=Inscription.Statut.VALIDEE
        ).exists()
    return False


class EstMembreDuSalon(permissions.BasePermission):
    """Autorise l'accès à un salon selon `utilisateur_a_acces_salon`."""

    def has_object_permission(self, request, view, obj):
        return utilisateur_a_acces_salon(request.user, obj)
