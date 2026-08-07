from django.contrib import admin
from .models import Inscription, HistoriqueInscription


@admin.register(Inscription)
class InscriptionAdmin(admin.ModelAdmin):
    list_display = ('eleve', 'club', 'annee_scolaire', 'statut', 'date_inscription')
    list_filter = ('statut', 'annee_scolaire', 'club')
    search_fields = ('eleve__nom', 'eleve__prenom', 'club__nom')


@admin.register(HistoriqueInscription)
class HistoriqueInscriptionAdmin(admin.ModelAdmin):
    list_display = ('inscription', 'ancien_statut', 'nouveau_statut', 'modifie_par', 'date_modification')