from rest_framework import serializers
from utilisateurs.models import Utilisateur
from annees_scolaires.models import AnneeScolaire
from .models import Inscription, HistoriqueInscription


# Ligne d'historique d'une inscription (qui a changé le statut, quand).
class HistoriqueInscriptionSerializer(serializers.ModelSerializer):
    modifie_par_nom = serializers.CharField(source='modifie_par.nom_complet', read_only=True)

    class Meta:
        model = HistoriqueInscription
        fields = ['id', 'ancien_statut', 'nouveau_statut', 'modifie_par_nom', 'date_modification', 'commentaire']


# === Inscription d'un élève à un club ===
class InscriptionSerializer(serializers.ModelSerializer):
    # Champs ajoutés pour l'affichage (noms lisibles) et historique complet.
    eleve_nom = serializers.CharField(source='eleve.nom_complet', read_only=True)
    club_nom = serializers.CharField(source='club.nom', read_only=True)
    annee_scolaire_libelle = serializers.CharField(source='annee_scolaire.libelle', read_only=True)
    historique = HistoriqueInscriptionSerializer(many=True, read_only=True)
    eleve = serializers.PrimaryKeyRelatedField(
        queryset=Utilisateur.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Inscription
        fields = [
            'id', 'eleve', 'eleve_nom', 'club', 'club_nom',
            'annee_scolaire', 'annee_scolaire_libelle', 'statut',
            'date_inscription', 'date_traitement', 'traite_par', 'historique',
        ]
        read_only_fields = ['id', 'statut', 'date_inscription', 'date_traitement', 'traite_par']
        # Facultative : par défaut, l'année scolaire active (l'élève n'a qu'à choisir le club).
        extra_kwargs = {'annee_scolaire': {'required': False}}
        validators = []  # on gère l'unicité manuellement dans validate()

    # Contrôles avant la création d'une inscription.
    def validate(self, attrs):
        club = attrs.get('club')
        # Sans année précisée, on prend l'année scolaire active.
        if self.instance is None and not attrs.get('annee_scolaire'):
            attrs['annee_scolaire'] = AnneeScolaire.objects.filter(est_active=True).first()
            if attrs['annee_scolaire'] is None:
                raise serializers.ValidationError(
                    {"annee_scolaire": "Aucune année scolaire n'est active : les inscriptions sont fermées."}
                )
        annee_scolaire = attrs.get('annee_scolaire')
        request_user = self.context['request'].user
        # Un élève ne peut agir que pour lui-même (le champ `eleve` est ignoré pour lui).
        # L'élève concerné : lui-même s'il est élève, sinon celui choisi par le gestionnaire.
        eleve = request_user if request_user.role == 'eleve' else (attrs.get('eleve') or request_user)

        # L'inscrit doit être un élève, le club actif et l'année en cours.
        if eleve.role != Utilisateur.Role.ELEVE:
            raise serializers.ValidationError({"eleve": "L'inscription doit concerner un élève."})
        if club and club.statut != club.Statut.ACTIF:
            raise serializers.ValidationError({"club": "Ce club n'accepte pas d'inscriptions actuellement."})
        if annee_scolaire and not annee_scolaire.est_active:
            raise serializers.ValidationError(
                {"annee_scolaire": "Les inscriptions ne sont possibles que pour l'année scolaire active."}
            )

        # Refuse un doublon (une inscription annulée ne compte pas : elle sera réactivée).
        doublons = Inscription.objects.filter(
            eleve=eleve, club=club, annee_scolaire=annee_scolaire
        ).exclude(statut=Inscription.Statut.ANNULEE)
        if self.instance:
            doublons = doublons.exclude(pk=self.instance.pk)
        if club and annee_scolaire and doublons.exists():
            raise serializers.ValidationError(
                "Cet élève est déjà inscrit à ce club pour cette année scolaire."
            )

        return attrs