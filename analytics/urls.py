from django.urls import path
from .views import (
    RisqueDesengagementView, PredictionParticipationView,
    ClubEnDifficulteView, StatistiquesGlobalesView, RapportDetailleView,
)

urlpatterns = [
    path('risques-desengagement/', RisqueDesengagementView.as_view(), name='risques-desengagement'),
    path('participation/<int:activite_id>/', PredictionParticipationView.as_view(), name='prediction-participation'),
    path('clubs-difficulte/', ClubEnDifficulteView.as_view(), name='clubs-difficulte'),
    path('statistiques-globales/', StatistiquesGlobalesView.as_view(), name='statistiques-globales'),
    path('rapport-detaille/', RapportDetailleView.as_view(), name='rapport-detaille'),
]