from rest_framework import serializers
from .models import Notification, PreferenceNotification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'type_notification', 'titre', 'message', 'lu', 'date_creation', 'date_lecture']
        read_only_fields = ['id', 'type_notification', 'titre', 'message', 'date_creation', 'date_lecture']


class PreferenceNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreferenceNotification
        fields = ['id', 'notifications_internes', 'notifications_email', 'notifications_sms']
        read_only_fields = ['id']