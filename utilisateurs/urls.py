from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    InscriptionView, ConnexionView, DeconnexionView,
    ProfilView, ChangementMotDePasseView, ParentViewSet, MesEnfantsView,
    TableauDeBordParentView, ComptesEnAttenteView, ValiderCompteView,
    RefuserCompteView, CodeInvitationViewSet, UtilisateurAdminViewSet,
    TelechargerJustificatifView, DemandeReinitialisationMotDePasseView,
    ConfirmerReinitialisationMotDePasseView, EnvoyerCodeValidationView,
    RegenererCodeValidationView, ValiderCodeCompteView,  RenvoyerCodeExpireView,
)

router = DefaultRouter()
router.register(r'parents', ParentViewSet, basename='parent')
router.register(r'codes-invitation', CodeInvitationViewSet, basename='code-invitation')
router.register(r'utilisateurs', UtilisateurAdminViewSet, basename='utilisateur-admin')

urlpatterns = [
    path('register/', InscriptionView.as_view(), name='inscription'),
    path('login/', ConnexionView.as_view(), name='connexion'),
    path('logout/', DeconnexionView.as_view(), name='deconnexion'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profil/', ProfilView.as_view(), name='profil'),
    path('changer-mot-de-passe/', ChangementMotDePasseView.as_view(), name='changer_mot_de_passe'),
    path('mes-enfants/', MesEnfantsView.as_view(), name='mes_enfants'),
    path('dashboard-parent/', TableauDeBordParentView.as_view(), name='dashboard_parent'),
    path('comptes-en-attente/', ComptesEnAttenteView.as_view(), name='comptes_en_attente'),
    path('comptes/<int:pk>/valider/', ValiderCompteView.as_view(), name='valider_compte'),
    path('comptes/<int:pk>/refuser/', RefuserCompteView.as_view(), name='refuser_compte'),
    path('', include(router.urls)),
    path('justificatif/<int:utilisateur_id>/', TelechargerJustificatifView.as_view(), name='telecharger_justificatif'),
    path('mot-de-passe-oublie/', DemandeReinitialisationMotDePasseView.as_view(), name='mot_de_passe_oublie'),
    path('reinitialiser-mot-de-passe/', ConfirmerReinitialisationMotDePasseView.as_view(), name='reinitialiser_mot_de_passe'),
    path('valider-code/', ValiderCodeCompteView.as_view(), name='valider_code_compte'),
    path('comptes/<int:pk>/envoyer_code/', EnvoyerCodeValidationView.as_view(), name='envoyer_code'),
    path('comptes/<int:pk>/regenerer_code/', RegenererCodeValidationView.as_view(), name='regenerer_code'),
    path('renvoyer-code-expire/', RenvoyerCodeExpireView.as_view(), name='renvoyer_code_expire'),
]