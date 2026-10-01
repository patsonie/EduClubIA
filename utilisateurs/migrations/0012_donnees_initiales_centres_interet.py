import unicodedata

from django.db import migrations

# (catégorie, [(centre d'intérêt, catégorie de club correspondante)])
CATALOGUE = [
    ("Sciences et technologie", [("Sciences", "scientifique"), ("Mathématiques", "scientifique"),
                                 ("Robotique", "technologique")]),
    ("Informatique et numérique", [("Informatique", "technologique"), ("Programmation", "technologique"),
                                   ("Intelligence artificielle", "technologique")]),
    ("Arts et créativité", [("Dessin et peinture", "artistique"), ("Théâtre", "artistique")]),
    ("Sport", [("Football", "sportif"), ("Basketball", "sportif"), ("Athlétisme", "sportif")]),
    ("Communication", [("Journalisme", "culturel"), ("Débat et éloquence", "culturel")]),
    ("Culture", [("Culture générale", "culturel"), ("Histoire", "culturel")]),
    ("Lecture", [("Lecture", "culturel"), ("Écriture", "culturel")]),
    ("Environnement", [("Environnement", "humanitaire"), ("Écologie", "humanitaire")]),
    ("Entrepreneuriat", [("Entrepreneuriat", "")]),
    ("Leadership", [("Leadership", "")]),
    ("Sciences humaines et sociales", [("Droits humains", "humanitaire"), ("Action sociale", "humanitaire")]),
    ("Agriculture", [("Agriculture", "scientifique")]),
    ("Musique", [("Musique", "artistique"), ("Chant", "artistique"), ("Danse", "artistique")]),
    ("Langues", [("Langues étrangères", "culturel")]),
]


def _normaliser(texte):
    texte = unicodedata.normalize('NFKD', texte or '')
    return ''.join(c for c in texte if not unicodedata.combining(c)).lower().strip()


def creer_centres_initiaux(apps, schema_editor):
    """get_or_create : rejouable sans doublon, ne supprime ni ne modifie l'existant."""
    Categorie = apps.get_model('utilisateurs', 'CategorieInteret')
    Centre = apps.get_model('utilisateurs', 'CentreInteret')
    Utilisateur = apps.get_model('utilisateurs', 'Utilisateur')

    for ordre, (nom_categorie, centres) in enumerate(CATALOGUE):
        categorie, _ = Categorie.objects.get_or_create(nom=nom_categorie, defaults={'ordre': ordre})
        for nom, categorie_club in centres:
            Centre.objects.get_or_create(
                nom=nom, defaults={'categorie': categorie, 'categorie_club': categorie_club},
            )
    Categorie.objects.get_or_create(nom="Autres", defaults={'ordre': len(CATALOGUE)})

    # Reprise des anciens textes libres : seuls les termes correspondant exactement à un centre sont reliés.
    par_nom = {_normaliser(c.nom): c for c in Centre.objects.all()}
    for utilisateur in Utilisateur.objects.exclude(centres_interet__isnull=True).exclude(centres_interet=''):
        for terme in utilisateur.centres_interet.split(','):
            centre = par_nom.get(_normaliser(terme))
            if centre:
                utilisateur.interets.add(centre)


class Migration(migrations.Migration):

    dependencies = [
        ('utilisateurs', '0011_centres_interet'),
    ]

    operations = [
        migrations.RunPython(creer_centres_initiaux, migrations.RunPython.noop),
    ]
