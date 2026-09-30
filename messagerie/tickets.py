"""Tickets WebSocket : jeton signé, valable 30 s, à usage unique (évite de mettre le JWT dans l'URL)."""
from django.core import signing
from django.core.cache import cache

SALT = 'messagerie.ws-ticket'
DUREE_VALIDITE = 30  # secondes


def creer_ticket(utilisateur):
    return signing.dumps({'uid': utilisateur.id}, salt=SALT)


def consommer_ticket(ticket):
    """Retourne l'identifiant utilisateur, ou None si le ticket est invalide, expiré ou déjà utilisé."""
    try:
        donnees = signing.loads(ticket, salt=SALT, max_age=DUREE_VALIDITE)
    except signing.BadSignature:
        return None
    if not cache.add(f'wsticket:{ticket}', 1, DUREE_VALIDITE * 2):
        return None
    return donnees.get('uid')
