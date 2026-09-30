from rest_framework import serializers
from .models import AnneeScolaire


class AnneeScolaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnneeScolaire
        fields = ['id', 'libelle', 'date_debut', 'date_fin', 'est_active', 'date_creation']
        # `est_active` ne se change que via l'action /activer/ (qui archive aussi les inscriptions).
        read_only_fields = ['id', 'est_active', 'date_creation']

    def validate(self, attrs):
        date_debut = attrs.get('date_debut', getattr(self.instance, 'date_debut', None))
        date_fin = attrs.get('date_fin', getattr(self.instance, 'date_fin', None))
        if date_debut and date_fin and date_debut >= date_fin:
            raise serializers.ValidationError(
                "La date de fin doit être postérieure à la date de début."
            )
        return attrs