from django.db import models
from django.conf import settings


class Club(models.Model):
    """Représente un club scolaire avec ses caractéristiques principales."""

    # Catégories de club (aussi utilisées par les centres d'intérêt et les recommandations IA).
    class Categorie(models.TextChoices):
        SCIENTIFIQUE = 'scientifique', 'Scientifique'
        SPORTIF = 'sportif', 'Sportif'
        CULTUREL = 'culturel', 'Culturel'
        ARTISTIQUE = 'artistique', 'Artistique'
        TECHNOLOGIQUE = 'technologique', 'Technologique'
        HUMANITAIRE = 'humanitaire', 'Humanitaire'
        AUTRE = 'autre', 'Autre'

    # Cycle de vie d'un club : seuls les clubs « actif » acceptent des inscriptions.
    class Statut(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        INACTIF = 'inactif', 'Inactif'
        EN_ATTENTE = 'en_attente', 'En attente de validation'
        ARCHIVE = 'archive', 'Archivé'

    # --- Informations du club ---
    nom = models.CharField(max_length=150, unique=True)
    description = models.TextField()
    categorie = models.CharField(max_length=20, choices=Categorie.choices, default=Categorie.AUTRE)
    objectifs = models.TextField(help_text="Objectifs pédagogiques et éducatifs du club")
    # Encadreur responsable : un seul par club (vide = club disponible pour un encadreur).
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clubs_encadres',
        limit_choices_to={'role': 'encadreur'},
    )
    date_creation = models.DateField(auto_now_add=True)
    nombre_max_membres = models.PositiveIntegerField(default=30)
    # Logo : dossier public (affiché sans authentification).
    logo = models.ImageField(upload_to='clubs/logos/', blank=True, null=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)

    class Meta:
        verbose_name = "Club"
        verbose_name_plural = "Clubs"
        ordering = ['nom']

    def __str__(self):
        return self.nom

    # Nombre de membres validés (valeur pré-calculée par la vue si disponible, sinon requête).
    @property
    def nombre_membres_actuels(self):
        annote = getattr(self, 'membres_annotes', None)
        if annote is not None:
            return annote
        return self.inscriptions.filter(statut='validee').count()

    # Places restantes (jamais négatif).
    @property
    def places_disponibles(self):
        return max(self.nombre_max_membres - self.nombre_membres_actuels, 0)