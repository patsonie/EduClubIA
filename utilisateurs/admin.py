from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Utilisateur, JournalActivite, RelationParentEleve
from .models import Utilisateur, JournalActivite, RelationParentEleve, CodeInvitation


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
            'classe', 'filiere', 'centres_interet', 'moyenne_generale', 'profession',
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