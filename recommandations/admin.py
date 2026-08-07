from django.contrib import admin
from .models import Recommandation


@admin.register(Recommandation)
class RecommandationAdmin(admin.ModelAdmin):
    list_display = ('eleve', 'club', 'score', 'date_calcul')
    list_filter = ('club',)
    ordering = ('-score',)