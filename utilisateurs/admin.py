from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Utilisateur, JournalActivite, RelationParentEleve
from django.db.models import Count
from .models import (
    Utilisateur, JournalActivite, RelationParentEleve, CodeInvitation, MatriculeOfficiel,
    CategorieInteret, CentreInteret,
)


class UtilisateurAdmin(UserAdmin):
    model = Utilisateur
    list_display = ('email', 'nom', 'prenom', 'role', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff')
    ordering = ('email',)
    search_fields = ('email', 'nom', 'prenom', 'profession')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informations personnelles', {'fields': (
            'nom', 'prenom', 'telephone', 'date_naissance', 'photo',
            'classe', 'filiere', 'centres_interet', 'interets', 'moyenne_generale', 'profession',
        )}),
        ('Rôle et permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates importantes', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nom', 'prenom', 'role', 'password1', 'password2'),
        }),
    )
    readonly_fields = ('date_joined',)
    filter_horizontal = ('groups', 'user_permissions', 'interets')


class RelationParentEleveInline(admin.TabularInline):
    """Permet de gérer les enfants liés directement depuis la fiche admin d'un parent."""
    model = RelationParentEleve
    fk_name = 'parent'
    extra = 1
    autocomplete_fields = ['enfant']


@admin.register(RelationParentEleve)
class RelationParentEleveAdmin(admin.ModelAdmin):
    list_display = ('parent', 'enfant', 'date_creation', 'cree_par')
    search_fields = ('parent__nom', 'parent__prenom', 'enfant__nom', 'enfant__prenom')
    list_filter = ('date_creation',)
    autocomplete_fields = ['parent', 'enfant', 'cree_par']


admin.site.register(Utilisateur, UtilisateurAdmin)
admin.site.register(JournalActivite)

@admin.register(CodeInvitation)
class CodeInvitationAdmin(admin.ModelAdmin):
    list_display = ('code', 'role_cible', 'utilise', 'utilise_par', 'date_creation')
    list_filter = ('role_cible', 'utilise')
    readonly_fields = ('utilise', 'utilise_par', 'date_utilisation')


@admin.register(CategorieInteret)
class CategorieInteretAdmin(admin.ModelAdmin):
    list_display = ('nom', 'ordre')
    search_fields = ('nom',)


@admin.register(CentreInteret)
class CentreInteretAdmin(admin.ModelAdmin):
    list_display = ('nom', 'categorie', 'categorie_club', 'actif', 'nombre_eleves')
    list_filter = ('categorie', 'categorie_club', 'actif')
    list_editable = ('actif',)
    search_fields = ('nom', 'description')
    readonly_fields = ('date_creation', 'date_modification', 'liste_eleves')
    actions = ['desactiver', 'activer']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_nb_eleves=Count('eleves'))

    @admin.display(description="Élèves", ordering='_nb_eleves')
    def nombre_eleves(self, obj):
        return obj._nb_eleves

    @admin.display(description="Élèves associés")
    def liste_eleves(self, obj):
        noms = [e.nom_complet for e in obj.eleves.all()[:50]]
        return ', '.join(noms) or '—'

    @admin.action(description="Désactiver les centres sélectionnés")
    def desactiver(self, request, queryset):
        queryset.update(actif=False)

    @admin.action(description="Activer les centres sélectionnés")
    def activer(self, request, queryset):
        queryset.update(actif=True)


@admin.register(MatriculeOfficiel)
class MatriculeOfficielAdmin(admin.ModelAdmin):
    list_display = ('matricule', 'role', 'nom', 'prenom', 'classe')
    list_filter = ('role',)
    search_fields = ('matricule', 'nom', 'prenom')
