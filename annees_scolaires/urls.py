from rest_framework.routers import DefaultRouter
from .views import AnneeScolaireViewSet

router = DefaultRouter()
router.register(r'', AnneeScolaireViewSet, basename='annee-scolaire')

urlpatterns = router.urls