from django.contrib import admin
from .models import Club


# Liste des clubs dans l'interface d'administration Django.
@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ('nom', 'categorie', 'responsable', 'statut', 'nombre_max_membres', 'date_creation')
    list_filter = ('categorie', 'statut')
    search_fields = ('nom', 'description')