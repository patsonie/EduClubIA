from django.contrib import admin
from .models import Participation


@admin.register(Participation)
class ParticipationAdmin(admin.ModelAdmin):
    list_display = ('inscription', 'activite', 'statut', 'date_enregistrement', 'enregistre_par')
    list_filter = ('statut', 'activite')