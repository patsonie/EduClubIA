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
        read_only_fields = ['id', 'statut', 'date_inscription', 'date_traitement', 'traite_par']
        validators = []  # on gère l'unicité manuellement dans validate()

    def validate(self, attrs):
        club = attrs.get('club')
        annee_scolaire = attrs.get('annee_scolaire')
        request_user = self.context['request'].user
        # Un élève ne peut agir que pour lui-même (le champ `eleve` est ignoré pour lui).
        eleve = request_user if request_user.role == 'eleve' else (attrs.get('eleve') or request_user)

        if eleve.role != Utilisateur.Role.ELEVE:
            raise serializers.ValidationError({"eleve": "L'inscription doit concerner un élève."})
        if club and club.statut != club.Statut.ACTIF:
            raise serializers.ValidationError({"club": "Ce club n'accepte pas d'inscriptions actuellement."})
        if annee_scolaire and not annee_scolaire.est_active:
            raise serializers.ValidationError(
                {"annee_scolaire": "Les inscriptions ne sont possibles que pour l'année scolaire active."}
            )

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