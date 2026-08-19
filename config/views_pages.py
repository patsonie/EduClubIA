from django.views.generic import TemplateView



class PageConnexionView(TemplateView):
    template_name = 'base/connexion.html'


class PageDashboardView(TemplateView):
    template_name = 'dashboard/dashboard.html'
    
class PageMesEnfantsView(TemplateView):
    template_name = 'parents/mes_enfants.html'
    
class PageClubsView(TemplateView):
    template_name = 'clubs/liste_clubs.html'
    
class PageDetailClubView(TemplateView):
    template_name = 'clubs/detail_club.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['club_id'] = kwargs.get('club_id')
        return context
    
class PageActivitesView(TemplateView):
    template_name = 'activites/liste_activites.html'
    
class PagePresencesView(TemplateView):
    template_name = 'activites/presences.html'
    
class PageNotificationsView(TemplateView):
    template_name = 'base/notifications.html'
    
class PageMessagerieView(TemplateView):
    template_name = 'base/messagerie.html'
    
class PageParametresView(TemplateView):
    template_name = 'base/parametres.html'
    
class PageInscriptionsView(TemplateView):
    template_name = 'clubs/inscriptions.html'

class PageCalendrierView(TemplateView):
    template_name = 'activites/calendrier.html'

class PageMesClubsView(TemplateView):
    template_name = 'clubs/mes_clubs.html'

class PageMesActivitesView(TemplateView):
    template_name = 'activites/mes_activites.html'

class PageMesPresencesView(TemplateView):
    template_name = 'activites/mes_presences.html'

class PageRecommandationsView(TemplateView):
    template_name = 'clubs/recommandations.html'

class PageParentRecommandationsView(TemplateView):
    template_name = 'parents/recommandations.html'

class PageParentClubsView(TemplateView):
    template_name = 'parents/clubs_enfants.html'


class PageParentActivitesView(TemplateView):
    template_name = 'parents/activites_enfants.html'


class PageParentPresencesView(TemplateView):
    template_name = 'parents/presences_enfants.html'


class PageParentCalendrierView(TemplateView):
    template_name = 'parents/calendrier_enfants.html'
    
class PageInscriptionView(TemplateView):
    template_name = 'base/inscription.html'
    
class PageComptesEnAttenteView(TemplateView):
    template_name = 'base/comptes_en_attente.html'
    
class PageUtilisateursView(TemplateView):
    template_name = 'base/utilisateurs.html'
    
class PageRapportsView(TemplateView):
    template_name = 'base/rapports.html'
    
class PageMotDePasseOublieView(TemplateView):
    template_name = 'base/mot_de_passe_oublie.html'


class PageReinitialiserMotDePasseView(TemplateView):
    template_name = 'base/reinitialiser_mot_de_passe.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['uidb64'] = kwargs.get('uidb64')
        context['token'] = kwargs.get('token')
        return context
    
class PageValidationCompteView(TemplateView):
    template_name = 'base/validation_compte.html'