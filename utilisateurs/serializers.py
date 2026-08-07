from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import Utilisateur, JournalActivite, RelationParentEleve, CodeInvitation
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str

class InscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer d'inscription publique. Le rôle 'administrateur' est explicitement
    interdit ici : un administrateur ne peut être créé que par un administrateur
    existant, via ParentSerializer/l'admin Django, jamais via ce endpoint public.
    """

    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)
    code_invitation = serializers.CharField(write_only=True, required=False, allow_blank=True)
    matricule_enfant = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Utilisateur
        fields = [
            'id', 'email', 'nom', 'prenom', 'role', 'telephone', 'date_naissance', 'genre',
            'password', 'password2',
            # Élève
            'matricule', 'classe',
            # Parent
            'type_lien_eleve', 'matricule_enfant',
            # Encadreur
            'type_encadreur', 'fonction', 'domaine_competence', 'club_souhaite', 'justificatif',
            # Responsable pédagogique
            'service_responsabilite', 'code_invitation',
        ]
        extra_kwargs = {
            'role': {'required': True},
            'matricule': {'required': False},
            'classe': {'required': False},
            'type_lien_eleve': {'required': False},
            'type_encadreur': {'required': False},
            'fonction': {'required': False},
            'domaine_competence': {'required': False},
            'club_souhaite': {'required': False},
            'justificatif': {'required': False},
            'service_responsabilite': {'required': False},
        }

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

        elif role == Utilisateur.Role.PARENT:
            if not attrs.get('type_lien_eleve'):
                raise serializers.ValidationError({"type_lien_eleve": "Veuillez préciser votre lien avec l'élève."})
            matricule_enfant = attrs.get('matricule_enfant')
            if matricule_enfant and not Utilisateur.objects.filter(
                matricule=matricule_enfant, role=Utilisateur.Role.ELEVE
            ).exists():
                raise serializers.ValidationError(
                    {"matricule_enfant": "Aucun élève ne correspond à ce matricule."}
                )

        elif role == Utilisateur.Role.ENCADREUR:
            type_encadreur = attrs.get('type_encadreur')
            if not type_encadreur:
                raise serializers.ValidationError({"type_encadreur": "Veuillez préciser le type d'encadreur."})
            if type_encadreur == Utilisateur.TypeEncadreur.PROFESSIONNEL and not attrs.get('matricule'):
                raise serializers.ValidationError(
                    {"matricule": "Le matricule professionnel est requis pour un encadreur professionnel."}
                )

        elif role == Utilisateur.Role.PROVISEUR:
            code = attrs.get('code_invitation')
            if not code:
                raise serializers.ValidationError(
                    {"code_invitation": "Un code d'invitation est requis pour ce rôle."}
                )
            from .models import CodeInvitation
            code_obj = CodeInvitation.objects.filter(
                code=code, role_cible=CodeInvitation.RoleCible.RESPONSABLE_PEDAGOGIQUE, utilise=False
            ).first()
            if not code_obj:
                raise serializers.ValidationError(
                    {"code_invitation": "Ce code d'invitation est invalide ou déjà utilisé."}
                )
            attrs['_code_invitation_obj'] = code_obj

        return attrs

    def create(self, validated_data):
        from django.utils import timezone
        from .models import RelationParentEleve, CodeInvitation

        validated_data.pop('password2')
        password = validated_data.pop('password')
        matricule_enfant = validated_data.pop('matricule_enfant', None)
        code_invitation_str = validated_data.pop('code_invitation', None)
        code_obj = validated_data.pop('_code_invitation_obj', None)

        role = validated_data.get('role')

        # Détermination du statut de validation selon le rôle
        if role == Utilisateur.Role.ELEVE:
            statut = Utilisateur.StatutValidation.EN_ATTENTE
        elif role == Utilisateur.Role.ENCADREUR:
            statut = Utilisateur.StatutValidation.EN_ATTENTE
        elif role == Utilisateur.Role.PROVISEUR:
            statut = Utilisateur.StatutValidation.EN_ATTENTE
        else:  # parent
            statut = Utilisateur.StatutValidation.VALIDE

        validated_data['statut_validation'] = statut
        utilisateur = Utilisateur.objects.create_user(password=password, **validated_data)

        if role == Utilisateur.Role.PARENT and matricule_enfant:
            enfant = Utilisateur.objects.filter(
                matricule=matricule_enfant, role=Utilisateur.Role.ELEVE
            ).first()
            if enfant:
                RelationParentEleve.objects.get_or_create(parent=utilisateur, enfant=enfant)

        if role == Utilisateur.Role.PROVISEUR and code_obj:
            code_obj.utilise = True
            code_obj.utilise_par = utilisateur
            code_obj.date_utilisation = timezone.now()
            code_obj.save()

        return utilisateur


class UtilisateurSerializer(serializers.ModelSerializer):
    """Serializer pour afficher/modifier le profil utilisateur."""

    nom_complet = serializers.ReadOnlyField()
    nombre_enfants = serializers.SerializerMethodField()

    class Meta:
        model = Utilisateur
        fields = ['id', 'email', 'nom', 'prenom', 'nom_complet', 'role',
                   'telephone', 'date_naissance', 'photo', 'classe', 'filiere',
                   'centres_interet', 'moyenne_generale', 'profession',
                   'nombre_enfants', 'is_active', 'date_joined']
        read_only_fields = ['id', 'email', 'role', 'is_active', 'date_joined']

    def get_nombre_enfants(self, obj):
        if obj.role == Utilisateur.Role.PARENT:
            return obj.enfants.count()
        return None

class ConnexionSerializer(serializers.Serializer):
    """Serializer pour la connexion (validation des identifiants)."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        utilisateur = authenticate(username=attrs['email'], password=attrs['password'])
        if not utilisateur:
            raise serializers.ValidationError("Email ou mot de passe incorrect.")
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
            password=password or Utilisateur.objects.make_random_password(),
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
    enfant_nom = serializers.CharField(source='enfant.nom_complet', read_only=True)

    class Meta:
        model = RelationParentEleve
        fields = ['id', 'parent', 'parent_nom', 'enfant', 'enfant_nom', 'date_creation', 'cree_par']
        read_only_fields = ['id', 'date_creation', 'cree_par']

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

    class Meta:
        model = Utilisateur
        fields = [
            'id', 'nom_complet', 'email', 'role', 'matricule', 'type_encadreur',
            'fonction', 'domaine_competence', 'club_souhaite', 'justificatif',
            'service_responsabilite', 'date_joined', 'statut_validation',
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

        attrs['utilisateur'] = utilisateur
        return attrs