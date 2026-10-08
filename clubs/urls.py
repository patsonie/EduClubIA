from rest_framework.routers import DefaultRouter
from .views import ClubViewSet

# Toutes les adresses /api/clubs/... sont générées par le routeur à partir du ViewSet.
router = DefaultRouter()
router.register(r'', ClubViewSet, basename='club')

urlpatterns = router.urls