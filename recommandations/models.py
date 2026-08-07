from django.db import models
from django.conf import settings
from clubs.models import Club


class Recommandation(models.Model):
    """
    Stocke le résultat du calcul de recommandation d'un club pour un élève.
    Recalculée périodiquement par le moteur IA (content-based filtering).
    """

    eleve = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='recommandations',
        limit_choices_to={'role': 'eleve'},
    )
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='recommandations')
    score = models.FloatField(help_text="Score de compatibilité en pourcentage (0 à 100)")
    explication = models.TextField(help_text="Explication lisible de la recommandation")
    date_calcul = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Recommandation"
        verbose_name_plural = "Recommandations"
        ordering = ['-score']
        constraints = [
            models.UniqueConstraint(fields=['eleve', 'club'], name='recommandation_unique_par_club')
        ]

    def __str__(self):
        return f"{self.eleve.nom_complet} → {self.club.nom} ({self.score}%)"
    
class HistoriqueEntrainement(models.Model):
    """Trace chaque exécution du pipeline d'entraînement des modèles IA."""

    class TypeDeclenchement(models.TextChoices):
        MANUEL = 'manuel', 'Manuel'
        HEBDOMADAIRE = 'hebdomadaire', 'Hebdomadaire'
        AUTOMATIQUE = 'automatique', 'Automatique'

    class Statut(models.TextChoices):
        SUCCES = 'succes', 'Succès'
        ECHEC = 'echec', 'Échec'

    type_declenchement = models.CharField(max_length=15, choices=TypeDeclenchement.choices)
    statut = models.CharField(max_length=10, choices=Statut.choices)
    metriques = models.TextField(help_text="Résultats de validation au format JSON", blank=True)
    message_erreur = models.TextField(blank=True, null=True)
    declenche_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    date_entrainement = models.DateTimeField(auto_now_add=True)
    duree_secondes = models.FloatField(default=0)

    class Meta:
        verbose_name = "Historique d'entraînement IA"
        verbose_name_plural = "Historique des entraînements IA"
        ordering = ['-date_entrainement']

    def __str__(self):
        return f"Entraînement {self.get_type_declenchement_display()} du {self.date_entrainement:%d/%m/%Y %H:%M} — {self.statut}"