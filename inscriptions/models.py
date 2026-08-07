from django.db import models
from django.conf import settings
from clubs.models import Club
from annees_scolaires.models import AnneeScolaire


class Inscription(models.Model):
    """Représente l'inscription d'un élève à un club pour une année scolaire donnée."""

    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente de validation'
        VALIDEE = 'validee', 'Validée'
        REFUSEE = 'refusee', 'Refusée'
        ANNULEE = 'annulee', 'Annulée (désinscription)'
        ARCHIVEE = 'archivee', 'Archivée'

    eleve = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='inscriptions',
        limit_choices_to={'role': 'eleve'},
    )
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='inscriptions')
    annee_scolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.PROTECT, related_name='inscriptions'
    )
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)
    date_inscription = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(blank=True, null=True)
    traite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inscriptions_traitees',
    )

    class Meta:
        verbose_name = "Inscription"
        verbose_name_plural = "Inscriptions"
        ordering = ['-date_inscription']
        constraints = [
            models.UniqueConstraint(
                fields=['eleve', 'club', 'annee_scolaire'],
                name='inscription_unique_par_annee',
            )
        ]

    def __str__(self):
        return f"{self.eleve.nom_complet} → {self.club.nom} ({self.annee_scolaire.libelle})"


class HistoriqueInscription(models.Model):
    """Trace les changements de statut d'une inscription."""

    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name='historique')
    ancien_statut = models.CharField(max_length=20, blank=True, null=True)
    nouveau_statut = models.CharField(max_length=20)
    modifie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    date_modification = models.DateTimeField(auto_now_add=True)
    commentaire = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Historique d'inscription"
        verbose_name_plural = "Historiques d'inscriptions"
        ordering = ['-date_modification']

    def __str__(self):
        return f"{self.inscription} : {self.ancien_statut} → {self.nouveau_statut}"