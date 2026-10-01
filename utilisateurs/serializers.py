from rest_framework import serializers
from django.contrib.auth import authenticate
from django.db import transaction
from .models import (
    Utilisateur, JournalActivite, RelationParentEleve, CodeInvitation, MatriculeOfficiel, CentreInteret,
)
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
import secrets
from .securite import verifier_non_bloque, enregistrer_echec, reinitialiser
from .matricules import trouver_entree_officielle
from django.utils import timezone
from django.contrib.auth.password_validation import validate_password


class CentreInteretSerializer(serializers.ModelSerializer):
    categorie = serializers.CharField(source='categorie.nom', default='Autres', read_only=True)

    class Meta:
        model = CentreInteret
        fields = ['id', 'nom', 'description', 'categorie']
        read_only_fields = fields


def champ_interets():
    """Liste d'identifiants de centres d'intérêt actifs (champ facultatif)."""
    return serializers.PrimaryKeyRelatedField(
        many=True, required=False, queryset=CentreInteret.objects.filter(actif=True),
    )


class InscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer d'inscription publique. Le rôle 'administrateur' est explicitement
    interdit ici : un administrateur ne peut être créé que par un administrateur
    existant, via ParentSerializer/l'admin Django, jamais via ce endpoint public.
    """

    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)
    matricule_enfant = serializers.CharField(write_only=True, required=False, allow_blank=True)
    interets = champ_interets()

    class Meta:
        model = Utilisateur
        fields = [
            'id', 'email', 'nom', 'prenom', 'role', 'telephone', 'date_naissance', 'genre',
            'password', 'password2',
            # Élève
            'matricule', 'classe', 'filiere', 'centres_interet', 'interets',
            # Parent
            'type_lien_eleve', 'matricule_enfant',
            # Encadreur
            'type_encadreur', 'fonction', 'domaine_competence', 'club_souhaite', 'justificatif',
            # Responsable pédagogique
            'service_responsabilite', 'etablissement',
        ]
        extra_kwargs = {
            'role': {'required': True},
            'matricule': {'required': False},
            'classe': {'required': False},
            'filiere': {'required': False},
            'centres_interet': {'required': False},
            'type_lien_eleve': {'required': False},
            'type_encadreur': {'required': False},
            'fonction': {'required': False},
            'domaine_competence': {'required': False},
            'club_souhaite': {'required': False},
            'justificatif': {'required': False},
            'service_responsabilite': {'required': False},
        }

    def validate_password(self, value):
        validate_password(value)
        return value

    @staticmethod
    def _verifier_liste_officielle(role, attrs):
        """
        Si une liste officielle existe pour ce rôle, le matricule doit y figurer avec le même nom et
        prénom. On adopte l'orthographe officielle (évite les doublons de casse) et la classe officielle.
        """
        try:
            entree = trouver_entree_officielle(role, attrs.get('matricule'), attrs.get('nom'), attrs.get('prenom'))
        except ValueError as erreur:
            raise serializers.ValidationError({"matricule": str(erreur)})
        if entree:
            attrs['matricule'] = entree.matricule
            if role == 'eleve' and not attrs.get('classe') and entree.classe:
                attrs['classe'] = entree.classe

    def validate_role(self, value):
        if value == Utilisateur.Role.ADMINISTRATEUR:
            raise serializers.ValidationError(
                "La création d'un compte administrateur n'est pas autorisée depuis cette page."
            )
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Les deux mots de passe ne correspondent pas."})

        role = attrs.get('role')

        if role == Utilisateur.Role.ELEVE:
            if not attrs.get('matricule'):
                raise serializers.ValidationError({"matricule": "Le matricule scolaire est requis."})
            self._verifier_liste_officielle('eleve', attrs)

        elif role == Utilisateur.Role.PARENT:
            if not attrs.get('type_lien_eleve'):
                raise serializers.ValidationError({"type_lien_eleve": "Veuillez préciser votre lien avec l'élève."})

        elif role == Utilisateur.Role.ENCADREUR:
            type_encadreur = attrs.get('type_encadreur')
            if not type_encadreur:
                raise serializers.ValidationError({"type_encadreur": "Veuillez préciser le type d'encadreur."})
            if type_encadreur == Utilisateur.TypeEncadreur.PROFESSIONNEL and not attrs.get('matricule'):
                raise serializers.ValidationError(
                    {"matricule": "Le matricule professionnel est requis pour un encadreur professionnel."}
                )
            if type_encadreur == Utilisateur.TypeEncadreur.PROFESSIONNEL:
                self._verifier_liste_officielle('encadreur', attrs)

        elif role == Utilisateur.Role.PROVISEUR:
            if not attrs.get('justificatif'):
                raise serializers.ValidationError(
                    {"justificatif": "L'acte de nomination est obligatoire pour ce rôle."}
                )
            if not attrs.get('etablissement'):
                raise serializers.ValidationError(
                    {"etablissement": "Le nom de l'établissement est obligatoire."}
                )
            etablissement = attrs.get('etablissement').strip()
            existe_deja = Utilisateur.objects.filter(
                role=Utilisateur.Role.PROVISEUR,
                etablissement__iexact=etablissement,
                statut_validation__in=[
                    Utilisateur.StatutValidation.EN_ATTENTE,
                    Utilisateur.StatutValidation.CODE_ENVOYE,
                    Utilisateur.StatutValidation.CODE_VALIDE,
                    Utilisateur.StatutValidation.VALIDE,
                ],
            ).exists()
            if existe_deja:
                raise serializers.ValidationError(
                    {"etablissement": "Un responsable pédagogique est déjà enregistré pour cet établissement."}
                )

        return attrs

   
    def create(self, validated_data):
        from .models import RelationParentEleve

        validated_data.pop('password2')
        password = validated_data.pop('password')
        matricule_enfant = validated_data.pop('matricule_enfant', None)
        interets = validated_data.pop('interets', [])

        role = validated_data.get('role')

        if role == Utilisateur.Role.ELEVE:
            statut = Utilisateur.StatutValidation.EN_ATTENTE
        elif role == Utilisateur.Role.ENCADREUR:
            statut = Utilisateur.StatutValidation.EN_ATTENTE
        elif role == Utilisateur.Role.PROVISEUR:
            statut = Utilisateur.StatutValidation.EN_ATTENTE
            # Génération automatique du code dès la création — jamais manuellement par l'admin
            validated_data['code_validation_compte'] = f"RP-{secrets.token_hex(8).upper()}"
        else:
            statut = Utilisateur.StatutValidation.VALIDE

        validated_data['statut_validation'] = statut

        # Compte, intérêts et demande de rattachement sont créés ensemble ou pas du tout.
        with transaction.atomic():
            utilisateur = Utilisateur.objects.create_user(password=password, **validated_data)
            if role == Utilisateur.Role.ELEVE and interets:
                utilisateur.interets.set(interets)

            if role == Utilisateur.Role.PARENT and matricule_enfant:
                enfant = Utilisateur.objects.filter(
                    matricule=matricule_enfant, role=Utilisateur.Role.ELEVE
                ).first()
                if enfant:
                    # Simple demande de rattachement : un gestionnaire doit la valider.
                    # Le matricule seul ne prouve pas la filiation.
                    RelationParentEleve.objects.get_or_create(
                        parent=utilisateur, enfant=enfant,
                        defaults={'statut': RelationParentEleve.Statut.EN_ATTENTE},
                    )

        return utilisateur


class UtilisateurSerializer(serializers.ModelSerializer):
    """Serializer pour afficher/modifier le profil utilisateur."""

    nom_complet = serializers.ReadOnlyField()
    nombre_enfants = serializers.SerializerMethodField()
    interets = champ_interets()
    interets_details = CentreInteretSerializer(source='interets', many=True, read_only=True)

    class Meta:
        model = Utilisateur
        fields = ['id', 'email', 'nom', 'prenom', 'nom_complet', 'role',
                   'telephone', 'date_naissance', 'photo', 'classe', 'filiere',
                   'centres_interet', 'interets', 'interets_details', 'moyenne_generale', 'profession',
                   'nombre_enfants', 'is_active', 'date_joined']
        read_only_fields = ['id', 'email', 'role', 'is_active', 'date_joined']

    def validate_interets(self, value):
        if self.instance is not None and self.instance.role != Utilisateur.Role.ELEVE and value:
            raise serializers.ValidationError("Seuls les élèves peuvent renseigner des centres d'intérêt.")
        return value

    def get_nombre_enfants(self, obj):
        if obj.role == Utilisateur.Role.PARENT:
            return obj.enfants.count()
        return None


class ConnexionSerializer(serializers.Serializer):
    """Serializer pour la connexion (validation des identifiants)."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        verifier_non_bloque('login', attrs['email'])
        utilisateur = authenticate(username=attrs['email'], password=attrs['password'])
        if not utilisateur:
            enregistrer_echec('login', attrs['email'])
            raise serializers.ValidationError("Email ou mot de passe incorrect.")
        reinitialiser('login', attrs['email'])
        if not utilisateur.is_active:
            raise serializers.ValidationError("Ce compte est désactivé.")

        if utilisateur.statut_validation == Utilisateur.StatutValidation.EN_ATTENTE:
            raise serializers.ValidationError(
                "Votre compte est en attente de validation par l'administration."
            )
        if utilisateur.statut_validation == Utilisateur.StatutValidation.REFUSE:
            raise serializers.ValidationError(
                "Votre demande d'inscription a été refusée. Contactez l'administration pour plus d'informations."
            )
        if utilisateur.statut_validation == Utilisateur.StatutValidation.SUSPENDU:
            raise serializers.ValidationError("Votre compte est suspendu. Contactez l'administration.")

        attrs['utilisateur'] = utilisateur
        return attrs


class ChangementMotDePasseSerializer(serializers.Serializer):
    """Serializer pour le changement de mot de passe depuis le profil."""

    ancien_mot_de_passe = serializers.CharField(write_only=True)
    nouveau_mot_de_passe = serializers.CharField(write_only=True, min_length=8)

    def validate_nouveau_mot_de_passe(self, value):
        validate_password(value, self.context['request'].user)
        return value

    def validate_ancien_mot_de_passe(self, value):
        utilisateur = self.context['request'].user
        if not utilisateur.check_password(value):
            raise serializers.ValidationError("Ancien mot de passe incorrect.")
        return value


class ParentSerializer(serializers.ModelSerializer):
    """Serializer pour la gestion admin des comptes parents (liste, création, modification)."""

    nom_complet = serializers.ReadOnlyField()
    enfants_noms = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = Utilisateur
        fields = [
            'id', 'email', 'nom', 'prenom', 'nom_complet', 'telephone',
            'profession', 'photo', 'is_active', 'date_joined', 'enfants_noms', 'password',
        ]
        read_only_fields = ['id', 'date_joined']

    def get_enfants_noms(self, obj):
        return [e.nom_complet for e in obj.enfants]

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        validated_data['role'] = Utilisateur.Role.PARENT
        parent = Utilisateur.objects.create_user(
            password=password or secrets.token_urlsafe(16),
            **validated_data,
        )
        return parent

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class RelationParentEleveSerializer(serializers.ModelSerializer):
    """Serializer pour associer/dissocier un parent et un élève (usage admin)."""

    parent_nom = serializers.CharField(source='parent.nom_complet', read_only=True)
    parent_email = serializers.CharField(source='parent.email', read_only=True)
    parent_telephone = serializers.CharField(source='parent.telephone', read_only=True)
    type_lien_eleve = serializers.CharField(source='parent.type_lien_eleve', read_only=True)
    enfant_nom = serializers.CharField(source='enfant.nom_complet', read_only=True)
    enfant_matricule = serializers.CharField(source='enfant.matricule', read_only=True)
    enfant_classe = serializers.CharField(source='enfant.classe', read_only=True)

    class Meta:
        model = RelationParentEleve
        fields = [
            'id', 'parent', 'parent_nom', 'parent_email', 'parent_telephone', 'type_lien_eleve',
            'enfant', 'enfant_nom', 'enfant_matricule', 'enfant_classe',
            'statut', 'date_creation', 'cree_par',
        ]
        read_only_fields = ['id', 'statut', 'date_creation', 'cree_par']

    def validate_parent(self, value):
        if value.role != Utilisateur.Role.PARENT:
            raise serializers.ValidationError("Cet utilisateur n'a pas le rôle 'parent'.")
        return value

    def validate_enfant(self, value):
        if value.role != Utilisateur.Role.ELEVE:
            raise serializers.ValidationError("Cet utilisateur n'a pas le rôle 'élève'.")
        return value


class CompteEnAttenteSerializer(serializers.ModelSerializer):
    nom_complet = serializers.ReadOnlyField()
    justificatif = serializers.SerializerMethodField()

    def get_justificatif(self, obj):
        # URL de la vue authentifiée, jamais le chemin de stockage.
        return f'/api/auth/justificatif/{obj.id}/' if obj.justificatif else None

    class Meta:
        model = Utilisateur
        fields = [
            'id', 'nom_complet', 'nom', 'prenom', 'email', 'telephone', 'role', 'matricule',
            'type_encadreur', 'fonction', 'domaine_competence', 'club_souhaite', 'justificatif',
            'service_responsabilite', 'date_joined', 'statut_validation',
            'code_validation_compte', 'date_code_envoye', 'date_code_valide',
        ]
        read_only_fields = fields


class CodeInvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CodeInvitation
        fields = ['id', 'code', 'role_cible', 'utilise', 'utilise_par', 'date_creation', 'date_utilisation']
        read_only_fields = ['id', 'utilise', 'utilise_par', 'date_creation', 'date_utilisation']


class UtilisateurAdminSerializer(serializers.ModelSerializer):
    """Serializer complet pour la gestion admin de tous les utilisateurs, tous rôles confondus."""

    nom_complet = serializers.ReadOnlyField()

    class Meta:
        model = Utilisateur
        fields = [
            'id', 'email', 'nom', 'prenom', 'nom_complet', 'role', 'telephone',
            'matricule', 'statut_validation', 'is_active', 'date_joined',
        ]
        read_only_fields = ['id', 'date_joined']


class DemandeReinitialisationSerializer(serializers.Serializer):
    """Étape 1 : l'utilisateur fournit son email pour recevoir un lien de réinitialisation."""

    email = serializers.EmailField()

    def validate_email(self, value):
        # Ne révèle jamais si l'email existe ou non (évite l'énumération de comptes) :
        # la validation réussit toujours, l'action réelle est conditionnelle dans la vue.
        return value


class ConfirmationReinitialisationSerializer(serializers.Serializer):
    """Étape 2 : l'utilisateur fournit le lien reçu (uid + token) et son nouveau mot de passe."""

    uidb64 = serializers.CharField()
    token = serializers.CharField()
    nouveau_mot_de_passe = serializers.CharField(min_length=8)

    def validate(self, attrs):
        try:
            uid = force_str(urlsafe_base64_decode(attrs['uidb64']))
            utilisateur = Utilisateur.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, Utilisateur.DoesNotExist):
            raise serializers.ValidationError("Lien de réinitialisation invalide.")

        if not default_token_generator.check_token(utilisateur, attrs['token']):
            raise serializers.ValidationError("Ce lien de réinitialisation est invalide ou a expiré.")

        validate_password(attrs['nouveau_mot_de_passe'], utilisateur)
        attrs['utilisateur'] = utilisateur
        return attrs


class ValidationCodeSerializer(serializers.Serializer):
    """Étape self-service : le responsable pédagogique saisit son email + le code reçu."""

    email = serializers.EmailField()
    code = serializers.CharField()

    def validate(self, attrs):
        verifier_non_bloque('code', attrs['email'])
        utilisateur = Utilisateur.objects.filter(
            email=attrs['email'], role=Utilisateur.Role.PROVISEUR
        ).first()

        if not utilisateur:
            raise serializers.ValidationError("Compte introuvable.")

        if utilisateur.statut_validation in [
            Utilisateur.StatutValidation.CODE_VALIDE, Utilisateur.StatutValidation.VALIDE,
        ]:
            raise serializers.ValidationError("Ce code a déjà été utilisé.")

        if utilisateur.statut_validation != Utilisateur.StatutValidation.CODE_ENVOYE:
            raise serializers.ValidationError("Aucun code en attente de validation pour ce compte.")

        if utilisateur.date_expiration_code and timezone.now() > utilisateur.date_expiration_code:
            raise serializers.ValidationError("Ce code de validation a expiré. Veuillez renvoyer un autre code.")

        attendu = utilisateur.code_validation_compte or ''
        fourni = attrs['code'].strip().upper()
        if not attendu or not secrets.compare_digest(attendu.encode(), fourni.encode()):
            enregistrer_echec('code', attrs['email'])
            raise serializers.ValidationError("Code de validation incorrect.")
        reinitialiser('code', attrs['email'])

        attrs['utilisateur'] = utilisateur
        return attrs


class MatriculeOfficielSerializer(serializers.ModelSerializer):
    compte_cree = serializers.SerializerMethodField()

    class Meta:
        model = MatriculeOfficiel
        fields = ['id', 'matricule', 'role', 'nom', 'prenom', 'classe', 'compte_cree', 'date_import']
        read_only_fields = fields

    def get_compte_cree(self, obj):
        return obj.matricule in self.context.get('matricules_utilises', set())
