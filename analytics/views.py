from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone

from .models import RisqueDesengagement, PredictionParticipation, ClubEnDifficulte
from .serializers import (
    RisqueDesengagementSerializer, PredictionParticipationSerializer,
    ClubEnDifficulteSerializer, StatistiquesGlobalesSerializer,
)
from .services import (
    calculer_risques_desengagement_tous_eleves,
    predire_nombre_participants,
    detecter_clubs_en_difficulte,
)
from .permissions import EstGestionnaire, EstGestionnaireStrict

from utilisateurs.models import Utilisateur
from clubs.models import Club
from activites.models import Activite

from django.template.loader import render_to_string
from django.http import HttpResponse
from xhtml2pdf import pisa
import io

from django.db.models import Count
from django.db.models.functions import TruncMonth
from datetime import timedelta
import calendar


class RisqueDesengagementView(APIView):
    """
    GET /api/predictions/risques-desengagement/
    Gestionnaires : recalcule et retourne le risque pour tous les élèves.
    Parent : ne voit que le risque de ses propres enfants.
    Filtre optionnel : ?niveau=eleve
    """
    permission_classes = [EstGestionnaire]  # inclut le parent, filtrage fait ci-dessous

    def get(self, request):
        resultats = calculer_risques_desengagement_tous_eleves()

        objets_sauvegardes = []
        for resultat in resultats:
            objet, _ = RisqueDesengagement.objects.update_or_create(
                eleve=resultat["eleve"],
                club=resultat["club"],
                defaults={
                    "score_risque": resultat["score_risque"],
                    "niveau": resultat["niveau"],
                },
            )
            objets_sauvegardes.append(objet)

        if request.user.role == 'parent':
            ids_enfants = set(request.user.enfants.values_list('id', flat=True))
            objets_sauvegardes = [o for o in objets_sauvegardes if o.eleve_id in ids_enfants]

        niveau_filtre = request.query_params.get('niveau')
        if niveau_filtre:
            objets_sauvegardes = [o for o in objets_sauvegardes if o.niveau == niveau_filtre]

        objets_sauvegardes.sort(key=lambda o: o.score_risque, reverse=True)

        serializer = RisqueDesengagementSerializer(objets_sauvegardes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PredictionParticipationView(APIView):
    """
    GET /api/predictions/participation/{activite_id}/
    Prédit le nombre de participants pour une activité planifiée.
    Pas de logique de filtrage par enfant -> accès gestionnaires uniquement.
    """
    permission_classes = [EstGestionnaireStrict]

    def get(self, request, activite_id):
        try:
            activite = Activite.objects.get(id=activite_id)
        except Activite.DoesNotExist:
            return Response({"error": "Activité introuvable."}, status=status.HTTP_404_NOT_FOUND)

        nombre_prevu = predire_nombre_participants(activite)

        prediction, _ = PredictionParticipation.objects.update_or_create(
            activite=activite,
            defaults={"nombre_prevu": nombre_prevu},
        )

        serializer = PredictionParticipationSerializer(prediction)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ClubEnDifficulteView(APIView):
    """
    GET /api/predictions/clubs-difficulte/
    Détecte et retourne la liste des clubs en baisse d'activité.
    Pas de logique de filtrage par enfant -> accès gestionnaires uniquement.
    """
    permission_classes = [EstGestionnaireStrict]

    def get(self, request):
        resultats = detecter_clubs_en_difficulte()

        objets_sauvegardes = []
        for resultat in resultats:
            objet, _ = ClubEnDifficulte.objects.update_or_create(
                club=resultat["club"],
                defaults={
                    "score_difficulte": resultat["score_difficulte"],
                    "raison": resultat["raison"],
                },
            )
            objets_sauvegardes.append(objet)

        serializer = ClubEnDifficulteSerializer(objets_sauvegardes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class StatistiquesGlobalesView(APIView):
    """
    GET /api/predictions/statistiques-globales/
    Chiffres clés pour le tableau de bord principal.
    Accessible à tout utilisateur authentifié (les données sont agrégées, non sensibles).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        

        aujourdhui = timezone.now().date()
        debut_mois_actuel = aujourdhui.replace(day=1)
        debut_mois_precedent = (debut_mois_actuel - timedelta(days=1)).replace(day=1)

        def variation_pourcentage(queryset, champ_date):
            ce_mois = queryset.filter(**{f'{champ_date}__gte': debut_mois_actuel}).count()
            mois_dernier = queryset.filter(
                **{f'{champ_date}__gte': debut_mois_precedent, f'{champ_date}__lt': debut_mois_actuel}
            ).count()
            if mois_dernier == 0:
                return 100.0 if ce_mois > 0 else 0.0
            return round(((ce_mois - mois_dernier) / mois_dernier) * 100, 1)

        clubs_avec_effectif = Club.objects.all()
        clubs_populaires = sorted(
            clubs_avec_effectif, key=lambda c: c.nombre_membres_actuels, reverse=True
        )[:5]

        activites_a_venir = Activite.objects.filter(
            date__gte=aujourdhui
        ).exclude(statut=Activite.Statut.ANNULEE).order_by('date')[:5]

        repartition_categories = list(
            Club.objects.values('categorie').annotate(total=Count('id')).order_by('-total')
        )

        from inscriptions.models import Inscription
        inscriptions_par_mois = (
            Inscription.objects.filter(date_inscription__gte=aujourdhui - timedelta(days=365))
            .annotate(mois=TruncMonth('date_inscription'))
            .values('mois')
            .annotate(total=Count('id'))
            .order_by('mois')
        )
        evolution_inscriptions = [
            {"mois": calendar.month_abbr[i['mois'].month], "total": i['total']}
            for i in inscriptions_par_mois
        ]
        
        from participations.models import Participation

        activites_en_cours = Activite.objects.filter(statut=Activite.Statut.EN_COURS).count()
        activites_a_valider = Activite.objects.filter(statut=Activite.Statut.PLANIFIEE).count()
        nouveaux_clubs_mois = Club.objects.filter(date_creation__gte=debut_mois_actuel).count()

        participations_mois = Participation.objects.filter(date_enregistrement__gte=debut_mois_actuel)
        presences_mois = participations_mois.filter(statut='present').count()
        absences_mois = participations_mois.filter(statut__in=['absent', 'excuse']).count()

        total_participations_global = Participation.objects.count()
        taux_participation_global = 0
        if total_participations_global:
            taux_participation_global = round(
                Participation.objects.filter(statut='present').count() / total_participations_global * 100, 1
            )

        clubs_taux_participation = []
        for club in Club.objects.filter(statut='actif')[:8]:
            parts_club = Participation.objects.filter(inscription__club=club)
            total_club = parts_club.count()
            taux_club = round((parts_club.filter(statut='present').count() / total_club * 100), 1) if total_club else 0
            clubs_taux_participation.append({"nom": club.nom, "taux_participation": taux_club})
        clubs_taux_participation.sort(key=lambda c: c["taux_participation"], reverse=True)
        clubs_taux_participation = clubs_taux_participation[:5]

        data = {
            "nombre_clubs": Club.objects.count(),
            "nombre_activites": Activite.objects.count(),
            "nombre_eleves": Utilisateur.objects.filter(role='eleve').count(),
            "nombre_encadreurs": Utilisateur.objects.filter(role='encadreur').count(),
            "nombre_parents": Utilisateur.objects.filter(role='parent').count(),
            "variation_clubs": variation_pourcentage(Club.objects.all(), 'date_creation'),
            "variation_activites": variation_pourcentage(Activite.objects.all(), 'date_creation'),
            "variation_eleves": variation_pourcentage(Utilisateur.objects.filter(role='eleve'), 'date_joined'),
            "variation_inscriptions": variation_pourcentage(Inscription.objects.all(), 'date_inscription'),
            "nombre_inscriptions": Inscription.objects.count(),
            "activites_en_cours": activites_en_cours,
            "activites_a_valider": activites_a_valider,
            "nouveaux_clubs_mois": nouveaux_clubs_mois,
            "presences_mois": presences_mois,
            "absences_mois": absences_mois,
            "taux_participation_global": taux_participation_global,
            "clubs_taux_participation": clubs_taux_participation,
            "clubs_populaires": [
                {"nom": c.nom, "membres": c.nombre_membres_actuels, "categorie": c.categorie}
                for c in clubs_populaires
            ],
            "activites_a_venir": [
                {"titre": a.titre, "date": str(a.date), "club": a.club.nom, "categorie": a.club.categorie}
                for a in activites_a_venir
            ],
            "repartition_categories": repartition_categories,
            "evolution_inscriptions": evolution_inscriptions,
        }
        serializer = StatistiquesGlobalesSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RapportDetailleView(APIView):
    """
    GET /api/predictions/rapport-detaille/?club=<id>  (optionnel, sinon tous les clubs)
    Statistiques agrégées pour un rapport imprimable.
    Pas de logique de filtrage par enfant -> accès gestionnaires uniquement.
    """
    permission_classes = [EstGestionnaireStrict]

    def get(self, request):
        from participations.models import Participation
        from inscriptions.models import Inscription

        club_id = request.query_params.get('club')
        clubs = Club.objects.filter(id=club_id) if club_id else Club.objects.all()

        rapport_clubs = []
        for club in clubs:
            participations = Participation.objects.filter(inscription__club=club)
            total = participations.count()
            presents = participations.filter(statut='present').count()
            taux = round((presents / total * 100), 1) if total else 0

            rapport_clubs.append({
                "nom": club.nom,
                "categorie": club.categorie,
                "nombre_membres": club.nombre_membres_actuels,
                "nombre_activites": Activite.objects.filter(club=club).count(),
                "taux_participation": taux,
            })

        total_inscriptions = Inscription.objects.count()
        taux_global_participation = 0
        total_participations_global = Participation.objects.count()
        if total_participations_global:
            taux_global_participation = round(
                Participation.objects.filter(statut='present').count() / total_participations_global * 100, 1
            )

        return Response({
            "total_clubs": clubs.count(),
            "total_inscriptions": total_inscriptions,
            "taux_participation_global": taux_global_participation,
            "clubs": rapport_clubs,
        }, status=status.HTTP_200_OK)
        
class RapportPDFView(APIView):
    """
    GET /api/predictions/rapport-detaille/pdf/?club=<id>  (optionnel)
    Génère et retourne le rapport détaillé au format PDF (généré côté serveur).
    """
    permission_classes = [EstGestionnaireStrict]

    def get(self, request):
        from participations.models import Participation
        from inscriptions.models import Inscription

        club_id = request.query_params.get('club')
        clubs = Club.objects.filter(id=club_id) if club_id else Club.objects.all()
        club_filtre_nom = clubs.first().nom if club_id and clubs.exists() else None

        rapport_clubs = []
        for club in clubs:
            participations = Participation.objects.filter(inscription__club=club)
            total = participations.count()
            presents = participations.filter(statut='present').count()
            taux = round((presents / total * 100), 1) if total else 0

            rapport_clubs.append({
                "nom": club.nom,
                "categorie": club.categorie,
                "nombre_membres": club.nombre_membres_actuels,
                "nombre_activites": Activite.objects.filter(club=club).count(),
                "taux_participation": taux,
            })

        total_participations_global = Participation.objects.count()
        taux_global = 0
        if total_participations_global:
            taux_global = round(
                Participation.objects.filter(statut='present').count() / total_participations_global * 100, 1
            )

        contexte = {
            "nom_etablissement": "Lycée — Gestion des clubs et activités",
            "date_generation": timezone.now().strftime("%d/%m/%Y à %H:%M"),
            "club_filtre": club_filtre_nom,
            "total_clubs": clubs.count(),
            "total_inscriptions": Inscription.objects.count(),
            "taux_participation_global": taux_global,
            "clubs": rapport_clubs,
        }

        html_genere = render_to_string('base/rapport_pdf.html', contexte)

        buffer_pdf = io.BytesIO()
        resultat = pisa.CreatePDF(src=html_genere, dest=buffer_pdf, encoding='UTF-8')

        if resultat.err:
            return Response(
                {"error": "Erreur lors de la génération du PDF."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        buffer_pdf.seek(0)
        reponse = HttpResponse(buffer_pdf.read(), content_type='application/pdf')
        reponse['Content-Disposition'] = 'attachment; filename="rapport_clubs.pdf"'
        return reponse