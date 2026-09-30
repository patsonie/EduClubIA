from rest_framework import serializers
from .models import SalonDiscussion, Message


class MessageSerializer(serializers.ModelSerializer):
    expediteur_nom = serializers.CharField(source='expediteur.nom_complet', read_only=True)
    contenu = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    fichier = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'salon', 'expediteur', 'expediteur_nom', 'contenu', 'fichier', 'date_envoi']
        read_only_fields = ['id', 'expediteur', 'date_envoi']

    def get_fichier(self, obj):
        # URL protégée (contrôle d'accès au salon), jamais l'URL brute du stockage.
        if not obj.fichier:
            return None
        return f'/api/messagerie/salons/{obj.salon_id}/fichier/{obj.id}/'


class SalonDiscussionSerializer(serializers.ModelSerializer):
    nom_affiche = serializers.ReadOnlyField()
    dernier_message = serializers.SerializerMethodField()

    class Meta:
        model = SalonDiscussion
        fields = ['id', 'club', 'activite', 'nom_affiche', 'date_creation', 'dernier_message']

    def get_dernier_message(self, obj):
        dernier = obj.messages.select_related('expediteur').order_by('-date_envoi').first()
        if not dernier:
            return None
        return {
            "contenu": dernier.contenu,
            "expediteur_nom": dernier.expediteur.nom_complet,
            "date_envoi": dernier.date_envoi,
        }
