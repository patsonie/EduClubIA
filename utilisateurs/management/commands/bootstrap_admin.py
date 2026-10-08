"""
Crée automatiquement un compte administrateur à partir de variables
d'environnement, si aucun n'existe encore. Conçu pour être exécuté à chaque
déploiement (build.sh) sans risque de duplication.

Variables d'environnement nécessaires :
    ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NOM, ADMIN_PRENOM
"""

import os
from django.core.management.base import BaseCommand
from utilisateurs.models import Utilisateur


class Command(BaseCommand):
    help = "Crée un compte administrateur à partir de variables d'environnement, si aucun n'existe."

    def handle(self, *args, **options):
        # Lecture des identifiants dans les variables d'environnement (jamais dans le code).
        email = os.environ.get('ADMIN_EMAIL')
        password = os.environ.get('ADMIN_PASSWORD')
        nom = os.environ.get('ADMIN_NOM', 'Administrateur')
        prenom = os.environ.get('ADMIN_PRENOM', 'Principal')

        # Sans email ou mot de passe : on ne fait rien.
        if not email or not password:
            self.stdout.write(self.style.WARNING(
                "ADMIN_EMAIL ou ADMIN_PASSWORD non défini(s) — aucun superutilisateur créé."
            ))
            return

        # Si un administrateur existe déjà : on ne fait rien non plus.
        if Utilisateur.objects.filter(role=Utilisateur.Role.ADMINISTRATEUR).exists():
            self.stdout.write(self.style.NOTICE(
                "Un compte administrateur existe déjà — aucune action nécessaire."
            ))
            return

        # Création du premier administrateur.
        Utilisateur.objects.create_superuser(
            email=email, password=password, nom=nom, prenom=prenom,
        )
        self.stdout.write(self.style.SUCCESS(f"Superutilisateur créé : {email}"))