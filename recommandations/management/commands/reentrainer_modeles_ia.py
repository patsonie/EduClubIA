"""
Commande de réentraînement des modèles IA, destinée à être planifiée
(Hebdomadaire ou Automatique) via le Planificateur de tâches Windows,
ou exécutée manuellement en ligne de commande.

Usage :
    python manage.py reentrainer_modeles_ia --type hebdomadaire
    python manage.py reentrainer_modeles_ia --type automatique
    python manage.py reentrainer_modeles_ia               (par défaut : manuel)
"""

import json
import time
from django.core.management.base import BaseCommand
from recommandations.models import HistoriqueEntrainement
from recommandations.ml_pipeline import (
    entrainer_modele_content_based, valider_modele_content_based,
    entrainer_modele_collaboratif, valider_modele_collaboratif,
)
from analytics.ml_pipeline import entrainer_modele_participation, valider_modele_participation


class Command(BaseCommand):
    help = "Réentraîne et valide les modèles IA (recommandations + prédiction de participation)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--type', type=str, default='manuel',
            choices=['manuel', 'hebdomadaire', 'automatique'],
            help="Type de déclenchement à enregistrer dans l'historique.",
        )

    def handle(self, *args, **options):
        type_declenchement = options['type']
        debut = time.time()
        resultats = {}

        self.stdout.write(self.style.NOTICE(f"Démarrage de l'entraînement ({type_declenchement})..."))

        try:
            self.stdout.write("→ Entraînement content-based...")
            resultats['content_based'] = entrainer_modele_content_based()
            resultats['validation_content_based'] = valider_modele_content_based()

            self.stdout.write("→ Entraînement collaboratif (KNN)...")
            resultats['collaboratif'] = entrainer_modele_collaboratif()
            resultats['validation_collaboratif'] = valider_modele_collaboratif()

            self.stdout.write("→ Entraînement prédiction de participation...")
            resultats['participation'] = entrainer_modele_participation()
            resultats['validation_participation'] = valider_modele_participation()

            duree = round(time.time() - debut, 2)

            HistoriqueEntrainement.objects.create(
                type_declenchement=type_declenchement,
                statut=HistoriqueEntrainement.Statut.SUCCES,
                metriques=json.dumps(resultats, default=str),
                duree_secondes=duree,
            )

            self.stdout.write(self.style.SUCCESS(f"Entraînement terminé avec succès en {duree}s."))
            for cle, valeur in resultats.items():
                self.stdout.write(f"  {cle} : {valeur}")

        except Exception as e:
            duree = round(time.time() - debut, 2)
            HistoriqueEntrainement.objects.create(
                type_declenchement=type_declenchement,
                statut=HistoriqueEntrainement.Statut.ECHEC,
                message_erreur=str(e),
                duree_secondes=duree,
            )
            self.stderr.write(self.style.ERROR(f"Échec de l'entraînement : {e}"))