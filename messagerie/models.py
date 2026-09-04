from django.db import models
from django.conf import settings
from clubs.models import Club
from activites.models import Activite
from utilisateurs.validators import valider_fichier_message


class SalonDiscussion(models.Model):
    """
    Salon de discussion temps réel. Trois types possibles :
    - CLUB : salon collectif lié à un club (auto-créé)
    - ACTIVITE : salon collectif lié à une activité (auto-créé)
    - PRIVE : conversation privée à deux (ex: parent ↔ encadreur), créée à la demande
    """

    class TypeSalon(models.TextChoices):
        CLUB = 'club', 'Club'
        ACTIVITE = 'activite', 'Activité'
        PRIVE = 'prive', 'Conversation privée'

    type_salon = models.CharField(max_length=10, choices=TypeSalon.choices, default=TypeSalon.CLUB)
    club = models.OneToOneField(
        Club, on_delete=models.CASCADE, related_name='salon', blank=True, null=True
    )
    activite = models.OneToOneField(
        Activite, on_delete=models.CASCADE, related_name='salon', blank=True, null=True
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='salons_prives',
        help_text="Utilisé uniquement pour les salons de type 'prive'",
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Salon de discussion"
        verbose_name_plural = "Salons de discussion"

    def __str__(self):
        if self.type_salon == self.TypeSalon.CLUB and self.club:
            return f"Salon du club {self.club.nom}"
        if self.type_salon == self.TypeSalon.ACTIVITE and self.activite:
            return f"Salon de l'activité {self.activite.titre}"
        return f"Conversation privée #{self.id}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.type_salon == self.TypeSalon.CLUB and not self.club:
            raise ValidationError("Un salon de type 'club' doit être lié à un club.")
        if self.type_salon == self.TypeSalon.ACTIVITE and not self.activite:
            raise ValidationError("Un salon de type 'activite' doit être lié à une activité.")

    @property
    def nom_affiche(self):
        if self.club:
            return self.club.nom
        if self.activite:
            return self.activite.titre
        noms = [p.nom_complet for p in self.participants.all()]
        return " & ".join(noms) if noms else f"Conversation #{self.id}"


class Message(models.Model):
    """Message envoyé dans un salon de discussion, avec pièce jointe optionnelle."""

    salon = models.ForeignKey(SalonDiscussion, on_delete=models.CASCADE, related_name='messages')
    expediteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='messages_envoyes'
    )
    contenu = models.TextField(blank=True)
    fichier = models.FileField(
        upload_to='messagerie/fichiers/', blank=True, null=True,
        validators=[valider_fichier_message],
    )
    date_envoi = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ['date_envoi']

    def __str__(self):
        return f"{self.expediteur.nom_complet} @ {self.salon} : {self.contenu[:30]}"
