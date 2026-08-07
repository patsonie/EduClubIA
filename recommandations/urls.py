from django.urls import path
from .views import RecommandationListeView

urlpatterns = [
    path('', RecommandationListeView.as_view(), name='recommandation-liste'),
]