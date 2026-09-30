from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Participation
from .serializers import ParticipationSerializer, RapportIndividuelSerializer
from .permissions import EstGestionnaireOuLectureSeule
from django.db import transaction
from activites.models import Activite
from inscriptions.models import Inscription
from utilisateurs.perimetre import est_gestion_globale, clubs_geres, peut_gerer_club
from notifications.services import notifier_parents_absence


class ParticipationViewSet(viewsets.ModelViewSet):
    """
    CRUD des participations (présences).
    Un élève voit uniquement ses propres participations ; gestionnaires voient tout.
    Filtre : ?activite=1&statut=present&inscription=2
    Action : GET /api/participations/rapport_individuel/?eleve_id=3
    """
    serializer_class = ParticipationSerializer
    permission_classes = [EstGestionnaireOuLectureSeule]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['activite', 'statut', 'inscription', 'inscription__eleve']
    ordering_fields = ['date_enregistrement']


    def get_queryset(self):
        user = self.request.user
        base = Participation.objects.select_related(
            'inscription__eleve', 'inscription__club', 'activite'
        )
        if est_gestion_globale(user):
            return base
        if user.role == 'encadreur':
            return base.filter(activite__club__in=clubs_geres(user))
        if user.role == 'parent':
            return base.filter(inscription__eleve__in=user.enfants)
        return base.filter(inscription__eleve=user)

    def perform_create(self, serializer):
        participation = serializer.save(enregistre_par=self.request.user)
        notifier_parents_absence(participation)

    def perform_update(self, serializer):
        ancien_statut = serializer.instance.statut
        participation = serializer.save(enregistre_par=self.request.user)
        if participation.statut != ancien_statut:
            notifier_parents_absence(participation)

    @staticmethod
    def _peut_consulter_eleve(user, eleve_id):
        if est_gestion_globale(user) or user.role == 'encadreur':
            return True
        if user.role == 'parent':
            return user.enfants.filter(id=eleve_id).exists()
        return user.id == eleve_id

    @action(detail=False, methods=['get'])
    def rapport_individuel(self, request):
        """
        GET /api/participations/rapport_individuel/?eleve_id=3
        Calcule le taux de participation d'un élève sur l'ensemble de ses activités.
        """
        eleve_id = request.query_params.get('eleve_id')
        if not eleve_id:
            return Response(
                {"error": "Le paramètre eleve_id est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            eleve_id = int(eleve_id)
        except (TypeError, ValueError):
            return Response({"error": "eleve_id invalide."}, status=status.HTTP_400_BAD_REQUEST)

        # Le queryset est déjà restreint au périmètre de l'utilisateur
        # (élève : lui-même, parent : ses enfants, encadreur : ses clubs).
        participations = self.get_queryset().filter(inscription__eleve_id=eleve_id)
        if not participations.exists() and not self._peut_consulter_eleve(request.user, eleve_id):
            return Response(
                {"error": "Vous n'êtes pas autorisé à consulter cet élève."},
                status=status.HTTP_403_FORBIDDEN,
            )
        total = participations.count()
        presences = participations.filter(statut=Participation.Statut.PRESENT).count()
        taux = round((presences / total * 100), 2) if total > 0 else 0.0

        premiere = participations.first()
        eleve_nom = premiere.inscription.eleve.nom_complet if premiere else ""

        data = {
            "eleve_id": int(eleve_id),
            "eleve_nom": eleve_nom,
            "total_activites": total,
            "total_presences": presences,
            "taux_participation": taux,
        }
        serializer = RapportIndividuelSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def enregistrer_lot(self, request):
        """
        POST /api/participations/enregistrer_lot/
        body: {"activite": <id>, "presences": [{"inscription": <id>, "statut": "present"}, ...]}
        Crée ou met à jour en une seule requête (atomique) les présences de toute une activité.
        """
        try:
            activite = Activite.objects.select_related('club').get(pk=request.data.get('activite'))
        except (Activite.DoesNotExist, TypeError, ValueError):
            return Response({"error": "Activité introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if not peut_gerer_club(request.user, activite.club):
            return Response(
                {"error": "Vous ne gérez pas le club de cette activité."},
                status=status.HTTP_403_FORBIDDEN,
            )

        presences = request.data.get('presences')
        if not isinstance(presences, list) or not presences:
            return Response({"error": "La liste `presences` est requise."}, status=status.HTTP_400_BAD_REQUEST)

        statuts_valides = {choix for choix, _ in Participation.Statut.choices}
        inscriptions = {
            i.id: i for i in Inscription.objects.select_related('eleve').filter(
                club=activite.club, statut=Inscription.Statut.VALIDEE
            )
        }

        entrees = []
        for entree in presences:
            if not isinstance(entree, dict):
                return Response({"error": "Entrée de présence invalide."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                inscription_id = int(entree.get('inscription'))
            except (TypeError, ValueError):
                return Response({"error": "Identifiant d'inscription invalide."}, status=status.HTTP_400_BAD_REQUEST)
            if inscription_id not in inscriptions:
                return Response(
                    {"error": f"L'inscription {inscription_id} n'est pas une inscription validée de ce club."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if entree.get('statut') not in statuts_valides:
                return Response(
                    {"error": f"Statut invalide. Valeurs possibles : {sorted(statuts_valides)}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            entrees.append((inscription_id, entree['statut']))

        anciens = dict(
            Participation.objects.filter(activite=activite).values_list('inscription_id', 'statut')
        )
        resultats = []
        with transaction.atomic():
            for inscription_id, statut in entrees:
                participation, _ = Participation.objects.update_or_create(
                    inscription_id=inscription_id,
                    activite=activite,
                    defaults={'statut': statut, 'enregistre_par': request.user},
                )
                resultats.append(participation)

        for participation in resultats:
            if anciens.get(participation.inscription_id) != participation.statut:
                notifier_parents_absence(participation)

        return Response(
            {"message": f"{len(resultats)} présence(s) enregistrée(s).", "ids": [p.id for p in resultats]},
            status=status.HTTP_200_OK,
        )
