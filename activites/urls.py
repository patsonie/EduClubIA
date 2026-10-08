from rest_framework.routers import DefaultRouter
from .views import ActiviteViewSet

# Adresses /api/activites/... générées par le routeur.
router = DefaultRouter()
router.register(r'', ActiviteViewSet, basename='activite')

urlpatterns = router.urls