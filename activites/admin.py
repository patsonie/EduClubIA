from django.contrib import admin
from .models import Activite, HistoriqueActivite


@admin.register(Activite)
class ActiviteAdmin(admin.ModelAdmin):
    list_display = ('titre', 'club', 'date', 'heure', 'lieu', 'statut', 'budget')
    list_filter = ('statut', 'club')
    search_fields = ('titre', 'description', 'lieu')


@admin.register(HistoriqueActivite)
class HistoriqueActiviteAdmin(admin.ModelAdmin):
    list_display = ('activite', 'ancien_statut', 'nouveau_statut', 'modifie_par', 'date_modification')
    list_filter = ('nouveau_statut',)