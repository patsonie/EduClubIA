from django.utils import timezone
from .models import Utilisateur


def demander_rattachement_par_matricule(parent, matricule):
    """
    Enregistre une demande de rattachement à partir du matricule saisi par un parent.
    La demande est créée QUE le matricule existe ou non : le parent voit la même chose
    dans les deux cas (pas de moyen de tester des matricules). Si un élève porte ce
    matricule, il est pré-désigné pour le gestionnaire, qui reste seul à valider le lien.
    Retourne la demande créée, ou None si une demande identique est déjà en attente
    ou si le lien existe déjà.
    """
    from .models import DemandeRattachement, RelationParentEleve
    from notifications.models import Notification
    from notifications.services import creer_notification

    matricule = (matricule or '').strip()
    if not matricule:
        return None
    libelle = f"Matricule {matricule.upper()}"

    # Une seule demande en attente par matricule et par parent.
    if DemandeRattachement.objects.filter(
        parent=parent, nom_complet_enfant__iexact=libelle, statut=DemandeRattachement.Statut.EN_ATTENTE,
    ).exists():
        return None

    enfant = Utilisateur.objects.filter(
        role=Utilisateur.Role.ELEVE, matricule__iexact=matricule,
    ).exclude(statut_validation=Utilisateur.StatutValidation.REFUSE).first()
    # Enfant déjà rattaché (ou lien déjà en cours) : rien de nouveau à demander.
    if enfant and RelationParentEleve.objects.filter(parent=parent, enfant=enfant).exists():
        return None

    demande = DemandeRattachement.objects.create(parent=parent, nom_complet_enfant=libelle, enfant=enfant)

    # Les responsables pédagogiques sont prévenus qu'une demande attend leur décision.
    for gestionnaire in Utilisateur.objects.filter(
        role=Utilisateur.Role.PROVISEUR, statut_validation=Utilisateur.StatutValidation.VALIDE, is_active=True,
    ):
        creer_notification(
            gestionnaire, Notification.TypeNotification.AUTRE,
            "Demande de rattachement parent",
            f"{parent.nom_complet} demande à être rattaché(e) à l'élève de {libelle.lower()}.",
        )
    return demande


def construire_dashboard_parent(parent):
    """
    Construit les données du tableau de bord d'un parent : pour chaque enfant,
    ses clubs, ses activités à venir, son taux de présence/absence, ses dernières
    notifications et ses recommandations IA.
    """
    # Imports locaux pour éviter les dépendances circulaires entre applications.
    from inscriptions.models import Inscription
    from activites.models import Activite
    from participations.models import Participation
    from notifications.models import Notification
    from recommandations.services import calculer_recommandations_hybrides

    enfants_data = []

    # Pour chaque enfant au lien validé : clubs, activités à venir, présences, notifications, IA.
    for enfant in parent.enfants:
        inscriptions = Inscription.objects.filter(eleve=enfant, statut=Inscription.Statut.VALIDEE)
        clubs = [i.club for i in inscriptions]
        clubs_ids = [c.id for c in clubs]

        # Activités à venir (10 maximum) des clubs de l'enfant, hors activités annulées.
        activites_a_venir = Activite.objects.filter(
            club_id__in=clubs_ids,
            date__gte=timezone.now().date(),
        ).exclude(statut=Activite.Statut.ANNULEE).order_by('date')[:10]

        # Statistiques de présence : « excusé » est compté comme une absence.
        participations = Participation.objects.filter(inscription__eleve=enfant)
        total_participations = participations.count()
        presences = participations.filter(statut=Participation.Statut.PRESENT).count()
        absences = participations.filter(
            statut__in=[Participation.Statut.ABSENT, Participation.Statut.EXCUSE]
        ).count()
        taux_presence = round((presences / total_participations * 100), 2) if total_participations else None

        notifications_recentes = Notification.objects.filter(destinataire=enfant).order_by('-date_creation')[:5]

        recommandations = calculer_recommandations_hybrides(enfant, top_n=5)

        # Données envoyées au navigateur pour cet enfant.
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

    # Demandes de rattachement encore en attente (par matricule ou par nom).
    from .models import RelationParentEleve, DemandeRattachement
    demandes = RelationParentEleve.objects.filter(
        parent=parent, statut=RelationParentEleve.Statut.EN_ATTENTE
    ).select_related('enfant')
    demandes_nominatives = DemandeRattachement.objects.filter(
        parent=parent, statut=DemandeRattachement.Statut.EN_ATTENTE
    ).values_list('nom_complet_enfant', flat=True)

    return {
        "nombre_enfants": len(enfants_data),
        "enfants": enfants_data,
        "demandes_en_attente": [d.enfant.nom_complet for d in demandes] + list(demandes_nominatives),
    }