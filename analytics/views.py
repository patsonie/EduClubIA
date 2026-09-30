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
from utilisateurs.perimetre import clubs_geres, peut_gerer_club

from utilisateurs.models import Utilisateur
from clubs.models import Club
from activites.models import Activite

from django.template.loader import render_to_string
from django.http import HttpResponse
from xhtml2pdf import pisa
import io

from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from datetime import timedelta
MOIS_ABREGES = ['Janv', 'Févr', 'Mars', 'Avr', 'Mai', 'Juin', 'Juil', 'Août', 'Sept', 'Oct', 'Nov', 'Déc']


def construire_rapport_clubs(request):
    """Données communes au rapport JSON et PDF, limitées au périmètre de l'utilisateur."""
    from participations.models import Participation
    from inscriptions.models import Inscription

    club_id = request.query_params.get('club')
    clubs = clubs_geres(request.user)
    if club_id:
        try:
            clubs = clubs.filter(id=int(club_id))
        except (TypeError, ValueError):
            clubs = clubs.none()
    clubs = clubs.annotate(
        membres_annotes=Count('inscriptions', filter=Q(inscriptions__statut='validee'), distinct=True)
    )
    club_filtre_nom = clubs.first().nom if club_id and clubs.exists() else None

    participations = Participation.objects.filter(inscription__club__in=clubs)
    par_club = {
        ligne['inscription__club_id']: ligne
        for ligne in participations.values('inscription__club_id').annotate(
            total=Count('id'), presents=Count('id', filter=Q(statut='present'))
        )
    }
    activites_par_club = dict(
        Activite.objects.filter(club__in=clubs).values_list('club_id').annotate(n=Count('id'))
    )

    rapport_clubs = []
    for club in clubs:
        stats = par_club.get(club.id, {'total': 0, 'presents': 0})
        taux = round(stats['presents'] / stats['total'] * 100, 1) if stats['total'] else 0
        rapport_clubs.append({
            "nom": club.nom,
            "categorie": club.categorie,
            "nombre_membres": club.nombre_membres_actuels,
            "nombre_activites": activites_par_club.get(club.id, 0),
            "taux_participation": taux,
        })

    total_global = participations.count()
    taux_global = round(participations.filter(statut='present').count() / total_global * 100, 1) if total_global else 0

    return {
        "club_filtre_nom": club_filtre_nom,
        "total_clubs": clubs.count(),
        "total_inscriptions": Inscription.objects.filter(club__in=clubs).count(),
        "taux_participation_global": taux_global,
        "clubs": rapport_clubs,
    }


class RisqueDesengagementView(APIView):
    """
    GET /api/predictions/risques-desengagement/
    Gestionnaires : recalcule et retourne le risque pour tous les élèves.
    Parent : ne voit que le risque de ses propres enfants.
    Filtre optionnel : ?niveau=eleve
    """
    permission_classes = [EstGestionnaire]  # inclut le parent, filtrage fait ci-dessous

    def get(self, request):
        user = request.user
        # Périmètre : parent -> ses enfants ; encadreur -> ses clubs ; sinon tout.
        if user.role == 'parent':
            filtre = {'eleve__in': user.enfants}
        elif user.role == 'encadreur':
            filtre = {'club__in': clubs_geres(user)}
        else:
            filtre = {}
        perimetre_complet = not filtre

        resultats = calculer_risques_desengagement_tous_eleves(**filtre)

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

        if perimetre_complet:
            # Supprime les risques obsolètes (inscription plus active).
            RisqueDesengagement.objects.exclude(
                pk__in=[o.pk for o in objets_sauvegardes]
            ).delete()

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
            activite = Activite.objects.select_related('club').get(id=activite_id)
        except Activite.DoesNotExist:
            return Response({"error": "Activité introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if not peut_gerer_club(request.user, activite.club):
            return Response({"error": "Vous ne gérez pas ce club."}, status=status.HTTP_403_FORBIDDEN)

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
        ids_geres = set(clubs_geres(request.user).values_list('id', flat=True))
        resultats_complets = resultats
        resultats = [r for r in resultats if r["club"].id in ids_geres]

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

        if request.user.role in ('administrateur', 'proviseur'):
            # Retire les alertes de clubs qui ne sont plus en difficulté.
            ClubEnDifficulte.objects.exclude(
                club_id__in=[r["club"].id for r in resultats_complets]
            ).delete()

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

        clubs_populaires = list(
            Club.objects.annotate(
                membres_annotes=Count('inscriptions', filter=Q(inscriptions__statut='validee'))
            ).order_by('-membres_annotes', 'nom')[:5]
        )

        activites_a_venir = Activite.objects.select_related('club').filter(
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
            {"mois": f"{MOIS_ABREGES[i['mois'].month - 1]} {i['mois'].year % 100:02d}", "total": i['total']}
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

        stats_clubs = (
            Club.objects.filter(statut='actif')
            .annotate(
                total_part=Count('inscriptions__participations'),
                presents=Count('inscriptions__participations', filter=Q(inscriptions__participations__statut='present')),
            )
        )
        clubs_taux_participation = sorted(
            [
                {
                    "nom": c.nom,
                    "taux_participation": round(c.presents / c.total_part * 100, 1) if c.total_part else 0,
                }
                for c in stats_clubs
            ],
            key=lambda c: c["taux_participation"], reverse=True,
        )[:5]

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
                {"nom": c.nom, "membres": c.membres_annotes, "categorie": c.categorie}
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

        rapport = construire_rapport_clubs(request)
        return Response({
            "total_clubs": rapport["total_clubs"],
            "total_inscriptions": rapport["total_inscriptions"],
            "taux_participation_global": rapport["taux_participation_global"],
            "clubs": rapport["clubs"],
        }, status=status.HTTP_200_OK)
        
class RapportPDFView(APIView):
    """
    GET /api/predictions/rapport-detaille/pdf/?club=<id>  (optionnel)
    Génère et retourne le rapport détaillé au format PDF (généré côté serveur).
    """
    permission_classes = [EstGestionnaireStrict]

    def get(self, request):
        rapport = construire_rapport_clubs(request)
        contexte = {
            "nom_etablissement": "Lycée — Gestion des clubs et activités",
            "date_generation": timezone.now().strftime("%d/%m/%Y à %H:%M"),
            "club_filtre": rapport["club_filtre_nom"],
            "total_clubs": rapport["total_clubs"],
            "total_inscriptions": rapport["total_inscriptions"],
            "taux_participation_global": rapport["taux_participation_global"],
            "clubs": rapport["clubs"],
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