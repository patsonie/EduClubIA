from rest_framework.routers import DefaultRouter
from .views import ParticipationViewSet

# Adresses /api/participations/... générées par le routeur.
router = DefaultRouter()
router.register(r'', ParticipationViewSet, basename='participation')

urlpatterns = router.urls