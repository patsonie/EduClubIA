import json
import time
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

DELAI_MIN_ENTRE_MESSAGES = 0.5  # secondes : limite anti-flood par connexion


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Gère une connexion WebSocket pour un salon de discussion donné.
    URL : ws/messagerie/<salon_id>/?token=<access_token>
    Les droits sont revérifiés à chaque message (suspension, retrait du club...).
    """

    async def connect(self):
        self.salon_id = self.scope['url_route']['kwargs']['salon_id']
        self.groupe_salon = f'salon_{self.salon_id}'
        self.user = self.scope['user']
        self.dernier_envoi = 0.0

        if not self.user or not self.user.is_authenticated or not self.user.is_active:
            await self.close(code=4001)
            return

        autorise = await self.verifier_acces_salon()
        if not autorise:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.groupe_salon, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'groupe_salon'):
            await self.channel_layer.group_discard(self.groupe_salon, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(data, dict):
            return
        contenu = data.get('contenu', '')
        if not isinstance(contenu, str):
            return
        contenu = contenu.strip()

        if not contenu or len(contenu) > 2000:
            return

        maintenant = time.monotonic()
        if maintenant - self.dernier_envoi < DELAI_MIN_ENTRE_MESSAGES:
            return
        self.dernier_envoi = maintenant

        if not await self.verifier_acces_salon():
            await self.close(code=4003)
            return

        message = await self.enregistrer_message(contenu)

        await self.channel_layer.group_send(
            self.groupe_salon,
            {
                'type': 'diffuser_message',
                'message_id': message.id,
                'contenu': message.contenu,
                'expediteur_id': self.user.id,
                'expediteur_nom': self.user.nom_complet,
                'date_envoi': message.date_envoi.isoformat(),
            }
        )

    async def diffuser_message(self, event):
        await self.send(text_data=json.dumps({
            'id': event['message_id'],
            'contenu': event['contenu'],
            'expediteur_id': event['expediteur_id'],
            'expediteur_nom': event['expediteur_nom'],
            'date_envoi': event['date_envoi'],
            'fichier_url': event.get('fichier_url'),
        }))

    @database_sync_to_async
    def verifier_acces_salon(self):
        from .models import SalonDiscussion
        from .permissions import utilisateur_a_acces_salon
        from utilisateurs.models import Utilisateur

        try:
            salon = SalonDiscussion.objects.select_related('club', 'activite__club').get(id=self.salon_id)
            # Rechargement : le statut du compte a pu changer depuis la connexion.
            utilisateur = Utilisateur.objects.get(id=self.user.id)
        except (SalonDiscussion.DoesNotExist, Utilisateur.DoesNotExist):
            return False

        return utilisateur_a_acces_salon(utilisateur, salon)

    @database_sync_to_async
    def enregistrer_message(self, contenu):
        from .models import SalonDiscussion, Message
        salon = SalonDiscussion.objects.get(id=self.salon_id)
        return Message.objects.create(salon=salon, expediteur=self.user, contenu=contenu)
