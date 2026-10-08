from django.contrib import admin
from .models import RisqueDesengagement, PredictionParticipation, ClubEnDifficulte

# Résultats d'analyse visibles dans l'interface d'administration.
admin.site.register(RisqueDesengagement)
admin.site.register(PredictionParticipation)
admin.site.register(ClubEnDifficulte)