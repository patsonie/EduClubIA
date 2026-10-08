from django.contrib import admin
from .models import Recommandation


# Recommandations calculées, visibles dans l'interface d'administration.
@admin.register(Recommandation)
class RecommandationAdmin(admin.ModelAdmin):
    list_display = ('eleve', 'club', 'score', 'date_calcul')
    list_filter = ('club',)
    ordering = ('-score',)