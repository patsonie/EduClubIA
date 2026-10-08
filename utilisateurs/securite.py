"""Protection contre le brute force par compte (en complément du throttling par IP)."""
import logging

from django.core.cache import cache
from rest_framework.exceptions import Throttled

logger = logging.getLogger('securite')

# Nombre d'échecs tolérés avant blocage, et durée du blocage.
MAX_ECHECS = 5
DUREE_BLOCAGE = 15 * 60  # secondes


# Clé de cache, par exemple « echecs:login:eleve@mail.cm ».
def _cle(portee, identifiant):
    return f"echecs:{portee}:{str(identifiant).strip().lower()}"


def verifier_non_bloque(portee, identifiant):
    """Lève Throttled (HTTP 429) si trop d'échecs récents pour cet identifiant."""
    if cache.get(_cle(portee, identifiant), 0) >= MAX_ECHECS:
        logger.warning("Blocage temporaire (%s) pour %s", portee, identifiant)
        raise Throttled(wait=DUREE_BLOCAGE, detail="Trop de tentatives. Réessayez dans quelques minutes.")


# Compte un échec de plus (le compteur expire tout seul après DUREE_BLOCAGE).
def enregistrer_echec(portee, identifiant):
    cle = _cle(portee, identifiant)
    cache.add(cle, 0, DUREE_BLOCAGE)
    try:
        cache.incr(cle)
    except ValueError:
        cache.set(cle, 1, DUREE_BLOCAGE)
    logger.info("Échec d'authentification (%s) pour %s", portee, identifiant)


# Remet le compteur à zéro après une réussite.
def reinitialiser(portee, identifiant):
    cache.delete(_cle(portee, identifiant))
