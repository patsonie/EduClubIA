from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet, PreferenceNotificationView

# Routeur : liste, détail et actions des notifications.
router = DefaultRouter()
router.register(r'', NotificationViewSet, basename='notification')

# « preferences/ » doit précéder le routeur : sinon il est capturé comme un identifiant de notification (404).
urlpatterns = [
    path('preferences/', PreferenceNotificationView.as_view({'get': 'list', 'put': 'update_preferences'}), name='preferences-notification'),
] + router.urls