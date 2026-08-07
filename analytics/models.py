from django.db import models
from django.conf import settings
from clubs.models import Club
from activites.models import Activite


class RisqueDesengagement(models.Model):
    """Score de risque qu'un élève quitte son club, calculé à partir de son comportement."""

    class NiveauRisque(models.TextChoices):
        FAIBLE = 'faible', 'Faible'
        MOYEN = 'moyen', 'Moyen'
        ELEVE = 'eleve', 'Élevé'

    eleve = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='risques_desengagement'
    )
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='risques_desengagement')
    score_risque = models.FloatField(help_text="Probabilité de désengagement, de 0 à 100")
    niveau = models.CharField(max_length=10, choices=NiveauRisque.choices)
    date_calcul = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Risque de désengagement"
        verbose_name_plural = "Risques de désengagement"
        constraints = [
            models.UniqueConstraint(fields=['eleve', 'club'], name='risque_unique_par_club')
        ]

    def __str__(self):
        return f"{self.eleve.nom_complet} - {self.club.nom} : {self.niveau} ({self.score_risque}%)"


class PredictionParticipation(models.Model):
    """Nombre d'élèves prévus pour une activité future."""

    activite = models.OneToOneField(
        Activite, on_delete=models.CASCADE, related_name='prediction_participation'
    )
    nombre_prevu = models.PositiveIntegerField()
    date_calcul = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Prédiction de participation"
        verbose_name_plural = "Prédictions de participation"

    def __str__(self):
        return f"{self.activite.titre} : {self.nombre_prevu} participants prévus"


class ClubEnDifficulte(models.Model):
    """Club identifié comme ayant une baisse d'activité significative."""

    club = models.OneToOneField(Club, on_delete=models.CASCADE, related_name='alerte_difficulte')
    score_difficulte = models.FloatField(help_text="Score de difficulté, de 0 à 100")
    raison = models.TextField()
    date_calcul = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Club en difficulté"
        verbose_name_plural = "Clubs en difficulté"

    def __str__(self):
        return f"{self.club.nom} : difficulté {self.score_difficulte}%"