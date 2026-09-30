"""
Importe la liste officielle des matricules depuis un fichier CSV.

    python manage.py importer_matricules eleves.csv --role eleve
    python manage.py importer_matricules encadreurs.csv --role encadreur

Colonnes : matricule, nom, prenom, classe (facultative) ; séparateur « , » ou « ; ».
Dès qu'une liste existe pour un rôle, l'inscription publique de ce rôle exige un matricule officiel.
"""
from django.core.management.base import BaseCommand, CommandError

from utilisateurs.matricules import importer_csv


class Command(BaseCommand):
    help = "Importe la liste officielle des matricules (CSV)."

    def add_arguments(self, parser):
        parser.add_argument('fichier')
        parser.add_argument('--role', choices=['eleve', 'encadreur'], default='eleve')

    def handle(self, *args, **options):
        try:
            with open(options['fichier'], 'rb') as f:
                resultat = importer_csv(f.read(), options['role'])
        except (OSError, ValueError) as erreur:
            raise CommandError(str(erreur))
        self.stdout.write(self.style.SUCCESS(
            f"{resultat['crees']} créé(s), {resultat['mis_a_jour']} mis à jour."
        ))
        for erreur in resultat['erreurs']:
            self.stderr.write(self.style.WARNING(erreur))
