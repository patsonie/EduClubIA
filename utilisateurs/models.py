from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from .managers import UtilisateurManager
from django.db.models import Q
from .validators import valider_extension_justificatif, valider_extension_photo, valider_taille_fichier


class Utilisateur(AbstractBaseUser, PermissionsMixin):
    """
    Modèle utilisateur personnalisé pour la plateforme de gestion des clubs.
    Rôles possibles : administrateur, proviseur, encadreur, eleve, parent d'élève.
    """

    class Role(models.TextChoices):
        ADMINISTRATEUR = 'administrateur', 'Administrateur'
        PROVISEUR = 'proviseur', 'Responsable pédagogique'
        ENCADREUR = 'encadreur', 'Encadreur'
        ELEVE = 'eleve', 'Élève'
        PARENT = 'parent', "Parent d'élève"

    email = models.EmailField(unique=True, max_length=190, verbose_name="Adresse email")
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ELEVE)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    date_naissance = models.DateField(blank=True, null=True)
    classe = models.CharField(max_length=20, blank=True, null=True, help_text="Ex: Terminale D, 3ème A")
    filiere = models.CharField(max_length=50, blank=True, null=True, help_text="Ex: Scientifique, Littéraire")
    centres_interet = models.TextField(
        blank=True, null=True,
        help_text="Centres d'intérêt séparés par des virgules (ex: informatique, robotique, lecture)"
    )
    moyenne_generale = models.DecimalField(
        max_digits=4, decimal_places=2, blank=True, null=True,
        help_text="Moyenne générale sur 20"
    )
    profession = models.CharField(max_length=100, blank=True, null=True)
    photo = models.ImageField(
        upload_to='utilisateurs/photos/', blank=True, null=True,
        validators=[valider_extension_photo, valider_taille_fichier],
    )
    
    class Genre(models.TextChoices):
        MASCULIN = 'M', 'Masculin'
        FEMININ = 'F', 'Féminin'
        AUTRE = 'autre', 'Autre'

    class TypeEncadreur(models.TextChoices):
        PROFESSIONNEL = 'professionnel', 'Encadreur professionnel'
        VACATAIRE = 'vacataire', 'Encadreur vacataire'

    class StatutValidation(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente de validation'
        CODE_ENVOYE = 'code_envoye', 'Code envoyé'
        CODE_VALIDE = 'code_valide', 'Code validé'
        VALIDE = 'valide', 'Actif'
        REFUSE = 'refuse', 'Refusé'
        SUSPENDU = 'suspendu', 'Suspendu'
        
        
    genre = models.CharField(max_length=10, choices=Genre.choices, blank=True, null=True)
    matricule = models.CharField(max_length=30, unique=True, blank=True, null=True)
    statut_validation = models.CharField(
        max_length=15, choices=StatutValidation.choices, default=StatutValidation.VALIDE
    )
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

    motif_refus = models.TextField(blank=True, null=True)
    valide_par = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='comptes_valides'
    )
    date_validation = models.DateTimeField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UtilisateurManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nom', 'prenom']
    
    @property
    def compte_actif_utilisable(self):
        return self.statut_validation == self.StatutValidation.VALIDE

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

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.get_role_display()})"

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}"
    
    @property
    def enfants(self):
        """Retourne les élèves liés à ce parent (queryset vide si ce n'est pas un parent)."""
        if self.role != self.Role.PARENT:
            return Utilisateur.objects.none()
        enfants_ids = self.relations_enfants.values_list('enfant_id', flat=True)
        return Utilisateur.objects.filter(id__in=enfants_ids)

    @property
    def parents(self):
        """Retourne les parents liés à cet élève (queryset vide si ce n'est pas un élève)."""
        if self.role != self.Role.ELEVE:
            return Utilisateur.objects.none()
        parents_ids = self.relations_parents.values_list('parent_id', flat=True)
        return Utilisateur.objects.filter(id__in=parents_ids)
    

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


class RelationParentEleve(models.Model):
    """
    Relation entre un parent et son enfant (élève).
    Un élève peut avoir plusieurs parents ; un parent peut avoir plusieurs enfants.
    """

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

    class Meta:
        verbose_name = "Relation parent-enfant"
        verbose_name_plural = "Relations parent-enfant"
        constraints = [
            models.UniqueConstraint(fields=['parent', 'enfant'], name='relation_parent_enfant_unique')
        ]

    def __str__(self):
        return f"{self.parent.nom_complet} → {self.enfant.nom_complet}"
    
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