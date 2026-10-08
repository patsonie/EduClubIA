# Imports : vues génériques DRF, jetons JWT, envoi d'emails, modèles et serializers du compte,
# règles de sécurité (anti brute-force, révocation des jetons) et notifications internes.
from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from django.http import FileResponse, Http404
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
import logging
import os
import secrets

from .models import (
    Utilisateur, JournalActivite, RelationParentEleve, CodeInvitation, MatriculeOfficiel, CentreInteret,
    DemandeRattachement,
)
from .matricules import importer_csv
from rest_framework.parsers import MultiPartParser
from .serializers import (
    InscriptionSerializer, UtilisateurSerializer,
    ConnexionSerializer, ChangementMotDePasseSerializer,
    ParentSerializer, RelationParentEleveSerializer,
    CompteEnAttenteSerializer, CodeInvitationSerializer,
    UtilisateurAdminSerializer,
    DemandeReinitialisationSerializer, ConfirmationReinitialisationSerializer,
    ValidationCodeSerializer, MatriculeOfficielSerializer, CentreInteretSerializer,
    DemandeRattachementSerializer,
)
from .securite import verifier_non_bloque, enregistrer_echec
from .perimetre import clubs_disponibles_pour_encadreur
from clubs.models import Club
from rest_framework.exceptions import PermissionDenied, ValidationError
from .permissions import EstAdminOuProviseur, EstAdministrateur, LoginRateThrottle, ChangementMotDePasseThrottle
from .authentication import revoquer_jetons
from notifications.models import Notification
from notifications.services import creer_notification
from .services import construire_dashboard_parent, demander_rattachement_par_matricule

# Journal technique (erreurs d'envoi d'email, etc.).
logger = logging.getLogger(__name__)


# Adresse IP du client (derrière un proxy comme Render, lit X-Forwarded-For si autorisé).
def get_ip_client(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if settings.USE_X_FORWARDED_FOR and x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


# Règle commune aux vues de validation/refus de comptes.
def verifier_droit_validation(request_user, compte_cible):
    """
    Règle métier : seul un administrateur peut valider/refuser un responsable
    pédagogique ou un autre administrateur. Un responsable pédagogique ne peut
    agir que sur les élèves, encadreurs et parents.
    """
    if request_user.role == Utilisateur.Role.ADMINISTRATEUR:
        return True
    if request_user.role == Utilisateur.Role.PROVISEUR:
        return compte_cible.role not in [Utilisateur.Role.ADMINISTRATEUR, Utilisateur.Role.PROVISEUR]
    return False


# === Inscription publique ===
class InscriptionView(generics.CreateAPIView):
    """POST /api/auth/register/ — Création d'un nouveau compte utilisateur (sauf administrateur)."""
    queryset = Utilisateur.objects.all()
    serializer_class = InscriptionSerializer
    permission_classes = [permissions.AllowAny]

    # Message renvoyé après l'inscription selon le rôle (affiché par la page d'inscription).
    MESSAGES_PAR_ROLE = {
        'eleve': "Votre compte a été créé. Il est en attente de validation.",
        'encadreur': "Votre demande d'inscription a été envoyée. Votre compte sera activé après validation par le responsable pédagogique.",
        'proviseur': "Votre demande d'inscription a été enregistrée avec succès. Votre compte est actuellement en attente de validation. Un code d'invitation vous sera envoyé par l'administrateur après vérification de votre acte de nomination.",
        'parent': "Votre compte a été créé. Le rattachement à votre enfant sera effectif après validation par l'administration.",
    }

    # Valide les données, crée le compte, trace l'action puis répond.
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        utilisateur = serializer.save()

        JournalActivite.objects.create(
            utilisateur=utilisateur,
            action="Inscription",
            adresse_ip=get_ip_client(request),
        )

        message_statut = self.MESSAGES_PAR_ROLE.get(utilisateur.role, "Votre compte a été créé.")

        reponse = {
            "utilisateur": UtilisateurSerializer(utilisateur).data,
            "statut_validation": utilisateur.statut_validation,
            "message": message_statut,
        }

        # Un compte en attente ne reçoit pas de token immédiatement exploitable :
        # il doit d'abord être validé.
        if utilisateur.compte_actif_utilisable:
            refresh = RefreshToken.for_user(utilisateur)
            reponse["refresh"] = str(refresh)
            reponse["access"] = str(refresh.access_token)

        return Response(reponse, status=status.HTTP_201_CREATED)


# === Connexion : renvoie les jetons JWT (access + refresh) et le profil ===
class ConnexionView(APIView):
    """POST /api/auth/login/ — Connexion et génération des tokens JWT."""
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = ConnexionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        utilisateur = serializer.validated_data['utilisateur']

        refresh = RefreshToken.for_user(utilisateur)

        JournalActivite.objects.create(
            utilisateur=utilisateur,
            action="Connexion",
            adresse_ip=get_ip_client(request),
        )

        return Response({
            "utilisateur": UtilisateurSerializer(utilisateur).data,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_200_OK)


# === Déconnexion : le refresh token est mis en liste noire (inutilisable) ===
class DeconnexionView(APIView):
    """POST /api/auth/logout/ — Déconnexion (blacklist du refresh token)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()

            JournalActivite.objects.create(
                utilisateur=request.user,
                action="Déconnexion",
                adresse_ip=get_ip_client(request),
            )

            return Response({"message": "Déconnexion réussie."}, status=status.HTTP_205_RESET_CONTENT)
        except Exception:
            return Response({"error": "Token invalide."}, status=status.HTTP_400_BAD_REQUEST)


# === Profil de l'utilisateur connecté (page Paramètres) ===
class ProfilView(generics.RetrieveUpdateAPIView):
    """GET/PUT/PATCH /api/auth/profil/ — Consultation et modification du profil."""
    serializer_class = UtilisateurSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


# === Liste publique des centres d'intérêt (inscription, profil) ===
class CentresInteretView(generics.ListAPIView):
    """
    GET /api/auth/interets/ — Centres d'intérêt actifs, avec leur catégorie.
    Public : la page d'inscription en a besoin avant toute connexion (aucune donnée personnelle).
    """
    serializer_class = CentreInteretSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def get_queryset(self):
        return CentreInteret.objects.filter(actif=True).select_related('categorie')


# === Changement de mot de passe : révoque ensuite toutes les sessions ouvertes ===
class ChangementMotDePasseView(APIView):
    """POST /api/auth/changer-mot-de-passe/ — Modifier son mot de passe."""
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ChangementMotDePasseThrottle]

    def post(self, request):
        serializer = ChangementMotDePasseSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        utilisateur = request.user
        utilisateur.set_password(serializer.validated_data['nouveau_mot_de_passe'])
        utilisateur.save()
        revoquer_jetons(utilisateur)

        JournalActivite.objects.create(
            utilisateur=utilisateur,
            action="Changement de mot de passe",
            adresse_ip=get_ip_client(request),
        )

        return Response({"message": "Mot de passe modifié avec succès."}, status=status.HTTP_200_OK)


# === Gestion des parents et de leurs liens avec les élèves (administration / RP) ===
class ParentViewSet(viewsets.ModelViewSet):
    """
    CRUD complet des comptes parents, réservé aux administrateurs/proviseurs.
    Recherche : ?search=fouda
    """
    queryset = Utilisateur.objects.filter(role=Utilisateur.Role.PARENT)
    serializer_class = ParentSerializer
    permission_classes = [EstAdminOuProviseur]
    filter_backends = [filters.SearchFilter]
    search_fields = ['nom', 'prenom', 'email', 'profession']

    # Valider une demande de lien existante, sinon créer directement un lien validé.
    @action(detail=True, methods=['post'])
    def lier_enfant(self, request, pk=None):
        """
        POST /api/parents/{id}/lier_enfant/  body: {"enfant": <id_eleve>}
        Crée un lien validé, ou valide une demande de rattachement en attente.
        """
        parent = self.get_object()
        enfant_id = request.data.get('enfant')

        demande = RelationParentEleve.objects.filter(
            parent=parent, enfant_id=enfant_id, statut=RelationParentEleve.Statut.EN_ATTENTE
        ).first()
        if demande:
            demande.statut = RelationParentEleve.Statut.VALIDEE
            demande.cree_par = request.user
            demande.save()
            JournalActivite.objects.create(
                utilisateur=request.user, action="Rattachement parent validé",
                details=f"parent={parent.id} enfant={demande.enfant_id}",
                adresse_ip=get_ip_client(request),
            )
            creer_notification(
                parent, Notification.TypeNotification.AUTRE,
                "Rattachement validé",
                f"Votre rattachement à {demande.enfant.nom_complet} a été validé. Vous pouvez désormais suivre ses activités.",
            )
            return Response(RelationParentEleveSerializer(demande).data, status=status.HTTP_200_OK)

        data = {'parent': parent.id, 'enfant': enfant_id}
        serializer = RelationParentEleveSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(cree_par=request.user, statut=RelationParentEleve.Statut.VALIDEE)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # Refuser une demande de lien : elle est supprimée et le parent est notifié.
    @action(detail=True, methods=['post'])
    def refuser_rattachement(self, request, pk=None):
        """POST /api/auth/parents/{id}/refuser_rattachement/  body: {"enfant": <id_eleve>}"""
        parent = self.get_object()
        demande = RelationParentEleve.objects.filter(
            parent=parent, enfant_id=request.data.get('enfant'),
            statut=RelationParentEleve.Statut.EN_ATTENTE,
        ).select_related('enfant').first()
        if not demande:
            return Response({"error": "Demande introuvable."}, status=status.HTTP_404_NOT_FOUND)

        nom_enfant = demande.enfant.nom_complet
        demande.delete()
        JournalActivite.objects.create(
            utilisateur=request.user, action="Rattachement parent refusé",
            details=f"parent={parent.id}", adresse_ip=get_ip_client(request),
        )
        creer_notification(
            parent, Notification.TypeNotification.AUTRE,
            "Rattachement refusé",
            f"Votre demande de rattachement à {nom_enfant} n'a pas pu être validée. Contactez l'administration.",
        )
        return Response({"message": "Demande refusée."}, status=status.HTTP_200_OK)

    # Liste des demandes de lien en attente (page « Rattachements »).
    @action(detail=False, methods=['get'])
    def demandes_rattachement(self, request):
        """GET /api/auth/parents/demandes_rattachement/ — demandes parent→élève en attente de validation."""
        demandes = RelationParentEleve.objects.filter(
            statut=RelationParentEleve.Statut.EN_ATTENTE
        ).select_related('parent', 'enfant')
        return Response(RelationParentEleveSerializer(demandes, many=True).data)

    # Supprimer un lien parent ↔ élève.
    @action(detail=True, methods=['post'])
    def delier_enfant(self, request, pk=None):
        """POST /api/parents/{id}/delier_enfant/  body: {"enfant": <id_eleve>}"""
        parent = self.get_object()
        enfant_id = request.data.get('enfant')
        supprimee, _ = RelationParentEleve.objects.filter(parent=parent, enfant_id=enfant_id).delete()
        if supprimee:
            return Response({"message": "Lien supprimé."}, status=status.HTTP_200_OK)
        return Response({"error": "Lien introuvable."}, status=status.HTTP_404_NOT_FOUND)


# === Un parent consulte ses enfants (liens validés uniquement) ===
class MesEnfantsView(generics.ListAPIView):
    """GET /api/auth/mes-enfants/ — un parent connecté consulte la liste de ses enfants."""
    serializer_class = UtilisateurSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role != Utilisateur.Role.PARENT:
            return Utilisateur.objects.none()
        return self.request.user.enfants


# === Clubs sans encadreur (choix du club à l'inscription et dans le profil) ===
class ClubsDisponiblesView(APIView):
    """
    GET /api/auth/clubs-disponibles/ — clubs sans encadreur (id, nom uniquement).
    Public : la page d'inscription en a besoin avant toute connexion. Pour un encadreur
    connecté, son club actuel est inclus afin de pouvoir le garder.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        encadreur = request.user if (
            request.user.is_authenticated and request.user.role == Utilisateur.Role.ENCADREUR
        ) else None
        clubs = clubs_disponibles_pour_encadreur(encadreur).order_by('nom').values('id', 'nom')
        return Response(list(clubs))


# === Demande de rattachement d'un parent à un enfant par matricule ===
# Le matricule ne prouve pas la filiation : la demande reste « en attente » jusqu'à
# sa validation par un gestionnaire (DemandeRattachementViewSet.accepter).
class AssocierEnfantMatriculeView(APIView):
    """
    POST /api/auth/mes-enfants/associer/  body: {"matricule": "..."}
    Crée une demande de rattachement en attente (voir services.demander_rattachement_par_matricule).
    La réponse est toujours la même, que le matricule existe ou non.
    Nombre de demandes limité par compte (5 par quart d'heure).
    """
    permission_classes = [permissions.IsAuthenticated]

    MESSAGE_NEUTRE = (
        "Votre demande a été envoyée. Si ce matricule correspond à un élève, elle sera examinée "
        "par le responsable pédagogique avant que vous puissiez suivre votre enfant."
    )

    def post(self, request):
        parent = request.user
        if parent.role != Utilisateur.Role.PARENT:
            return Response({"error": "Réservé aux parents."}, status=status.HTTP_403_FORBIDDEN)

        matricule = str(request.data.get('matricule') or '').strip()
        if not matricule:
            return Response({"matricule": ["Le matricule est requis."]}, status=status.HTTP_400_BAD_REQUEST)

        # Chaque demande compte, qu'elle aboutisse ou non (limite le volume de demandes).
        verifier_non_bloque('rattachement', parent.pk)
        enregistrer_echec('rattachement', parent.pk)

        demande = demander_rattachement_par_matricule(parent, matricule)
        if demande:
            JournalActivite.objects.create(
                utilisateur=parent, action="Demande de rattachement par matricule",
                details=f"parent={parent.id} demande={demande.id}", adresse_ip=get_ip_client(request),
            )

        # Même réponse dans tous les cas (matricule inconnu, demande déjà faite, lien existant).
        return Response({"message": self.MESSAGE_NEUTRE}, status=status.HTTP_202_ACCEPTED)


# === Demandes d'association par nom de l'enfant (parent → responsable pédagogique) ===
class DemandeRattachementViewSet(viewsets.ModelViewSet):
    """
    Demandes d'association par nom complet de l'enfant.
    - Parent : crée et consulte ses propres demandes.
    - Administrateur / responsable pédagogique : consulte toutes les demandes,
      les accepte en désignant l'élève (POST {id}/accepter/ {"enfant": id}) ou les refuse.
    """
    serializer_class = DemandeRattachementSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']
    pagination_class = None

    # Chacun ne voit que ce qui le concerne : le parent ses demandes, le gestionnaire toutes.
    def get_queryset(self):
        user = self.request.user
        base = DemandeRattachement.objects.select_related('parent')
        if user.role in (Utilisateur.Role.ADMINISTRATEUR, Utilisateur.Role.PROVISEUR):
            statut = self.request.query_params.get('statut')
            return base.filter(statut=statut) if statut else base
        if user.role == Utilisateur.Role.PARENT:
            return base.filter(parent=user)
        return base.none()

    # Création par un parent, avec refus des doublons et notification des responsables pédagogiques.
    def perform_create(self, serializer):
        user = self.request.user
        if user.role != Utilisateur.Role.PARENT:
            raise PermissionDenied("Seuls les parents peuvent demander une association.")
        nom = serializer.validated_data['nom_complet_enfant']
        if DemandeRattachement.objects.filter(
            parent=user, nom_complet_enfant__iexact=nom, statut=DemandeRattachement.Statut.EN_ATTENTE,
        ).exists():
            raise ValidationError({"nom_complet_enfant": "Une demande pour cet enfant est déjà en attente."})
        demande = serializer.save(parent=user)

        gestionnaires = Utilisateur.objects.filter(
            role=Utilisateur.Role.PROVISEUR, statut_validation=Utilisateur.StatutValidation.VALIDE, is_active=True,
        )
        for gestionnaire in gestionnaires:
            creer_notification(
                gestionnaire, Notification.TypeNotification.AUTRE,
                "Demande d'association parent",
                f"{user.nom_complet} demande à être associé(e) à l'élève « {demande.nom_complet_enfant} ».",
            )

    # Outils internes : contrôle du rôle gestionnaire et de l'état « en attente » de la demande.
    def _verifier_gestionnaire(self, request):
        if request.user.role not in (Utilisateur.Role.ADMINISTRATEUR, Utilisateur.Role.PROVISEUR):
            raise PermissionDenied("Réservé au responsable pédagogique et à l'administration.")

    def _demande_en_attente(self):
        demande = self.get_object()
        if demande.statut != DemandeRattachement.Statut.EN_ATTENTE:
            raise ValidationError({"statut": "Cette demande a déjà été traitée."})
        return demande

    # Accepter : crée (ou valide) le lien parent ↔ élève choisi, puis notifie le parent.
    @action(detail=True, methods=['post'])
    def accepter(self, request, pk=None):
        from django.utils import timezone
        self._verifier_gestionnaire(request)
        demande = self._demande_en_attente()
        # Élève choisi par le gestionnaire, sinon celui pré-désigné par le matricule.
        enfant_id = request.data.get('enfant') or demande.enfant_id
        enfant = Utilisateur.objects.filter(pk=enfant_id, role=Utilisateur.Role.ELEVE).first()
        if not enfant:
            return Response({"enfant": ["Choisissez l'élève correspondant."]}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            relation, _ = RelationParentEleve.objects.get_or_create(
                parent=demande.parent, enfant=enfant,
                defaults={'statut': RelationParentEleve.Statut.VALIDEE, 'cree_par': request.user},
            )
            if relation.statut != RelationParentEleve.Statut.VALIDEE:
                relation.statut = RelationParentEleve.Statut.VALIDEE
                relation.cree_par = request.user
                relation.save(update_fields=['statut', 'cree_par'])
            demande.statut = DemandeRattachement.Statut.ACCEPTEE
            demande.enfant = enfant
            demande.traitee_par = request.user
            demande.date_traitement = timezone.now()
            demande.save()

        JournalActivite.objects.create(
            utilisateur=request.user, action="Demande d'association parent acceptée",
            details=f"parent={demande.parent_id} enfant={enfant.id}", adresse_ip=get_ip_client(request),
        )
        creer_notification(
            demande.parent, Notification.TypeNotification.AUTRE,
            "Association validée",
            f"Votre demande d'association à {enfant.nom_complet} a été acceptée. "
            "Vous pouvez désormais suivre ses activités.",
        )
        return Response(self.get_serializer(demande).data, status=status.HTTP_200_OK)

    # Refuser : la demande est close et le parent est informé.
    @action(detail=True, methods=['post'])
    def refuser(self, request, pk=None):
        from django.utils import timezone
        self._verifier_gestionnaire(request)
        demande = self._demande_en_attente()
        demande.statut = DemandeRattachement.Statut.REFUSEE
        demande.traitee_par = request.user
        demande.date_traitement = timezone.now()
        demande.save()
        creer_notification(
            demande.parent, Notification.TypeNotification.AUTRE,
            "Demande d'association refusée",
            f"Votre demande d'association à « {demande.nom_complet_enfant} » n'a pas pu être validée. "
            "Contactez l'administration.",
        )
        return Response(self.get_serializer(demande).data, status=status.HTTP_200_OK)


# === Tableau de bord du parent (enfants, clubs, présences) ===
class TableauDeBordParentView(APIView):
    """GET /api/auth/dashboard-parent/ — tableau de bord complet pour le parent connecté."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role != Utilisateur.Role.PARENT:
            return Response(
                {"error": "Cet endpoint est réservé aux parents."},
                status=status.HTTP_403_FORBIDDEN,
            )
        data = construire_dashboard_parent(request.user)
        return Response(data, status=status.HTTP_200_OK)


# === Comptes en attente de validation (page « Comptes en attente ») ===
class ComptesEnAttenteView(generics.ListAPIView):
    """GET /api/auth/comptes-en-attente/ — liste des comptes (encadreur, élève, responsable) en attente."""
    serializer_class = CompteEnAttenteSerializer
    permission_classes = [EstAdminOuProviseur]

    def get_queryset(self):
        statuts_en_cours = [
            Utilisateur.StatutValidation.EN_ATTENTE,
            Utilisateur.StatutValidation.CODE_ENVOYE,
            Utilisateur.StatutValidation.CODE_VALIDE,
        ]
        queryset = Utilisateur.objects.filter(statut_validation__in=statuts_en_cours)

        # Un responsable pédagogique ne voit jamais un autre responsable pédagogique
        # en cours de traitement (à aucune étape du processus) : ce cas est réservé
        # aux administrateurs, du début à la fin du parcours.
        if self.request.user.role != Utilisateur.Role.ADMINISTRATEUR:
            queryset = queryset.exclude(role=Utilisateur.Role.PROVISEUR)

        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        return queryset


# === Validation d'un compte (élève, encadreur professionnel ou vacataire, parent...) ===
# Le responsable pédagogique valide les encadreurs ; seul l'administrateur valide un RP.
class ValiderCompteView(APIView):
    """POST /api/auth/comptes/{id}/valider/"""
    permission_classes = [EstAdminOuProviseur]

    def post(self, request, pk):
        from django.utils import timezone
        try:
            utilisateur = Utilisateur.objects.get(id=pk)
        except Utilisateur.DoesNotExist:
            return Response({"error": "Compte introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if not verifier_droit_validation(request.user, utilisateur):
            return Response(
                {"error": "Seul un administrateur peut valider le compte d'un responsable pédagogique."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Un RP doit avoir validé son code reçu par email avant l'activation finale.
        if (
            utilisateur.role == Utilisateur.Role.PROVISEUR
            and utilisateur.statut_validation != Utilisateur.StatutValidation.CODE_VALIDE
        ):
            return Response(
                {"error": "Ce compte responsable pédagogique doit d'abord avoir un code validé avant l'activation finale."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Le compte devient actif : la connexion est désormais autorisée.
        utilisateur.statut_validation = Utilisateur.StatutValidation.VALIDE
        utilisateur.valide_par = request.user
        utilisateur.date_validation = timezone.now()
        utilisateur.save()

        # Email de confirmation pour le responsable pédagogique.
        if utilisateur.role == Utilisateur.Role.PROVISEUR:
            send_mail(
                subject="EduClubIA — Compte activé",
                message=(
                    f"Bonjour {utilisateur.prenom},\n\n"
                    f"Félicitations ! Votre compte Responsable pédagogique est désormais actif.\n"
                    f"Vous pouvez vous connecter sur {settings.FRONTEND_BASE_URL}/connexion/"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[utilisateur.email],
                fail_silently=True,
            )

        return Response({"message": f"Compte de {utilisateur.nom_complet} validé avec succès."}, status=status.HTTP_200_OK)


# === Refus d'un compte : statut « refusé », sessions coupées, club de l'encadreur libéré ===
class RefuserCompteView(APIView):
    """POST /api/auth/comptes/{id}/refuser/  body: {"motif": "..."}"""
    permission_classes = [EstAdminOuProviseur]

    def post(self, request, pk):
        try:
            utilisateur = Utilisateur.objects.get(id=pk)
        except Utilisateur.DoesNotExist:
            return Response({"error": "Compte introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if not verifier_droit_validation(request.user, utilisateur):
            return Response(
                {"error": "Seul un administrateur peut refuser le compte d'un responsable pédagogique."},
                status=status.HTTP_403_FORBIDDEN,
            )

        utilisateur.statut_validation = Utilisateur.StatutValidation.REFUSE
        utilisateur.motif_refus = request.data.get('motif', '')
        utilisateur.save()
        revoquer_jetons(utilisateur)
        if utilisateur.role == Utilisateur.Role.ENCADREUR:
            # Le club réservé à l'inscription redevient disponible pour un autre encadreur.
            Club.objects.filter(responsable=utilisateur).update(responsable=None)

        return Response({"message": f"Compte de {utilisateur.nom_complet} refusé."}, status=status.HTTP_200_OK)


# === Codes d'invitation (administrateur) : le code est généré aléatoirement côté serveur ===
class CodeInvitationViewSet(viewsets.ModelViewSet):
    """CRUD des codes d'invitation/activation, réservé aux administrateurs."""
    queryset = CodeInvitation.objects.all()
    serializer_class = CodeInvitationSerializer
    permission_classes = [EstAdministrateur]

    def perform_create(self, serializer):
        code = secrets.token_hex(4).upper()
        serializer.save(code=code, cree_par=self.request.user)


# === Gestion de tous les utilisateurs (page « Utilisateurs ») ===
class UtilisateurAdminViewSet(viewsets.ModelViewSet):
    """
    Gestion des utilisateurs.
    - Administrateur : accès complet (tous rôles).
    - Responsable pédagogique : lecture, suspension et réactivation des élèves,
      encadreurs et parents uniquement ; jamais les administrateurs ni les autres
      responsables, et aucune création/modification/suppression.
    Recherche : ?search=nom  |  Filtre : ?role=eleve&statut_validation=en_attente
    """
    serializer_class = UtilisateurAdminSerializer
    permission_classes = [EstAdminOuProviseur]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['nom', 'prenom', 'email', 'matricule']
    filterset_fields = ['role', 'statut_validation', 'is_active']

    ACTIONS_ECRITURE_ADMIN = ('create', 'update', 'partial_update', 'destroy')

    # Le RP ne voit ni les administrateurs ni les autres RP.
    def get_queryset(self):
        queryset = Utilisateur.objects.all().order_by('-date_joined')
        if self.request.user.role != Utilisateur.Role.ADMINISTRATEUR:
            queryset = queryset.exclude(
                role__in=[Utilisateur.Role.ADMINISTRATEUR, Utilisateur.Role.PROVISEUR]
            )
        return queryset

    # Création, modification et suppression réservées à l'administrateur.
    def get_permissions(self):
        if self.action in self.ACTIONS_ECRITURE_ADMIN:
            return [EstAdministrateur()]
        return super().get_permissions()

    # Empêche de se suspendre ou se réactiver soi-même.
    def _verifier_cible(self, request, utilisateur):
        if utilisateur.id == request.user.id:
            return Response(
                {"error": "Vous ne pouvez pas modifier votre propre statut."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None

    # Suspendre : le compte ne peut plus se connecter et ses sessions sont coupées.
    @action(detail=True, methods=['post'])
    def suspendre(self, request, pk=None):
        utilisateur = self.get_object()
        refus = self._verifier_cible(request, utilisateur)
        if refus:
            return refus
        utilisateur.statut_validation = Utilisateur.StatutValidation.SUSPENDU
        utilisateur.save()
        revoquer_jetons(utilisateur)
        return Response({"message": f"{utilisateur.nom_complet} suspendu."}, status=status.HTTP_200_OK)

    # Réactiver un compte suspendu.
    @action(detail=True, methods=['post'])
    def reactiver(self, request, pk=None):
        utilisateur = self.get_object()
        refus = self._verifier_cible(request, utilisateur)
        if refus:
            return refus
        utilisateur.statut_validation = Utilisateur.StatutValidation.VALIDE
        utilisateur.save()
        return Response({"message": f"{utilisateur.nom_complet} réactivé."}, status=status.HTTP_200_OK)

    # Suppression d'un compte (jamais le sien).
    def perform_destroy(self, instance):
        if instance.id == self.request.user.id:
            raise PermissionDenied("Vous ne pouvez pas supprimer votre propre compte.")
        instance.delete()


# === Téléchargement sécurisé d'un justificatif (jamais d'URL de stockage directe) ===
class TelechargerJustificatifView(APIView):
    """
    GET /api/auth/justificatif/{utilisateur_id}/
    Sert le fichier justificatif d'un encadreur, réservé aux administrateurs,
    responsables pédagogiques, et à l'encadreur concerné lui-même.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, utilisateur_id):
        try:
            utilisateur = Utilisateur.objects.get(id=utilisateur_id)
        except Utilisateur.DoesNotExist:
            raise Http404("Utilisateur introuvable.")

        est_gestionnaire = (
            request.user.role == 'administrateur'
            or (
                request.user.role == 'proviseur'
                and utilisateur.role not in ['administrateur', 'proviseur']
            )
        )
        est_lui_meme = request.user.id == utilisateur.id

        if not (est_gestionnaire or est_lui_meme):
            return Response(
                {"error": "Vous n'êtes pas autorisé à consulter ce document."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not utilisateur.justificatif:
            raise Http404("Aucun justificatif pour cet utilisateur.")

        try:
            fichier = utilisateur.justificatif.open('rb')
        except (FileNotFoundError, OSError):
            raise Http404("Fichier introuvable sur le serveur.")

        return FileResponse(fichier, as_attachment=False)


# === Mot de passe oublié : envoi du lien de réinitialisation par email ===
class DemandeReinitialisationMotDePasseView(APIView):
    """
    POST /api/auth/mot-de-passe-oublie/  body: {"email": "..."}
    Envoie un email avec un lien de réinitialisation si le compte existe.
    Répond toujours de la même façon, que l'email existe ou non (anti-énumération).
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = DemandeReinitialisationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        utilisateur = Utilisateur.objects.filter(
            email=email, is_active=True,
            statut_validation__in=[
                Utilisateur.StatutValidation.VALIDE,
                Utilisateur.StatutValidation.EN_ATTENTE,
                Utilisateur.StatutValidation.CODE_ENVOYE,
                Utilisateur.StatutValidation.CODE_VALIDE,
            ],
        ).first()

        if utilisateur:
            uidb64 = urlsafe_base64_encode(force_bytes(utilisateur.pk))
            token = default_token_generator.make_token(utilisateur)
            lien_reinitialisation = f"{settings.FRONTEND_BASE_URL}/reinitialiser-mot-de-passe/{uidb64}/{token}/"

            send_mail(
                subject="EduClubIA — Réinitialisation de votre mot de passe",
                message=(
                    f"Bonjour {utilisateur.prenom},\n\n"
                    f"Vous avez demandé la réinitialisation de votre mot de passe.\n"
                    f"Cliquez sur ce lien pour choisir un nouveau mot de passe :\n\n"
                    f"{lien_reinitialisation}\n\n"
                    f"Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.\n"
                    f"Ce lien expire après usage ou changement de mot de passe."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[utilisateur.email],
                fail_silently=True,
            )

        return Response(
            {"message": "Si un compte existe avec cet email, un lien de réinitialisation a été envoyé."},
            status=status.HTTP_200_OK,
        )


# === Mot de passe oublié : enregistrement du nouveau mot de passe ===
class ConfirmerReinitialisationMotDePasseView(APIView):
    """
    POST /api/auth/reinitialiser-mot-de-passe/
    body: {"uidb64": "...", "token": "...", "nouveau_mot_de_passe": "..."}
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = ConfirmationReinitialisationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        utilisateur = serializer.validated_data['utilisateur']
        utilisateur.set_password(serializer.validated_data['nouveau_mot_de_passe'])
        utilisateur.save()
        revoquer_jetons(utilisateur)

        JournalActivite.objects.create(
            utilisateur=utilisateur,
            action="Réinitialisation du mot de passe",
        )

        return Response(
            {"message": "Mot de passe réinitialisé avec succès. Vous pouvez maintenant vous connecter."},
            status=status.HTTP_200_OK,
        )


# === Envoi du code d'invitation au responsable pédagogique (par l'administrateur) ===
class EnvoyerCodeValidationView(APIView):
    """
    POST /api/auth/comptes/{id}/envoyer_code/
    Envoie par email le code déjà généré automatiquement à l'inscription.
    Réservé aux administrateurs. Fixe une expiration de 24h à chaque envoi/renvoi.
    """
    permission_classes = [EstAdminOuProviseur]

    def post(self, request, pk):
        from django.utils import timezone
        from datetime import timedelta

        try:
            utilisateur = Utilisateur.objects.get(id=pk, role=Utilisateur.Role.PROVISEUR)
        except Utilisateur.DoesNotExist:
            return Response({"error": "Compte responsable pédagogique introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if request.user.role != Utilisateur.Role.ADMINISTRATEUR:
            return Response(
                {"error": "Seul un administrateur peut envoyer un code d'invitation à un responsable pédagogique."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not utilisateur.code_validation_compte:
            # Sécurité : si le code n'existait pas encore (compte créé avant cette mise à jour), on le génère.
            utilisateur.code_validation_compte = f"RP-{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"

        # Envoi d'abord : le statut ne passe à « code envoyé » que si le serveur
        # SMTP a accepté le message, sinon l'administrateur est prévenu de l'échec.
        try:
            send_mail(
                subject="EduClubIA — Votre code d'invitation",
                message=(
                    f"Bonjour {utilisateur.prenom},\n\n"
                    f"Votre acte de nomination a été reçu. Voici votre code d'invitation "
                    f"(valable 24 heures) :\n\n"
                    f"{utilisateur.code_validation_compte}\n\n"
                    f"Rendez-vous sur la page de validation de compte et saisissez ce code "
                    f"avec votre adresse email pour poursuivre votre inscription.\n\n"
                    f"{settings.FRONTEND_BASE_URL}/validation-compte/"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[utilisateur.email],
                fail_silently=False,
            )
        except Exception:
            logger.exception("Échec d'envoi du code d'invitation au compte %s", utilisateur.pk)
            return Response(
                {"error": "L'email n'a pas pu être envoyé (serveur de messagerie injoignable ou refusé). "
                          "Vérifiez la configuration SMTP puis réessayez."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        utilisateur.statut_validation = Utilisateur.StatutValidation.CODE_ENVOYE
        utilisateur.date_code_envoye = timezone.now()
        utilisateur.date_expiration_code = timezone.now() + timedelta(hours=24)
        utilisateur.save()

        return Response(
            {"message": f"Code d'invitation envoyé à {utilisateur.email}."},
            status=status.HTTP_200_OK,
        )


# === Renvoi du code (même traitement que l'envoi) ===
class RegenererCodeValidationView(APIView):
    """POST /api/auth/comptes/{id}/regenerer_code/ — identique à envoyer_code, réutilisable."""
    permission_classes = [EstAdminOuProviseur]

    def post(self, request, pk):
        return EnvoyerCodeValidationView().post(request, pk)


# === Le RP saisit le code reçu : son compte passe à « code validé » ===
class ValiderCodeCompteView(APIView):
    """
    POST /api/auth/valider-code/  body: {"email": "...", "code": "..."}
    Étape self-service (public) : le responsable pédagogique valide son code reçu par email.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        from django.utils import timezone
        serializer = ValidationCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        utilisateur = serializer.validated_data['utilisateur']
        utilisateur.statut_validation = Utilisateur.StatutValidation.CODE_VALIDE
        utilisateur.date_code_valide = timezone.now()
        utilisateur.save()

        return Response(
            {"message": "Votre identité a été vérifiée. Votre compte est maintenant en attente de validation finale par l'administrateur."},
            status=status.HTTP_200_OK,
        )
    
# === Le RP demande un nouveau code après expiration ===
class RenvoyerCodeExpireView(APIView):
    """
    POST /api/auth/renvoyer-code-expire/  body: {"email": "..."}
    Self-service : le responsable pédagogique demande un nouveau code après expiration.
    Génère un nouveau code, une nouvelle expiration, et renvoie l'email.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        from django.utils import timezone
        from datetime import timedelta

        serializer = DemandeReinitialisationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        utilisateur = Utilisateur.objects.filter(email=email, role=Utilisateur.Role.PROVISEUR).first()

        if utilisateur and utilisateur.statut_validation == Utilisateur.StatutValidation.CODE_ENVOYE:
            utilisateur.code_validation_compte = f"RP-{secrets.token_hex(8).upper()}"
            utilisateur.date_code_envoye = timezone.now()
            utilisateur.date_expiration_code = timezone.now() + timedelta(hours=24)
            utilisateur.save()

            try:
                send_mail(
                    subject="EduClubIA — Nouveau code d'invitation",
                    message=(
                        f"Bonjour {utilisateur.prenom},\n\n"
                        f"Voici votre nouveau code d'invitation (valable 24 heures) :\n\n"
                        f"{utilisateur.code_validation_compte}\n\n"
                        f"{settings.FRONTEND_BASE_URL}/validation-compte/"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[utilisateur.email],
                    fail_silently=False,
                )
            except Exception:
                # Réponse inchangée (anti-énumération), mais l'échec reste visible dans les logs.
                logger.exception("Échec d'envoi du nouveau code au compte %s", utilisateur.pk)

        # Même réponse dans tous les cas : ne révèle ni l'existence d'un compte,
        # ni son état de validation.
        return Response(
            {"message": "Si un compte est éligible, un nouveau code lui a été envoyé."},
            status=status.HTTP_200_OK,
        )


# === Liste officielle des matricules : consultation et import CSV ===
class MatriculeOfficielViewSet(viewsets.ModelViewSet):
    """
    Liste officielle des matricules de l'établissement.
    Lecture : administrateur / responsable pédagogique. Import et suppression : administrateur.
    POST /api/auth/matricules/importer/  (multipart : fichier=<csv>, role=eleve|encadreur)
    """
    serializer_class = MatriculeOfficielSerializer
    permission_classes = [EstAdminOuProviseur]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['matricule', 'nom', 'prenom', 'classe']
    filterset_fields = ['role']
    http_method_names = ['get', 'post', 'delete', 'head', 'options']
    queryset = MatriculeOfficiel.objects.all()

    # Lecture pour administrateur et RP ; import et suppression pour l'administrateur seul.
    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [EstAdminOuProviseur()]
        return [EstAdministrateur()]

    # Transmet au serializer les matricules déjà utilisés (colonne « compte créé »).
    def get_serializer_context(self):
        contexte = super().get_serializer_context()
        contexte['matricules_utilises'] = set(
            Utilisateur.objects.exclude(matricule__isnull=True).values_list('matricule', flat=True)
        )
        return contexte

    # Pas de création ligne par ligne : on passe par l'import CSV.
    def create(self, request, *args, **kwargs):
        return Response({"error": "Utilisez /matricules/importer/."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(detail=False, methods=['post'], url_path='importer', parser_classes=[MultiPartParser])
    # Import d'un fichier CSV (2 Mo max), puis trace dans le journal d'activité.
    def importer(self, request):
        fichier = request.FILES.get('fichier')
        role = request.data.get('role', MatriculeOfficiel.Role.ELEVE)
        if role not in MatriculeOfficiel.Role.values:
            return Response({"error": f"role invalide. Valeurs : {MatriculeOfficiel.Role.values}."},
                            status=status.HTTP_400_BAD_REQUEST)
        if not fichier:
            return Response({"error": "Fichier CSV requis (champ `fichier`)."}, status=status.HTTP_400_BAD_REQUEST)
        if fichier.size > 2 * 1024 * 1024:
            return Response({"error": "Fichier trop volumineux (2 Mo maximum)."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            resultat = importer_csv(fichier.read(), role)
        except (ValueError, UnicodeDecodeError) as erreur:
            return Response({"error": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        JournalActivite.objects.create(
            utilisateur=request.user, action="Import de la liste officielle des matricules",
            details=f"role={role} crees={resultat['crees']} maj={resultat['mis_a_jour']}",
            adresse_ip=get_ip_client(request),
        )
        return Response(resultat, status=status.HTTP_200_OK)
