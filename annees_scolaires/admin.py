from django.contrib import admin
from .models import AnneeScolaire


# Années scolaires dans l'interface d'administration.
@admin.register(AnneeScolaire)
class AnneeScolaireAdmin(admin.ModelAdmin):
    list_display = ('libelle', 'date_debut', 'date_fin', 'est_active')
    list_filter = ('est_active',)