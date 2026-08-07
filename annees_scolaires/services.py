def archiver_inscriptions_annee_precedente(nouvelle_annee):
    """
    Archive automatiquement toutes les inscriptions actives des années
    scolaires précédentes lorsqu'une nouvelle année devient active.

    Import différé de Inscription pour éviter une dépendance circulaire
    entre les apps annees_scolaires et inscriptions.
    """
    from inscriptions.models import Inscription

    Inscription.objects.filter(
        annee_scolaire__est_active=False,
    ).exclude(
        statut='archivee'
    ).update(statut='archivee')