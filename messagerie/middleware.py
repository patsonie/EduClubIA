from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

from .tickets import consommer_ticket


# Retrouve l'utilisateur à partir du ticket (valide, non utilisé, compte actif) ; sinon anonyme.
@database_sync_to_async
def obtenir_utilisateur_depuis_ticket(ticket):
    from utilisateurs.models import Utilisateur
    user_id = consommer_ticket(ticket)
    if user_id is None:
        return AnonymousUser()
    try:
        utilisateur = Utilisateur.objects.get(id=user_id)
    except Utilisateur.DoesNotExist:
        return AnonymousUser()
    if not utilisateur.is_active or utilisateur.statut_validation != 'valide':
        return AnonymousUser()
    return utilisateur


class JWTAuthMiddleware(BaseMiddleware):
    """
    Authentifie les connexions WebSocket via un ticket à usage unique (30 s) obtenu par
    POST /api/messagerie/ticket/ avec le JWT d'accès. Le JWT lui-même n'apparaît jamais dans l'URL.
    Exemple : ws://127.0.0.1:8000/ws/messagerie/1/?ticket=<ticket>
    """

    # Lit le paramètre ?ticket= de l'URL WebSocket et place l'utilisateur dans la connexion.
    async def __call__(self, scope, receive, send):
        query_string = parse_qs(scope["query_string"].decode())
        ticket = query_string.get("ticket", [None])[0]

        if ticket:
            scope["user"] = await obtenir_utilisateur_depuis_ticket(ticket)
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
