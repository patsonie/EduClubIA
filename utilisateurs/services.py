from django.utils import timezone
from .models import Utilisateur


def construire_dashboard_parent(parent):
    """
    Construit les données du tableau de bord d'un parent : pour chaque enfant,
    ses clubs, ses activités à venir, son taux de présence/absence, ses dernières
    notifications et ses recommandations IA.
    """
    from inscriptions.models import Inscription
    from activites.models import Activite
    from participations.models import Participation
    from notifications.models import Notification
    from recommandations.services import calculer_recommandations_hybrides

    enfants_data = []

    for enfant in parent.enfants:
        inscriptions = Inscription.objects.filter(eleve=enfant, statut=Inscription.Statut.VALIDEE)
        clubs = [i.club for i in inscriptions]
        clubs_ids = [c.id for c in clubs]

        activites_a_venir = Activite.objects.filter(
            club_id__in=clubs_ids,
            date__gte=timezone.now().date(),
        ).exclude(statut=Activite.Statut.ANNULEE).order_by('date')[:10]

        participations = Participation.objects.filter(inscription__eleve=enfant)
        total_participations = participations.count()
        presences = participations.filter(statut=Participation.Statut.PRESENT).count()
        absences = participations.filter(
            statut__in=[Participation.Statut.ABSENT, Participation.Statut.EXCUSE]
        ).count()
        taux_presence = round((presences / total_participations * 100), 2) if total_participations else None

        notifications_recentes = Notification.objects.filter(destinataire=enfant).order_by('-date_creation')[:5]

        recommandations = calculer_recommandations_hybrides(enfant, top_n=5)

        enfants_data.append({
            "id": enfant.id,
            "nom_complet": enfant.nom_complet,
            "classe": enfant.classe,
            "clubs": [{"id": c.id, "nom": c.nom, "categorie": c.categorie} for c in clubs],
            "activites_a_venir": [
                {"id": a.id, "titre": a.titre, "date": a.date, "heure": a.heure, "lieu": a.lieu}
                for a in activites_a_venir
            ],
            "taux_presence": taux_presence,
            "total_presences": presences,
            "total_absences": absences,
            "dernieres_notifications": [
                {"id": n.id, "titre": n.titre, "message": n.message, "lu": n.lu, "date": n.date_creation}
                for n in notifications_recentes
            ],
            "recommandations": [
                {"club": r["club"].nom, "score": r["score"], "explication": r["explication"]}
                for r in recommandations
            ],
        })

    return {
        "nombre_enfants": len(enfants_data),
        "enfants": enfants_data,
    }