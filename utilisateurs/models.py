# Imports : classes de base Django pour un utilisateur personnalisé, le modèle Club
# (catégories reprises par les centres d'intérêt), le gestionnaire de création de comptes
# et les validateurs de fichiers (photo, justificatif).
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from clubs.models import Club
from .managers import UtilisateurManager
from django.db.models import Q
from .validators import valider_extension_justificatif, valider_extension_photo, valider_taille_fichier


class Utilisateur(AbstractBaseUser, PermissionsMixin):
    """
    Modèle utilisateur personnalisé pour la plateforme de gestion des clubs.
    Rôles possibles : administrateur, proviseur, encadreur, eleve, parent d'élève.
    """
    # Enregistrement : normalise le matricule avant la sauvegarde en base.
    def save(self, *args, **kwargs):
            # Garantit qu'un matricule vide est stocké comme NULL, jamais comme chaîne
        # vide, pour préserver la contrainte d'unicité sans faux conflits.
        if self.matricule == '':
            self.matricule = None
        super().save(*args, **kwargs)
        
    # Liste des rôles de la plateforme (valeur stockée en base, libellé affiché).
    # Pour ajouter un rôle : l'ajouter ici, puis générer une migration et adapter les permissions.
    class Role(models.TextChoices):
        ADMINISTRATEUR = 'administrateur', 'Administrateur'
        PROVISEUR = 'proviseur', 'Responsable pédagogique'
        ENCADREUR = 'encadreur', 'Encadreur'
        ELEVE = 'eleve', 'Élève'
        PARENT = 'parent', "Parent d'élève"

    # --- Informations communes à tous les comptes ---
    email = models.EmailField(unique=True, max_length=190, verbose_name="Adresse email")
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ELEVE)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    date_naissance = models.DateField(blank=True, null=True)
    classe = models.CharField(max_length=20, blank=True, null=True, help_text="Ex: Terminale D, 3ème A")
    filiere = models.CharField(max_length=50, blank=True, null=True, help_text="Ex: Scientifique, Littéraire")
    # Ancien champ texte libre (conservé pour compatibilité) ; les vrais intérêts sont dans `interets`.
    centres_interet = models.TextField(
        blank=True, null=True,
        help_text="Centres d'intérêt séparés par des virgules (ex: informatique, robotique, lecture)"
    )
    moyenne_generale = models.DecimalField(
        max_digits=4, decimal_places=2, blank=True, null=True,
        help_text="Moyenne générale sur 20"
    )
    # Centres d'intérêt de l'élève : relation plusieurs-à-plusieurs, donc plusieurs choix possibles.
    interets = models.ManyToManyField(
        'CentreInteret', blank=True, related_name='eleves',
        help_text="Centres d'intérêt choisis par l'élève (utilisés par les recommandations IA)"
    )
    profession = models.CharField(max_length=100, blank=True, null=True)
    # Photo de profil : seul dossier d'images publiques avec les logos de clubs.
    photo = models.ImageField(
        upload_to='utilisateurs/photos/', blank=True, null=True,
        validators=[valider_extension_photo, valider_taille_fichier],
    )
    
    # Valeurs possibles du genre.
    class Genre(models.TextChoices):
        MASCULIN = 'M', 'Masculin'
        FEMININ = 'F', 'Féminin'
        AUTRE = 'autre', 'Autre'

    # Deux types d'encadreurs ; tous deux doivent être validés par le responsable pédagogique.
    class TypeEncadreur(models.TextChoices):
        PROFESSIONNEL = 'professionnel', 'Encadreur professionnel'
        VACATAIRE = 'vacataire', 'Encadreur vacataire'

    # Étapes du cycle de vie d'un compte (inscription → validation → actif / refusé / suspendu).
    # CODE_ENVOYE et CODE_VALIDE ne concernent que le responsable pédagogique.
    class StatutValidation(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente de validation'
        CODE_ENVOYE = 'code_envoye', 'Code envoyé'
        CODE_VALIDE = 'code_valide', 'Code validé'
        VALIDE = 'valide', 'Actif'
        REFUSE = 'refuse', 'Refusé'
        SUSPENDU = 'suspendu', 'Suspendu'
        
        
    # --- Identité scolaire / professionnelle et suivi de la validation ---
    genre = models.CharField(max_length=10, choices=Genre.choices, blank=True, null=True)
    matricule = models.CharField(max_length=30, unique=True, blank=True, null=True)
    statut_validation = models.CharField(
        max_length=15, choices=StatutValidation.choices, default=StatutValidation.VALIDE
    )
    # Code de confirmation envoyé par email au responsable pédagogique, avec ses dates de suivi.
    code_validation_compte = models.CharField(max_length=20, blank=True, null=True)
    date_code_envoye = models.DateTimeField(blank=True, null=True)
    date_code_valide = models.DateTimeField(blank=True, null=True) 
    etablissement = models.CharField(max_length=200, blank=True, null=True)
    date_expiration_code = models.DateTimeField(blank=True, null=True)
    

    # Champs spécifiques Encadreur
    type_encadreur = models.CharField(max_length=15, choices=TypeEncadreur.choices, blank=True, null=True)
    fonction = models.CharField(max_length=150, blank=True, null=True)
    domaine_competence = models.CharField(max_length=150, blank=True, null=True)
    club_souhaite = models.CharField(
        max_length=200, blank=True, null=True,
        help_text="Club(s) que l'encadreur souhaite encadrer (renseigné à l'inscription)"
    )
    
    justificatif = models.FileField(
        upload_to='utilisateurs/justificatifs/', blank=True, null=True,
        validators=[valider_extension_justificatif, valider_taille_fichier],
    )

    # Champ spécifique Responsable pédagogique
    service_responsabilite = models.CharField(max_length=150, blank=True, null=True)

    # Champ spécifique Parent
    type_lien_eleve = models.CharField(max_length=20, blank=True, null=True, help_text="Père, Mère, Tuteur, Autre")

    # --- Traçabilité de la décision (qui a validé ou refusé le compte, quand, pourquoi) ---
    motif_refus = models.TextField(blank=True, null=True)
    valide_par = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='comptes_valides'
    )
    date_validation = models.DateTimeField(blank=True, null=True)

    # --- Champs techniques exigés par Django pour l'authentification et l'admin ---
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    # Gestionnaire personnalisé : create_user / create_superuser (voir managers.py).
    objects = UtilisateurManager()

    # La connexion se fait par email (pas de nom d'utilisateur).
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nom', 'prenom']
    
    # Vrai seulement si le compte a été validé : sert à autoriser la connexion.
    @property
    def compte_actif_utilisable(self):
        return self.statut_validation == self.StatutValidation.VALIDE

    # Métadonnées : noms affichés dans l'admin et contrainte d'unicité.
    # La contrainte garantit un seul responsable pédagogique (non refusé) par établissement.
    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        
        constraints = [
            models.UniqueConstraint(
                fields=['etablissement'],
                condition=Q(role='proviseur') & Q(statut_validation__in=[
                    'en_attente', 'code_envoye', 'code_valide', 'valide',
                ]),
                name='un_seul_responsable_pedagogique_par_etablissement',
            )
        ]

    # Texte affiché pour un utilisateur (admin Django, listes déroulantes).
    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.get_role_display()})"

    # Prénom + nom, utilisé partout dans l'interface.
    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}"
    
    # Enfants du parent : uniquement les liens VALIDÉS par un gestionnaire (règle de confidentialité).
    @property
    def enfants(self):
        """Retourne les élèves liés à ce parent (queryset vide si ce n'est pas un parent)."""
        if self.role != self.Role.PARENT:
            return Utilisateur.objects.none()
        enfants_ids = self.relations_enfants.filter(
            statut=RelationParentEleve.Statut.VALIDEE
        ).values_list('enfant_id', flat=True)
        return Utilisateur.objects.filter(id__in=enfants_ids)

    # Parents de l'élève : même règle, seuls les liens validés comptent.
    @property
    def parents(self):
        """Retourne les parents liés à cet élève (queryset vide si ce n'est pas un élève)."""
        if self.role != self.Role.ELEVE:
            return Utilisateur.objects.none()
        parents_ids = self.relations_parents.filter(
            statut=RelationParentEleve.Statut.VALIDEE
        ).values_list('parent_id', flat=True)
        return Utilisateur.objects.filter(id__in=parents_ids)
    

# Catégorie qui regroupe des centres d'intérêt (affichage par groupes dans l'interface).
class CategorieInteret(models.Model):
    """Regroupement de centres d'intérêt (Sport, Informatique et numérique, ...), géré par l'administration."""
    nom = models.CharField(max_length=100, unique=True)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Catégorie de centres d'intérêt"
        verbose_name_plural = "Catégories de centres d'intérêt"
        ordering = ['ordre', 'nom']

    def __str__(self):
        return self.nom


# Centre d'intérêt sélectionnable par l'élève (profil, inscription) et utilisé par l'IA.
class CentreInteret(models.Model):
    """
    Centre d'intérêt qu'un élève peut choisir. `categorie_club` relie l'intérêt à une catégorie
    de club (signal utilisé par le moteur de recommandation).
    """
    nom = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    categorie = models.ForeignKey(
        CategorieInteret, on_delete=models.SET_NULL, null=True, blank=True, related_name='centres'
    )
    categorie_club = models.CharField(
        max_length=20, blank=True, choices=Club.Categorie.choices,
        help_text="Catégorie de club correspondante (facultatif, améliore les recommandations)",
    )
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Centre d'intérêt"
        verbose_name_plural = "Centres d'intérêt"
        ordering = ['categorie__ordre', 'nom']

    def __str__(self):
        return self.nom


# Journal d'audit : chaque action sensible y est enregistrée avec l'adresse IP.
class JournalActivite(models.Model):
    """
    Trace les actions importantes des utilisateurs (connexion, modification, etc.)
    """
    utilisateur = models.ForeignKey(
        Utilisateur, on_delete=models.CASCADE, related_name='journaux'
    )
    action = models.CharField(max_length=255)
    details = models.TextField(blank=True, null=True)
    date_action = models.DateTimeField(auto_now_add=True)
    adresse_ip = models.GenericIPAddressField(blank=True, null=True)

    class Meta:
        verbose_name = "Journal d'activité"
        verbose_name_plural = "Journaux d'activités"
        ordering = ['-date_action']

    def __str__(self):
        return f"{self.utilisateur.email} - {self.action} ({self.date_action:%Y-%m-%d %H:%M})"


# Lien parent ↔ élève. Le parent ne voit l'enfant qu'une fois le lien au statut « validee ».
class RelationParentEleve(models.Model):
    """
    Relation entre un parent et son enfant (élève).
    Un élève peut avoir plusieurs parents ; un parent peut avoir plusieurs enfants.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente de validation'
        VALIDEE = 'validee', 'Validée'

    statut = models.CharField(max_length=15, choices=Statut.choices, default=Statut.VALIDEE)
    parent = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name='relations_enfants',
        limit_choices_to={'role': 'parent'},
    )
    enfant = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name='relations_parents',
        limit_choices_to={'role': 'eleve'},
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    cree_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='relations_creees',
        help_text="Administrateur ayant créé ce lien (traçabilité)",
    )

    # Un même couple parent/enfant ne peut exister qu'une fois.
    class Meta:
        verbose_name = "Relation parent-enfant"
        verbose_name_plural = "Relations parent-enfant"
        constraints = [
            models.UniqueConstraint(fields=['parent', 'enfant'], name='relation_parent_enfant_unique')
        ]

    def __str__(self):
        return f"{self.parent.nom_complet} → {self.enfant.nom_complet}"


# Demande de rattachement par nom : le gestionnaire choisit ensuite l'élève correspondant.
class DemandeRattachement(models.Model):
    """
    Demande d'association envoyée par un parent connecté au responsable pédagogique,
    à partir du seul nom complet de l'enfant. Le gestionnaire identifie l'élève
    puis l'acceptation crée un lien RelationParentEleve validé.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        ACCEPTEE = 'acceptee', 'Acceptée'
        REFUSEE = 'refusee', 'Refusée'

    parent = models.ForeignKey(
        Utilisateur, on_delete=models.CASCADE, related_name='demandes_rattachement',
        limit_choices_to={'role': 'parent'},
    )
    nom_complet_enfant = models.CharField(max_length=200)
    classe = models.CharField(max_length=50, blank=True)
    message = models.TextField(blank=True)
    statut = models.CharField(max_length=15, choices=Statut.choices, default=Statut.EN_ATTENTE)
    enfant = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        limit_choices_to={'role': 'eleve'},
        help_text="Élève identifié par le gestionnaire lors de l'acceptation",
    )
    traitee_par = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Demande de rattachement"
        verbose_name_plural = "Demandes de rattachement"
        ordering = ['-date_creation']

    def __str__(self):
        return f"{self.parent.nom_complet} → {self.nom_complet_enfant} ({self.get_statut_display()})"


# Codes d'invitation à usage unique (activation élève, invitation responsable pédagogique).
class CodeInvitation(models.Model):
    """
    Code à usage unique permettant de sécuriser certaines inscriptions :
    - code d'activation pour un élève (généré par l'établissement)
    - code d'invitation pour un responsable pédagogique (généré par un administrateur)
    """

    class RoleCible(models.TextChoices):
        ELEVE = 'eleve', 'Élève'
        RESPONSABLE_PEDAGOGIQUE = 'proviseur', 'Responsable pédagogique'

    code = models.CharField(max_length=30, unique=True)
    role_cible = models.CharField(max_length=20, choices=RoleCible.choices)
    utilise = models.BooleanField(default=False)
    utilise_par = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True, related_name='code_utilise'
    )
    cree_par = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True, related_name='codes_generes'
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_utilisation = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Code d'invitation"
        verbose_name_plural = "Codes d'invitation"

    def __str__(self):
        statut = "utilisé" if self.utilise else "disponible"
        return f"{self.code} ({self.get_role_cible_display()}, {statut})"


# Liste officielle des matricules importée par l'administrateur (anti-usurpation à l'inscription).
class MatriculeOfficiel(models.Model):
    """
    Entrée de la liste officielle fournie par l'établissement (élèves, encadreurs professionnels).
    Dès qu'une liste existe pour un rôle, l'inscription publique n'est acceptée que pour un
    matricule de cette liste dont le nom et le prénom correspondent (anti-usurpation).
    """

    class Role(models.TextChoices):
        ELEVE = 'eleve', 'Élève'
        ENCADREUR = 'encadreur', 'Encadreur professionnel'

    matricule = models.CharField(max_length=30, unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ELEVE)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    classe = models.CharField(max_length=20, blank=True, null=True)
    date_import = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Matricule officiel"
        verbose_name_plural = "Matricules officiels"
        ordering = ['nom', 'prenom']

    def __str__(self):
        return f"{self.matricule} — {self.prenom} {self.nom}"
