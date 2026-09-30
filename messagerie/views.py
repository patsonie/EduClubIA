from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from .tickets import creer_ticket
from rest_framework.exceptions import ValidationError
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Q
from django.http import FileResponse, Http404
from clubs.models import Club
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
        base = SalonDiscussion.objects.select_related('club', 'activite')
        prives = Q(type_salon=SalonDiscussion.TypeSalon.PRIVE, participants=user)

        if user.role in ['administrateur', 'proviseur']:
            return base.filter(~Q(type_salon=SalonDiscussion.TypeSalon.PRIVE) | prives).distinct()

        if user.role == 'encadreur':
            clubs_ids = Club.objects.filter(responsable=user).values_list('id', flat=True)
        elif user.role == 'eleve':
            clubs_ids = Inscription.objects.filter(
                eleve=user, statut=Inscription.Statut.VALIDEE
            ).values_list('club_id', flat=True)
        else:
            clubs_ids = []

        return base.filter(
            Q(club_id__in=clubs_ids) | Q(activite__club_id__in=clubs_ids) | prives
        ).distinct()


    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        salon = self.get_object()
        messages = salon.messages.select_related('expediteur').order_by('date_envoi')
        serializer = MessageSerializer(messages, many=True, context={'request': request})
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
                'fichier_url': f'/api/messagerie/salons/{salon.id}/fichier/{message.id}/',
            }
        )

        serializer = MessageSerializer(message, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path=r'fichier/(?P<message_id>\d+)')
    def fichier(self, request, pk=None, message_id=None):
        # Télécharge la pièce jointe d'un message, après contrôle d'accès au salon.
        salon = self.get_object()
        try:
            message = salon.messages.get(pk=message_id)
        except Message.DoesNotExist:
            raise Http404("Message introuvable.")
        if not message.fichier:
            raise Http404("Aucune pièce jointe.")
        try:
            ouvert = message.fichier.open('rb')
        except (FileNotFoundError, OSError):
            raise Http404("Fichier introuvable.")
        return FileResponse(ouvert, as_attachment=True, filename=message.fichier.name.rsplit('/', 1)[-1])


class TicketWebSocketView(APIView):
    """POST /api/messagerie/ticket/ — ticket à usage unique (30 s) pour ouvrir une connexion WebSocket."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        return Response({"ticket": creer_ticket(request.user)}, status=status.HTTP_200_OK)
