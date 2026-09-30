from rest_framework import serializers
from .models import Participation


class ParticipationSerializer(serializers.ModelSerializer):
    eleve_nom = serializers.CharField(source='inscription.eleve.nom_complet', read_only=True)
    club_nom = serializers.CharField(source='inscription.club.nom', read_only=True)
    activite_titre = serializers.CharField(source='activite.titre', read_only=True)

    class Meta:
        model = Participation
        fields = [
            'id', 'inscription', 'eleve_nom', 'club_nom', 'activite', 'activite_titre',
            'statut', 'date_enregistrement', 'enregistre_par', 'commentaire',
        ]
        read_only_fields = ['id', 'date_enregistrement', 'enregistre_par']
        validators = []  # unicité vérifiée manuellement dans validate()

    def validate(self, attrs):
        inscription = attrs.get('inscription')
        activite = attrs.get('activite')

        if self.instance:
            inscription = inscription or self.instance.inscription
            activite = activite or self.instance.activite

        request = self.context.get('request')
        if request and activite and request.user.role == 'encadreur' and activite.club.responsable_id != request.user.id:
            raise serializers.ValidationError("Vous ne gérez pas le club de cette activité.")

        if inscription and inscription.statut != inscription.Statut.VALIDEE:
            raise serializers.ValidationError("L'inscription de cet élève n'est pas validée.")

        if inscription and activite and inscription.club_id != activite.club_id:
            raise serializers.ValidationError(
                "Cette inscription ne correspond pas au club organisateur de l'activité."
            )

        doublons = Participation.objects.filter(inscription=inscription, activite=activite)
        if self.instance:
            doublons = doublons.exclude(pk=self.instance.pk)
        if doublons.exists():
            raise serializers.ValidationError(
                "La participation de cet élève à cette activité est déjà enregistrée."
            )

        return attrs


class RapportIndividuelSerializer(serializers.Serializer):
    """Rapport de participation individuel pour un élève donné."""

    eleve_id = serializers.IntegerField()
    eleve_nom = serializers.CharField()
    total_activites = serializers.IntegerField()
    total_presences = serializers.IntegerField()
    taux_participation = serializers.FloatField()