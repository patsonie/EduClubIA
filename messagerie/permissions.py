# RÈGLE UNIQUE d'accès aux salons, utilisée par l'API REST et par le WebSocket.
# Pour changer qui peut lire/écrire dans un salon, modifier utilisateur_a_acces_salon.
from rest_framework import permissions
from inscriptions.models import Inscription


# Club rattaché au salon (directement ou via l'activité).
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
    # Compte non connecté, désactivé ou non validé : aucun accès.
    if not user.is_authenticated or not user.is_active or user.statut_validation != 'valide':
        return False

    # Conversation privée : réservée à ses participants.
    if salon.type_salon == salon.TypeSalon.PRIVE:
        return salon.participants.filter(id=user.id).exists()

    club = salon_club(salon)
    if not club:
        return False

    # Accès selon le rôle (parents : pas d'accès aux salons de club).
    if user.role in ['administrateur', 'proviseur']:
        return True
    if user.role == 'encadreur':
        return club.responsable_id == user.id
    if user.role == 'eleve':
        return Inscription.objects.filter(
            eleve=user, club=club, statut=Inscription.Statut.VALIDEE
        ).exists()
    return False


# Permission DRF qui applique la règle ci-dessus à chaque salon demandé.
class EstMembreDuSalon(permissions.BasePermission):
    """Autorise l'accès à un salon selon `utilisateur_a_acces_salon`."""

    def has_object_permission(self, request, view, obj):
        return utilisateur_a_acces_salon(request.user, obj)
