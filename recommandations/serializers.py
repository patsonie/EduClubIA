from rest_framework import serializers
from .models import Recommandation, HistoriqueEntrainement


class RecommandationSerializer(serializers.ModelSerializer):
    club_nom = serializers.CharField(source='club.nom', read_only=True)
    club_categorie = serializers.CharField(source='club.categorie', read_only=True)
    club_logo = serializers.ImageField(source='club.logo', read_only=True)

    class Meta:
        model = Recommandation
        fields = [
            'id', 'club', 'club_nom', 'club_categorie', 'club_logo',
            'score', 'explication', 'date_calcul',
        ]
        read_only_fields = fields
        
class HistoriqueEntrainementSerializer(serializers.ModelSerializer):
    declenche_par_nom = serializers.CharField(source='declenche_par.nom_complet', read_only=True)

    class Meta:
        model = HistoriqueEntrainement
        fields = [
            'id', 'type_declenchement', 'statut', 'metriques',
            'message_erreur', 'declenche_par_nom', 'date_entrainement', 'duree_secondes',
        ]
        read_only_fields = fields