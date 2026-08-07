from django.db import models
from django.conf import settings
from activites.models import Activite
from inscriptions.models import Inscription


class Participation(models.Model):
    """Enregistre la présence (ou absence) d'un élève inscrit à une activité de son club."""

    class Statut(models.TextChoices):
        PRESENT = 'present', 'Présent'
        ABSENT = 'absent', 'Absent'
        EXCUSE = 'excuse', 'Absence excusée'
        RETARD = 'retard', 'En retard'

    inscription = models.ForeignKey(
        Inscription, on_delete=models.CASCADE, related_name='participations'
    )
    activite = models.ForeignKey(
        Activite, on_delete=models.CASCADE, related_name='participations'
    )
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.PRESENT)
    date_enregistrement = models.DateTimeField(auto_now_add=True)
    enregistre_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    commentaire = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Participation"
        verbose_name_plural = "Participations"
        ordering = ['-date_enregistrement']
        constraints = [
            models.UniqueConstraint(
                fields=['inscription', 'activite'],
                name='participation_unique_par_activite',
            )
        ]

    def __str__(self):
        return f"{self.inscription.eleve.nom_complet} - {self.activite.titre} ({self.get_statut_display()})"