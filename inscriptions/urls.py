from rest_framework.routers import DefaultRouter
from .views import InscriptionViewSet

# Adresses /api/inscriptions/... générées par le routeur.
router = DefaultRouter()
router.register(r'', InscriptionViewSet, basename='inscription')

urlpatterns = router.urls