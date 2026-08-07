from rest_framework import serializers
from .models import SalonDiscussion, Message


class MessageSerializer(serializers.ModelSerializer):
    expediteur_nom = serializers.CharField(source='expediteur.nom_complet', read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'salon', 'expediteur', 'expediteur_nom', 'contenu', 'fichier', 'date_envoi']
        read_only_fields = ['id', 'expediteur', 'date_envoi']


class SalonDiscussionSerializer(serializers.ModelSerializer):
    nom_affiche = serializers.ReadOnlyField()
    dernier_message = serializers.SerializerMethodField()

    class Meta:
        model = SalonDiscussion
        fields = ['id', 'club', 'activite', 'nom_affiche', 'date_creation', 'dernier_message']

    def get_dernier_message(self, obj):
        dernier = obj.messages.order_by('-date_envoi').first()
        if not dernier:
            return None
        return {
            "contenu": dernier.contenu,
            "expediteur_nom": dernier.expediteur.nom_complet,
            "date_envoi": dernier.date_envoi,
        }