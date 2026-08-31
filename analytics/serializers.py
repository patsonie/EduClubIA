from rest_framework import serializers
from .models import RisqueDesengagement
from .models import PredictionParticipation, ClubEnDifficulte

class RisqueDesengagementSerializer(serializers.ModelSerializer):
    eleve_nom = serializers.CharField(source='eleve.nom_complet', read_only=True)
    club_nom = serializers.CharField(source='club.nom', read_only=True)

    class Meta:
        model = RisqueDesengagement
        fields = ['id', 'eleve', 'eleve_nom', 'club', 'club_nom', 'score_risque', 'niveau', 'date_calcul']
        read_only_fields = fields
        

class PredictionParticipationSerializer(serializers.ModelSerializer):
    activite_titre = serializers.CharField(source='activite.titre', read_only=True)

    class Meta:
        model = PredictionParticipation
        fields = ['id', 'activite', 'activite_titre', 'nombre_prevu', 'date_calcul']
        read_only_fields = fields


class ClubEnDifficulteSerializer(serializers.ModelSerializer):
    club_nom = serializers.CharField(source='club.nom', read_only=True)

    class Meta:
        model = ClubEnDifficulte
        fields = ['id', 'club', 'club_nom', 'score_difficulte', 'raison', 'date_calcul']
        read_only_fields = fields
        
class StatistiquesGlobalesSerializer(serializers.Serializer):
    nombre_clubs = serializers.IntegerField()
    nombre_activites = serializers.IntegerField()
    nombre_eleves = serializers.IntegerField()
    nombre_encadreurs = serializers.IntegerField()
    nombre_parents = serializers.IntegerField()
    nombre_inscriptions = serializers.IntegerField()
    variation_clubs = serializers.FloatField()
    variation_activites = serializers.FloatField()
    variation_eleves = serializers.FloatField()
    variation_inscriptions = serializers.FloatField()
    clubs_populaires = serializers.ListField()
    activites_a_venir = serializers.ListField()
    repartition_categories = serializers.ListField()
    evolution_inscriptions = serializers.ListField()
    # Champs dédiés au dashboard Responsable pédagogique
    activites_en_cours = serializers.IntegerField()
    activites_a_valider = serializers.IntegerField()
    nouveaux_clubs_mois = serializers.IntegerField()
    presences_mois = serializers.IntegerField()
    absences_mois = serializers.IntegerField()
    taux_participation_global = serializers.FloatField()
    clubs_taux_participation = serializers.ListField()