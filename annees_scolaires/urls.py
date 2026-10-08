from rest_framework.routers import DefaultRouter
from .views import AnneeScolaireViewSet

# Adresses /api/annees-scolaires/... générées par le routeur.
router = DefaultRouter()
router.register(r'', AnneeScolaireViewSet, basename='annee-scolaire')

urlpatterns = router.urls