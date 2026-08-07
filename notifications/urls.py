from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet, PreferenceNotificationView

router = DefaultRouter()
router.register(r'', NotificationViewSet, basename='notification')

urlpatterns = router.urls + [
    path('preferences/', PreferenceNotificationView.as_view({'get': 'list', 'put': 'update_preferences'}), name='preferences-notification'),
]