from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Notification, PreferenceNotification
from .serializers import NotificationSerializer, PreferenceNotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/notifications/ — liste des notifications de l'utilisateur connecté.
    Filtre : ?lu=false
    Action : POST /api/notifications/{id}/marquer_lu/
    Action : POST /api/notifications/tout_marquer_lu/
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Notification.objects.filter(destinataire=self.request.user)
        lu = self.request.query_params.get('lu')
        if lu is not None:
            queryset = queryset.filter(lu=(lu.lower() == 'true'))
        return queryset

    @action(detail=True, methods=['post'])
    def marquer_lu(self, request, pk=None):
        notification = self.get_object()
        notification.lu = True
        notification.date_lecture = timezone.now()
        notification.save()
        return Response(NotificationSerializer(notification).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def tout_marquer_lu(self, request):
        Notification.objects.filter(destinataire=request.user, lu=False).update(
            lu=True, date_lecture=timezone.now()
        )
        return Response({"message": "Toutes les notifications ont été marquées comme lues."}, status=status.HTTP_200_OK)


class PreferenceNotificationView(viewsets.ViewSet):
    """
    GET/PUT /api/notifications/preferences/ — gestion des préférences de canal.
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        preference, _ = PreferenceNotification.objects.get_or_create(utilisateur=request.user)
        return Response(PreferenceNotificationSerializer(preference).data)

    def update_preferences(self, request):
        preference, _ = PreferenceNotification.objects.get_or_create(utilisateur=request.user)
        serializer = PreferenceNotificationSerializer(preference, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)