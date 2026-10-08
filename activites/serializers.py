from rest_framework import serializers
from .models import Activite, HistoriqueActivite


# Ligne d'historique d'une activité.
class HistoriqueActiviteSerializer(serializers.ModelSerializer):
    modifie_par_nom = serializers.CharField(source='modifie_par.nom_complet', read_only=True)

    class Meta:
        model = HistoriqueActivite
        fields = ['id', 'ancien_statut', 'nouveau_statut', 'modifie_par_nom', 'date_modification', 'commentaire']


# === Détail d'une activité ===
class ActiviteSerializer(serializers.ModelSerializer):
    club_nom = serializers.CharField(source='club.nom', read_only=True)
    responsable_nom = serializers.CharField(source='responsable.nom_complet', read_only=True)
    historique = HistoriqueActiviteSerializer(many=True, read_only=True)

    class Meta:
        model = Activite
        fields = [
            'id', 'club', 'club_nom', 'titre', 'description', 'date', 'heure',
            'lieu', 'budget', 'responsable', 'responsable_nom', 'statut',
            'date_creation', 'date_modification', 'historique',
        ]
        read_only_fields = ['id', 'date_creation', 'date_modification']

    # Le budget est masqué pour les élèves et les parents.
    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request and request.user.is_authenticated and request.user.role in ('eleve', 'parent'):
            data.pop('budget', None)
        return data


# === Version allégée pour les listes et le calendrier ===
class ActiviteListeSerializer(serializers.ModelSerializer):
    club_nom = serializers.CharField(source='club.nom', read_only=True)

    class Meta:
        model = Activite
        fields = ['id', 'titre', 'club_nom', 'date', 'heure', 'lieu', 'statut']