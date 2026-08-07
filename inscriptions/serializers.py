from rest_framework import serializers
from utilisateurs.models import Utilisateur
from .models import Inscription, HistoriqueInscription


class HistoriqueInscriptionSerializer(serializers.ModelSerializer):
    modifie_par_nom = serializers.CharField(source='modifie_par.nom_complet', read_only=True)

    class Meta:
        model = HistoriqueInscription
        fields = ['id', 'ancien_statut', 'nouveau_statut', 'modifie_par_nom', 'date_modification', 'commentaire']


class InscriptionSerializer(serializers.ModelSerializer):
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
        read_only_fields = ['id', 'date_inscription', 'date_traitement', 'traite_par']
        validators = []  # on gère l'unicité manuellement dans validate()

    def validate(self, attrs):
        club = attrs.get('club')
        annee_scolaire = attrs.get('annee_scolaire')
        eleve = attrs.get('eleve') or self.context['request'].user

        if Inscription.objects.filter(
            eleve=eleve, club=club, annee_scolaire=annee_scolaire
        ).exclude(statut=Inscription.Statut.ANNULEE).exists():
            raise serializers.ValidationError(
                "Cet élève est déjà inscrit à ce club pour cette année scolaire."
            )

        if club and club.places_disponibles <= 0:
            raise serializers.ValidationError(
                f"Le club {club.nom} a atteint son nombre maximal de membres."
            )

        return attrs