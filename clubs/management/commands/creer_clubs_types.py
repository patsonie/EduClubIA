"""
Crée les clubs types de l'établissement (même liste que docs/Liste_des_clubs_EduClubIA.docx).

    python manage.py creer_clubs_types               # clubs créés au statut « actif »
    python manage.py creer_clubs_types --en-attente  # clubs créés au statut « en attente »
    python manage.py creer_clubs_types --simulation  # affiche ce qui serait fait, sans rien écrire

Un club dont le nom existe déjà n'est ni recréé ni modifié : la commande peut être relancée sans risque.
Les clubs sont créés sans encadreur : chaque encadreur choisit le sien à l'inscription.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from clubs.models import Club

C = Club.Categorie

# Liste des clubs : nom, catégorie, description, objectifs, activités proposées.
# Pour ajouter un club, ajouter une entrée ici puis relancer la commande.
CLUBS_TYPES = [
    ("Club Scientifique", C.SCIENTIFIQUE,
     "Espace d'expérimentation où les élèves explorent la physique, la chimie et les sciences de la vie par la pratique, en dehors du cadre strict du programme.",
     ["Développer la démarche expérimentale et l'esprit critique", "Renforcer la compréhension des notions vues en classe", "Préparer les élèves aux concours et olympiades scientifiques"],
     ["Ateliers d'expériences (fabrication d'un volcan, électrolyse de l'eau, extraction d'ADN de banane)", "Préparation d'un stand pour la journée scientifique de l'établissement"]),
    ("Club Mathématiques", C.SCIENTIFIQUE,
     "Club consacré au raisonnement logique, à la résolution de problèmes et aux jeux mathématiques.",
     ["Donner le goût des mathématiques par le jeu et le défi", "Entraîner les élèves aux olympiades nationales de mathématiques", "Favoriser l'entraide entre élèves de niveaux différents"],
     ["Défi mathématique hebdomadaire avec classement", "Séances de préparation aux olympiades de mathématiques"]),
    ("Club Informatique et Robotique", C.TECHNOLOGIQUE,
     "Initiation à la programmation, à l'électronique et à la robotique à partir de cartes Arduino et de logiciels libres.",
     ["Initier les élèves à la programmation (Scratch, Python)", "Découvrir l'électronique et la robotique", "Encourager la création de solutions numériques à des problèmes locaux"],
     ["Construction d'un robot suiveur de ligne", "Hackathon : créer une application utile pour le lycée"]),
    ("Club Environnement", C.SCIENTIFIQUE,
     "Club engagé pour la protection de l'environnement, la propreté de l'établissement et la sensibilisation au développement durable.",
     ["Sensibiliser au tri des déchets et à la protection de la nature", "Améliorer le cadre de vie du lycée", "Promouvoir des gestes éco-citoyens dans la communauté"],
     ["Campagne de reboisement et entretien d'un jardin scolaire", "Journée de salubrité et de tri des déchets dans l'établissement"]),
    ("Club Football", C.SPORTIF,
     "Club sportif qui réunit les passionnés de football autour d'entraînements réguliers et de compétitions inter-établissements.",
     ["Développer la condition physique et l'esprit d'équipe", "Apprendre le respect des règles et de l'arbitre", "Représenter le lycée aux championnats scolaires (FENASSCO)"],
     ["Entraînements techniques et tactiques deux fois par semaine", "Tournoi inter-classes en fin de trimestre"]),
    ("Club Handball et Basketball", C.SPORTIF,
     "Club de sports collectifs en salle ou sur terrain, ouvert aux filles comme aux garçons.",
     ["Pratiquer une activité physique régulière", "Promouvoir la mixité et le fair-play", "Préparer les équipes aux jeux scolaires"],
     ["Séances d'initiation et de perfectionnement", "Match amical contre un lycée voisin"]),
    ("Club Athlétisme", C.SPORTIF,
     "Club axé sur la course, le saut et le lancer, pour améliorer ses performances individuelles.",
     ["Améliorer l'endurance, la vitesse et la coordination", "Apprendre à se fixer des objectifs et à les suivre", "Détecter les talents pour les compétitions scolaires"],
     ["Séances d'entraînement avec suivi des chronos", "Cross du lycée ouvert à tous les élèves"]),
    ("Club Théâtre", C.ARTISTIQUE,
     "Atelier d'expression scénique où les élèves travaillent la diction, l'improvisation et la mise en scène.",
     ["Développer l'aisance à l'oral et la confiance en soi", "Découvrir des œuvres du répertoire africain et mondial", "Travailler en troupe autour d'un projet commun"],
     ["Exercices d'improvisation et de diction", "Création et représentation d'une pièce lors de la fête de fin d'année"]),
    ("Club Musique et Chorale", C.ARTISTIQUE,
     "Club de chant et de pratique instrumentale qui anime les cérémonies de l'établissement.",
     ["Initier au chant choral et aux instruments", "Valoriser les musiques traditionnelles camerounaises", "Animer la vie culturelle du lycée"],
     ["Répétitions de la chorale (hymne national, chants patriotiques et traditionnels)", "Concert lors de la Fête de la Jeunesse (11 février)"]),
    ("Club Arts Plastiques", C.ARTISTIQUE,
     "Club de dessin, peinture, sculpture et artisanat, ouvert à tous les niveaux.",
     ["Développer la créativité et le sens esthétique", "Découvrir les techniques artisanales locales", "Embellir les espaces de l'établissement"],
     ["Réalisation d'une fresque murale dans la cour", "Exposition-vente des œuvres des élèves"]),
    ("Club Journal et Médias", C.CULTUREL,
     "Rédaction du journal du lycée, reportages photo et initiation au journalisme responsable.",
     ["Améliorer l'expression écrite en français et en anglais", "Apprendre à vérifier l'information et à lutter contre les fausses nouvelles", "Informer la communauté scolaire"],
     ["Publication d'un journal trimestriel du lycée", "Atelier « vrai ou faux » sur les informations circulant sur les réseaux sociaux"]),
    ("Club Bilingue et Débat", C.CULTUREL,
     "Club de pratique de l'anglais et du français à travers le débat, l'art oratoire et les échanges.",
     ["Promouvoir le bilinguisme officiel du Cameroun", "Développer l'argumentation et l'écoute", "Préparer les concours d'éloquence"],
     ["Débats hebdomadaires sur des sujets de société", "Concours d'éloquence bilingue"]),
    ("Club Culture et Patrimoine", C.CULTUREL,
     "Club de découverte des cultures, langues, danses et traditions des différentes régions du Cameroun.",
     ["Valoriser la diversité culturelle nationale", "Favoriser le vivre-ensemble entre élèves d'origines différentes", "Transmettre les contes, danses et savoir-faire traditionnels"],
     ["Journée culturelle avec danses, tenues et mets traditionnels", "Veillée de contes animée par un ancien de la communauté"]),
    ("Club Santé et Secourisme", C.HUMANITAIRE,
     "Club d'éducation à la santé et d'initiation aux premiers secours, en lien avec l'infirmerie du lycée.",
     ["Apprendre les gestes de premiers secours", "Sensibiliser à l'hygiène, au paludisme et aux IST", "Créer une équipe relais lors des événements sportifs"],
     ["Formation aux gestes qui sauvent (PLS, massage cardiaque, pansements)", "Campagne de sensibilisation contre le paludisme"]),
    ("Club Solidarité", C.HUMANITAIRE,
     "Club d'entraide et d'actions sociales au profit des élèves en difficulté et de la communauté.",
     ["Développer l'esprit de solidarité et de citoyenneté", "Soutenir les élèves en difficulté scolaire ou matérielle", "Mener des actions au service de la communauté"],
     ["Collecte de fournitures scolaires pour les élèves démunis", "Visite et dons dans un orphelinat ou un centre social"]),
    ("Club Entrepreneuriat", C.AUTRE,
     "Club d'initiation à la gestion de projet et à la création de petites activités économiques.",
     ["Développer l'esprit d'initiative et d'entreprise", "Apprendre à monter et gérer un projet simple", "Découvrir des métiers et des parcours de réussite"],
     ["Mini-entreprise : production et vente d'un produit (savon, jus naturel)", "Rencontre avec un entrepreneur local"]),
]


class Command(BaseCommand):
    help = "Crée les clubs types (description, objectifs, activités) s'ils n'existent pas encore."

    def add_arguments(self, parser):
        parser.add_argument('--en-attente', action='store_true',
                            help="Créer les clubs au statut « en attente » plutôt qu'« actif ».")
        parser.add_argument('--simulation', action='store_true',
                            help="Afficher ce qui serait créé sans rien enregistrer.")

    def handle(self, *args, **options):
        statut = Club.Statut.EN_ATTENTE if options['en_attente'] else Club.Statut.ACTIF
        existants = {nom.lower() for nom in Club.objects.values_list('nom', flat=True)}
        crees = ignores = 0

        with transaction.atomic():
            for nom, categorie, description, objectifs, activites in CLUBS_TYPES:
                if nom.lower() in existants:
                    ignores += 1
                    self.stdout.write(f"  déjà présent : {nom}")
                    continue
                # Les activités types sont ajoutées à la description (le modèle n'a pas de champ dédié).
                texte_description = description + "\n\nActivités proposées :\n" + "\n".join(f"- {a}" for a in activites)
                texte_objectifs = "\n".join(f"- {o}" for o in objectifs)
                if not options['simulation']:
                    Club.objects.create(
                        nom=nom, categorie=categorie, description=texte_description,
                        objectifs=texte_objectifs, statut=statut,
                    )
                crees += 1
                self.stdout.write(f"  {'à créer' if options['simulation'] else 'créé'} : {nom}")

        bilan = f"{crees} club(s) {'à créer' if options['simulation'] else 'créé(s)'}, {ignores} déjà présent(s)."
        self.stdout.write(self.style.SUCCESS(bilan))
