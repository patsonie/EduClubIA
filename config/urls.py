from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .views_pages import (
    PageConnexionView, PageDashboardView, PageMesEnfantsView,
    PageClubsView, PageDetailClubView, PageActivitesView, PagePresencesView,
    PageNotificationsView, PageMessagerieView,
    PageInscriptionsView, PageCalendrierView,
    PageMesClubsView, PageMesActivitesView, PageMesPresencesView,
    PageRecommandationsView, PageParentRecommandationsView,
    PageParentClubsView, PageParentActivitesView, PageParentPresencesView, PageParentCalendrierView,
    PageInscriptionView, PageComptesEnAttenteView, PageUtilisateursView, PageRapportsView, PageParametresView, 
    PageReinitialiserMotDePasseView, PageMotDePasseOublieView, PageValidationCompteView,
)
from recommandations.views import ReentrainementIAView, HistoriqueEntrainementView


urlpatterns = [
    path('connexion/', PageConnexionView.as_view(), name='page_connexion'),
    path('', PageDashboardView.as_view(), name='dashboard'),
    path('admin/', admin.site.urls),
    path('api/auth/', include('utilisateurs.urls')),
    path('api/clubs/', include('clubs.urls')),
    path('api/activites/', include('activites.urls')),
    path('api/annees-scolaires/', include('annees_scolaires.urls')),
    path('api/inscriptions/', include('inscriptions.urls')),
    path('api/participations/', include('participations.urls')),
    path('api/recommandations/', include('recommandations.urls')),
    path('api/predictions/', include('analytics.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/messagerie/', include('messagerie.urls')),
    path('parent/enfants/', PageMesEnfantsView.as_view(), name='page_mes_enfants'),
    path('clubs/', PageClubsView.as_view(), name='page_clubs'),
    path('clubs/<int:club_id>/', PageDetailClubView.as_view(), name='page_detail_club'),
    path('activites/', PageActivitesView.as_view(), name='page_activites'),
    path('presences/', PagePresencesView.as_view(), name='page_presences'),
    path('notifications/', PageNotificationsView.as_view(), name='page_notifications'),
    path('messagerie/', PageMessagerieView.as_view(), name='page_messagerie'),
    path('profil/', PageParametresView.as_view(), name='page_profil'),
    path('inscriptions/', PageInscriptionsView.as_view(), name='page_inscriptions'),
    path('calendrier/', PageCalendrierView.as_view(), name='page_calendrier'),
    path('mes-clubs/', PageMesClubsView.as_view(), name='page_mes_clubs'),
    path('mes-activites/', PageMesActivitesView.as_view(), name='page_mes_activites'),
    path('mes-presences/', PageMesPresencesView.as_view(), name='page_mes_presences'),
    path('recommandations/', PageRecommandationsView.as_view(), name='page_recommandations'),
    path('parent/recommandations/', PageParentRecommandationsView.as_view(), name='page_parent_recommandations'),
    path('parent/clubs/', PageParentClubsView.as_view(), name='page_parent_clubs'),
    path('parent/activites/', PageParentActivitesView.as_view(), name='page_parent_activites'),
    path('parent/presences/', PageParentPresencesView.as_view(), name='page_parent_presences'),
    path('parent/calendrier/', PageParentCalendrierView.as_view(), name='page_parent_calendrier'),
    path('inscription/', PageInscriptionView.as_view(), name='page_inscription'),
    path('comptes-en-attente/', PageComptesEnAttenteView.as_view(), name='page_comptes_en_attente'),
    path('utilisateurs/', PageUtilisateursView.as_view(), name='page_utilisateurs'),
    path('rapports/', PageRapportsView.as_view(), name='page_rapports'),
    path('mot-de-passe-oublie/', PageMotDePasseOublieView.as_view(), name='page_mot_de_passe_oublie'),
    path('reinitialiser-mot-de-passe/<str:uidb64>/<str:token>/', PageReinitialiserMotDePasseView.as_view(), name='page_reinitialiser_mot_de_passe'),
    path('api/ia/reentrainement/', ReentrainementIAView.as_view(), name='reentrainement_ia'),
    path('api/ia/historique-entrainement/', HistoriqueEntrainementView.as_view(), name='historique_entrainement'),
    path('validation-compte/', PageValidationCompteView.as_view(), name='page_validation_compte'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    