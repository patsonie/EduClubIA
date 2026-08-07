from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def obtenir_utilisateur_depuis_token(token):
    from utilisateurs.models import Utilisateur
    try:
        validated_token = AccessToken(token)
        user_id = validated_token['user_id']
        return Utilisateur.objects.get(id=user_id)
    except Exception:
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Authentifie les connexions WebSocket via un token JWT passé en query string.
    Exemple : ws://127.0.0.1:8000/ws/messagerie/1/?token=<access_token>
    """

    async def __call__(self, scope, receive, send):
        query_string = parse_qs(scope["query_string"].decode())
        token = query_string.get("token", [None])[0]

        if token:
            scope["user"] = await obtenir_utilisateur_depuis_token(token)
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)