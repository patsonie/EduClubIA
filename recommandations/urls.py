from django.urls import path
from .views import RecommandationListeView

# Adresse /api/recommandations/ (les adresses /api/ia/... sont dans config/urls.py).
urlpatterns = [
    path('', RecommandationListeView.as_view(), name='recommandation-liste'),
]