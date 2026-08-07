from django.db.models.signals import post_save
from django.dispatch import receiver
from clubs.models import Club
from activites.models import Activite
from .models import SalonDiscussion


@receiver(post_save, sender=Club)
def creer_salon_pour_club(sender, instance, created, **kwargs):
    if created:
        SalonDiscussion.objects.create(club=instance)


@receiver(post_save, sender=Activite)
def creer_salon_pour_activite(sender, instance, created, **kwargs):
    if created:
        SalonDiscussion.objects.create(activite=instance)