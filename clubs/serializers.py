from rest_framework import serializers
from .models import Club


class ClubSerializer(serializers.ModelSerializer):
    """Serializer complet pour la création/modification d'un club."""

    responsable_nom = serializers.CharField(source='responsable.nom_complet', read_only=True)
    nombre_membres_actuels = serializers.ReadOnlyField()
    places_disponibles = serializers.ReadOnlyField()

    class Meta:
        model = Club
        fields = [
            'id', 'nom', 'description', 'categorie', 'objectifs',
            'responsable', 'responsable_nom', 'date_creation',
            'nombre_max_membres', 'logo', 'statut',
            'nombre_membres_actuels', 'places_disponibles',
        ]
        read_only_fields = ['id', 'date_creation']


class ClubListeSerializer(serializers.ModelSerializer):
    """Serializer allégé pour l'affichage en liste (dashboard, recherche)."""

    responsable_nom = serializers.CharField(source='responsable.nom_complet', read_only=True)
    nombre_membres_actuels = serializers.ReadOnlyField()

    class Meta:
        model = Club
        fields = [
            'id', 'nom', 'categorie', 'responsable_nom',
            'nombre_max_membres', 'nombre_membres_actuels', 'logo', 'statut',
        ]