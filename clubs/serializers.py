from rest_framework import serializers
from .models import Club


# === Détail d'un club (lecture, création, modification) ===
class ClubSerializer(serializers.ModelSerializer):
    """Serializer complet pour la création/modification d'un club."""

    # Champs calculés : nom du responsable, membres actuels, places libres, inscription de l'élève connecté.
    responsable_nom = serializers.CharField(source='responsable.nom_complet', read_only=True)
    nombre_membres_actuels = serializers.ReadOnlyField()
    places_disponibles = serializers.ReadOnlyField()
    mon_inscription = serializers.SerializerMethodField()
    inscriptions_fermees_raison = serializers.SerializerMethodField()

    class Meta:
        model = Club
        fields = [
            'id', 'nom', 'description', 'categorie', 'objectifs',
            'responsable', 'responsable_nom', 'date_creation',
            'nombre_max_membres', 'logo', 'statut',
            'nombre_membres_actuels', 'places_disponibles', 'mon_inscription',
            'inscriptions_fermees_raison',
        ]
        read_only_fields = ['id', 'date_creation']

    # Permet à la page détail d'afficher « S'inscrire » ou « Se désinscrire » pour l'élève connecté.
    def get_mon_inscription(self, obj):
        """Pour un élève : son inscription en cours à ce club (id, statut), sinon None."""
        from inscriptions.models import Inscription
        request = self.context.get('request')
        if not request or getattr(request.user, 'role', None) != 'eleve':
            return None
        inscription = Inscription.objects.filter(
            eleve=request.user, club=obj,
            statut__in=[Inscription.Statut.EN_ATTENTE, Inscription.Statut.VALIDEE],
        ).order_by('-date_inscription').first()
        return {'id': inscription.id, 'statut': inscription.statut} if inscription else None

    # Explique à l'élève pourquoi il ne peut pas s'inscrire (None = inscriptions ouvertes).
    def get_inscriptions_fermees_raison(self, obj):
        from annees_scolaires.models import AnneeScolaire
        if obj.statut != Club.Statut.ACTIF:
            return f"Ce club est {obj.get_statut_display().lower()} : il n'accepte pas encore d'inscriptions."
        if not AnneeScolaire.objects.filter(est_active=True).exists():
            return "Aucune année scolaire n'est active : les inscriptions sont fermées."
        if obj.places_disponibles <= 0:
            return "Ce club est complet."
        return None

    # Contrôle à l'affectation d'un responsable par le gestionnaire.
    def validate_responsable(self, value):
        """Un encadreur encadre un et un seul club."""
        if value is None:
            return value
        if value.role != 'encadreur':
            raise serializers.ValidationError("Le responsable d'un club doit être un encadreur.")
        autre = Club.objects.filter(responsable=value)
        if self.instance is not None:
            autre = autre.exclude(pk=self.instance.pk)
        autre = autre.first()
        if autre:
            raise serializers.ValidationError(f"Cet encadreur encadre déjà le club « {autre.nom} ».")
        return value


# === Version allégée pour les listes de clubs ===
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