# Point d'entrée ASGI (serveur Daphne) : HTTP classique + WebSocket de la messagerie.
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Application Django standard pour les requêtes HTTP.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
import messagerie.routing
from channels.security.websocket import AllowedHostsOriginValidator
from messagerie.middleware import JWTAuthMiddleware

# Aiguillage : HTTP vers Django ; WebSocket vers la messagerie, après contrôle de l'origine
# et authentification par ticket.
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        JWTAuthMiddleware(
            URLRouter(
                messagerie.routing.websocket_urlpatterns
            )
        )
    ),
})