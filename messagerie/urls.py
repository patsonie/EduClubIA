from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import SalonDiscussionViewSet, TicketWebSocketView

router = DefaultRouter()
router.register(r'salons', SalonDiscussionViewSet, basename='salon')

urlpatterns = router.urls + [
    path('ticket/', TicketWebSocketView.as_view(), name='ws-ticket'),
]