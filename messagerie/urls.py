from rest_framework.routers import DefaultRouter
from .views import SalonDiscussionViewSet

router = DefaultRouter()
router.register(r'salons', SalonDiscussionViewSet, basename='salon')

urlpatterns = router.urls