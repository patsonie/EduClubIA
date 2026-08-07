from django.db import models
from django.conf import settings


class Notification(models.Model):
    """Notification interne adressée à un utilisateur."""

    class TypeNotification(models.TextChoices):
        NOUVELLE_ACTIVITE = 'nouvelle_activite', 'Nouvelle activité'
        VALIDATION_INSCRIPTION = 'validation_inscription', "Validation d'inscription"
        REFUS_INSCRIPTION = 'refus_inscription', "Refus d'inscription"
        RAPPEL_ACTIVITE = 'rappel_activite', "Rappel d'activité"
        RECOMMANDATION_IA = 'recommandation_ia', 'Recommandation IA'
        ALERTE_DESENGAGEMENT = 'alerte_desengagement', 'Alerte de désengagement'
        AUTRE = 'autre', 'Autre'

    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications'
    )
    type_notification = models.CharField(max_length=30, choices=TypeNotification.choices)
    titre = models.CharField(max_length=200)
    message = models.TextField()
    lu = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_lecture = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-date_creation']

    def __str__(self):
        return f"{self.destinataire.nom_complet} - {self.titre}"


class PreferenceNotification(models.Model):
    """Préférences de canal de notification par utilisateur."""

    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='preference_notification'
    )
    notifications_internes = models.BooleanField(default=True)
    notifications_email = models.BooleanField(default=True)
    notifications_sms = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Préférence de notification"
        verbose_name_plural = "Préférences de notification"

    def __str__(self):
        return f"Préférences de {self.utilisateur.nom_complet}"