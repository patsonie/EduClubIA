from django.core.management.base import BaseCommand
from utilisateurs.models import Utilisateur


class Command(BaseCommand):
    help = "Convertit les matricules vides ('') en NULL pour éviter les faux conflits d'unicité."

    def handle(self, *args, **options):
        nombre = Utilisateur.objects.filter(matricule='').update(matricule=None)
        self.stdout.write(self.style.SUCCESS(f"{nombre} compte(s) corrigé(s)."))