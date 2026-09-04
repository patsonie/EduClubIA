from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import SalonDiscussion, Message
from .serializers import SalonDiscussionSerializer, MessageSerializer
from .permissions import EstMembreDuSalon
from inscriptions.models import Inscription
from utilisateurs.validators import valider_fichier_message


class SalonDiscussionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/messagerie/salons/ — liste des salons accessibles à l'utilisateur connecté.
    GET /api/messagerie/salons/{id}/messages/ — historique des messages d'un salon.
    POST /api/messagerie/salons/{id}/envoyer_fichier/ — partage d'un fichier dans le salon.
    """
    serializer_class = SalonDiscussionSerializer
    permission_classes = [permissions.IsAuthenticated, EstMembreDuSalon]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['administrateur', 'proviseur', 'encadreur']:
            return SalonDiscussion.objects.all()

        clubs_ids = Inscription.objects.filter(
            eleve=user, statut=Inscription.Statut.VALIDEE
        ).values_list('club_id', flat=True)

        return SalonDiscussion.objects.filter(
            club_id__in=clubs_ids
        ) | SalonDiscussion.objects.filter(
            activite__club_id__in=clubs_ids
        )
        
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        salon = self.get_object()
        messages = salon.messages.all().order_by('date_envoi')
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def envoyer_fichier(self, request, pk=None):
        salon = self.get_object()
        fichier = request.FILES.get('fichier')

        if not fichier:
            return Response({"error": "Aucun fichier fourni."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            valider_fichier_message(fichier)
        except Exception as exc:
            raise ValidationError({"fichier": list(getattr(exc, 'messages', [str(exc)]))})

        contenu = request.data.get('contenu', '')
        if len(contenu) > 2000:
            raise ValidationError({"contenu": "Le message ne doit pas dépasser 2 000 caractères."})

        message = Message.objects.create(
            salon=salon,
            expediteur=request.user,
            contenu=contenu,
            fichier=fichier,
        )

        # Diffusion temps réel aux utilisateurs connectés au salon via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'salon_{salon.id}',
            {
                'type': 'diffuser_message',
                'message_id': message.id,
                'contenu': message.contenu,
                'expediteur_id': request.user.id,
                'expediteur_nom': request.user.nom_complet,
                'date_envoi': message.date_envoi.isoformat(),
            }
        )

        serializer = MessageSerializer(message)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
