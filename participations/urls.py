from rest_framework.routers import DefaultRouter
from .views import ParticipationViewSet

router = DefaultRouter()
router.register(r'', ParticipationViewSet, basename='participation')

urlpatterns = router.urls