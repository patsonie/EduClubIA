from django.db import models
from django.conf import settings
from clubs.models import Club


class Activite(models.Model):
    """Représente une activité extrascolaire planifiée par un club."""

    class Statut(models.TextChoices):
        PLANIFIEE = 'planifiee', 'Planifiée'
        VALIDEE = 'validee', 'Validée'
        EN_COURS = 'en_cours', 'En cours'
        TERMINEE = 'terminee', 'Terminée'
        ANNULEE = 'annulee', 'Annulée'

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='activites')
    titre = models.CharField(max_length=200)
    description = models.TextField()
    date = models.DateField()
    heure = models.TimeField()
    lieu = models.CharField(max_length=200)
    budget = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activites_encadrees',
    )
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.PLANIFIEE)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Activité"
        verbose_name_plural = "Activités"
        ordering = ['-date', '-heure']

    def __str__(self):
        return f"{self.titre} ({self.club.nom}) - {self.date}"


class HistoriqueActivite(models.Model):
    """Trace les changements de statut d'une activité (planification, validation, annulation...)."""

    activite = models.ForeignKey(Activite, on_delete=models.CASCADE, related_name='historique')
    ancien_statut = models.CharField(max_length=20, blank=True, null=True)
    nouveau_statut = models.CharField(max_length=20)
    modifie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    date_modification = models.DateTimeField(auto_now_add=True)
    commentaire = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Historique d'activité"
        verbose_name_plural = "Historiques d'activités"
        ordering = ['-date_modification']

    def __str__(self):
        return f"{self.activite.titre}: {self.ancien_statut} → {self.nouveau_statut}"