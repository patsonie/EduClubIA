# Configuration de l'interface d'administration Django (/admin/) pour les comptes.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Utilisateur, JournalActivite, RelationParentEleve
from django.db.models import Count
from .models import (
    Utilisateur, JournalActivite, RelationParentEleve, CodeInvitation, MatriculeOfficiel,
    CategorieInteret, CentreInteret,
)


# Fiche « Utilisateur » dans l'admin : colonnes de la liste, filtres, recherche.
class UtilisateurAdmin(UserAdmin):
    model = Utilisateur
    list_display = ('email', 'nom', 'prenom', 'role', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff')
    ordering = ('email',)
    search_fields = ('email', 'nom', 'prenom', 'profession')

    # Regroupement des champs sur la page de modification d'un compte.
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informations personnelles', {'fields': (
            'nom', 'prenom', 'telephone', 'date_naissance', 'photo',
            'classe', 'filiere', 'centres_interet', 'interets', 'moyenne_generale', 'profession',
        )}),
        ('Rôle et permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates importantes', {'fields': ('last_login', 'date_joined')}),
    )
    # Champs demandés lors de la création d'un compte depuis l'admin.
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nom', 'prenom', 'role', 'password1', 'password2'),
        }),
    )
    readonly_fields = ('date_joined',)
    filter_horizontal = ('groups', 'user_permissions', 'interets')


# Tableau des enfants affiché directement dans la fiche d'un parent.
class RelationParentEleveInline(admin.TabularInline):
    """Permet de gérer les enfants liés directement depuis la fiche admin d'un parent."""
    model = RelationParentEleve
    fk_name = 'parent'
    extra = 1
    autocomplete_fields = ['enfant']


# Liste des liens parent ↔ élève dans l'admin.
@admin.register(RelationParentEleve)
class RelationParentEleveAdmin(admin.ModelAdmin):
    list_display = ('parent', 'enfant', 'date_creation', 'cree_par')
    search_fields = ('parent__nom', 'parent__prenom', 'enfant__nom', 'enfant__prenom')
    list_filter = ('date_creation',)
    autocomplete_fields = ['parent', 'enfant', 'cree_par']


# Enregistrement des modèles dans l'admin.
admin.site.register(Utilisateur, UtilisateurAdmin)
admin.site.register(JournalActivite)

# Codes d'invitation : l'état « utilisé » n'est pas modifiable à la main.
@admin.register(CodeInvitation)
class CodeInvitationAdmin(admin.ModelAdmin):
    list_display = ('code', 'role_cible', 'utilise', 'utilise_par', 'date_creation')
    list_filter = ('role_cible', 'utilise')
    readonly_fields = ('utilise', 'utilise_par', 'date_utilisation')


# Catégories de centres d'intérêt (ordre d'affichage modifiable).
@admin.register(CategorieInteret)
class CategorieInteretAdmin(admin.ModelAdmin):
    list_display = ('nom', 'ordre')
    search_fields = ('nom',)


# Centres d'intérêt : activation/désactivation en masse et nombre d'élèves intéressés.
@admin.register(CentreInteret)
class CentreInteretAdmin(admin.ModelAdmin):
    list_display = ('nom', 'categorie', 'categorie_club', 'actif', 'nombre_eleves')
    list_filter = ('categorie', 'categorie_club', 'actif')
    list_editable = ('actif',)
    search_fields = ('nom', 'description')
    readonly_fields = ('date_creation', 'date_modification', 'liste_eleves')
    actions = ['desactiver', 'activer']

    # Ajoute le nombre d'élèves à chaque ligne en une seule requête.
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_nb_eleves=Count('eleves'))

    @admin.display(description="Élèves", ordering='_nb_eleves')
    def nombre_eleves(self, obj):
        return obj._nb_eleves

    @admin.display(description="Élèves associés")
    def liste_eleves(self, obj):
        noms = [e.nom_complet for e in obj.eleves.all()[:50]]
        return ', '.join(noms) or '—'

    # Actions groupées proposées dans la liste de l'admin.
    @admin.action(description="Désactiver les centres sélectionnés")
    def desactiver(self, request, queryset):
        queryset.update(actif=False)

    @admin.action(description="Activer les centres sélectionnés")
    def activer(self, request, queryset):
        queryset.update(actif=True)


# Liste officielle des matricules dans l'admin.
@admin.register(MatriculeOfficiel)
class MatriculeOfficielAdmin(admin.ModelAdmin):
    list_display = ('matricule', 'role', 'nom', 'prenom', 'classe')
    list_filter = ('role',)
    search_fields = ('matricule', 'nom', 'prenom')
