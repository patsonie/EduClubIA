from django.urls import re_path
from .consumers import ChatConsumer

# Adresse WebSocket d'un salon : ws/messagerie/<id du salon>/
websocket_urlpatterns = [
    re_path(r'ws/messagerie/(?P<salon_id>\d+)/$', ChatConsumer.as_asgi()),
]