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
import os
import secrets

from .models import Utilisateur, JournalActivite, RelationParentEleve, CodeInvitation, MatriculeOfficiel, CentreInteret
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
)
from rest_framework.exceptions import PermissionDenied
from .permissions import EstAdminOuProviseur, EstAdministrateur, LoginRateThrottle, ChangementMotDePasseThrottle
from .authentication import revoquer_jetons
from notifications.models import Notification
from notifications.services import creer_notification
from .services import construire_dashboard_parent


def get_ip_client(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if settings.USE_X_FORWARDED_FOR and x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


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


class InscriptionView(generics.CreateAPIView):
    """POST /api/auth/register/ — Création d'un nouveau compte utilisateur (sauf administrateur)."""
    queryset = Utilisateur.objects.all()
    serializer_class = InscriptionSerializer
    permission_classes = [permissions.AllowAny]

    MESSAGES_PAR_ROLE = {
        'eleve': "Votre compte a été créé. Il est en attente de validation.",
        'encadreur': "Votre demande d'inscription a été envoyée. Elle sera examinée par l'administration.",
        'proviseur': "Votre demande d'inscription a été enregistrée avec succès. Votre compte est actuellement en attente de validation. Un code d'invitation vous sera envoyé par l'administrateur après vérification de votre acte de nomination.",
        'parent': "Votre compte a été créé. Le rattachement à votre enfant sera effectif après validation par l'administration.",
    }

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


class ProfilView(generics.RetrieveUpdateAPIView):
    """GET/PUT/PATCH /api/auth/profil/ — Consultation et modification du profil."""
    serializer_class = UtilisateurSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


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

    @action(detail=False, methods=['get'])
    def demandes_rattachement(self, request):
        """GET /api/auth/parents/demandes_rattachement/ — demandes parent→élève en attente de validation."""
        demandes = RelationParentEleve.objects.filter(
            statut=RelationParentEleve.Statut.EN_ATTENTE
        ).select_related('parent', 'enfant')
        return Response(RelationParentEleveSerializer(demandes, many=True).data)

    @action(detail=True, methods=['post'])
    def delier_enfant(self, request, pk=None):
        """POST /api/parents/{id}/delier_enfant/  body: {"enfant": <id_eleve>}"""
        parent = self.get_object()
        enfant_id = request.data.get('enfant')
        supprimee, _ = RelationParentEleve.objects.filter(parent=parent, enfant_id=enfant_id).delete()
        if supprimee:
            return Response({"message": "Lien supprimé."}, status=status.HTTP_200_OK)
        return Response({"error": "Lien introuvable."}, status=status.HTTP_404_NOT_FOUND)


class MesEnfantsView(generics.ListAPIView):
    """GET /api/auth/mes-enfants/ — un parent connecté consulte la liste de ses enfants."""
    serializer_class = UtilisateurSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role != Utilisateur.Role.PARENT:
            return Utilisateur.objects.none()
        return self.request.user.enfants


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

        if (
            utilisateur.role == Utilisateur.Role.PROVISEUR
            and utilisateur.statut_validation != Utilisateur.StatutValidation.CODE_VALIDE
        ):
            return Response(
                {"error": "Ce compte responsable pédagogique doit d'abord avoir un code validé avant l'activation finale."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        utilisateur.statut_validation = Utilisateur.StatutValidation.VALIDE
        utilisateur.valide_par = request.user
        utilisateur.date_validation = timezone.now()
        utilisateur.save()

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

        return Response({"message": f"Compte de {utilisateur.nom_complet} refusé."}, status=status.HTTP_200_OK)


class CodeInvitationViewSet(viewsets.ModelViewSet):
    """CRUD des codes d'invitation/activation, réservé aux administrateurs."""
    queryset = CodeInvitation.objects.all()
    serializer_class = CodeInvitationSerializer
    permission_classes = [EstAdministrateur]

    def perform_create(self, serializer):
        code = secrets.token_hex(4).upper()
        serializer.save(code=code, cree_par=self.request.user)


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

    def get_queryset(self):
        queryset = Utilisateur.objects.all().order_by('-date_joined')
        if self.request.user.role != Utilisateur.Role.ADMINISTRATEUR:
            queryset = queryset.exclude(
                role__in=[Utilisateur.Role.ADMINISTRATEUR, Utilisateur.Role.PROVISEUR]
            )
        return queryset

    def get_permissions(self):
        if self.action in self.ACTIONS_ECRITURE_ADMIN:
            return [EstAdministrateur()]
        return super().get_permissions()

    def _verifier_cible(self, request, utilisateur):
        if utilisateur.id == request.user.id:
            return Response(
                {"error": "Vous ne pouvez pas modifier votre propre statut."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None

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

    @action(detail=True, methods=['post'])
    def reactiver(self, request, pk=None):
        utilisateur = self.get_object()
        refus = self._verifier_cible(request, utilisateur)
        if refus:
            return refus
        utilisateur.statut_validation = Utilisateur.StatutValidation.VALIDE
        utilisateur.save()
        return Response({"message": f"{utilisateur.nom_complet} réactivé."}, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        if instance.id == self.request.user.id:
            raise PermissionDenied("Vous ne pouvez pas supprimer votre propre compte.")
        instance.delete()


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

        utilisateur.statut_validation = Utilisateur.StatutValidation.CODE_ENVOYE
        utilisateur.date_code_envoye = timezone.now()
        utilisateur.date_expiration_code = timezone.now() + timedelta(hours=24)
        utilisateur.save()

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
            fail_silently=True,
        )

        return Response(
            {"message": f"Code d'invitation envoyé à {utilisateur.email}."},
            status=status.HTTP_200_OK,
        )


class RegenererCodeValidationView(APIView):
    """POST /api/auth/comptes/{id}/regenerer_code/ — identique à envoyer_code, réutilisable."""
    permission_classes = [EstAdminOuProviseur]

    def post(self, request, pk):
        return EnvoyerCodeValidationView().post(request, pk)


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
                fail_silently=True,
            )

        # Même réponse dans tous les cas : ne révèle ni l'existence d'un compte,
        # ni son état de validation.
        return Response(
            {"message": "Si un compte est éligible, un nouveau code lui a été envoyé."},
            status=status.HTTP_200_OK,
        )


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

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [EstAdminOuProviseur()]
        return [EstAdministrateur()]

    def get_serializer_context(self):
        contexte = super().get_serializer_context()
        contexte['matricules_utilises'] = set(
            Utilisateur.objects.exclude(matricule__isnull=True).values_list('matricule', flat=True)
        )
        return contexte

    def create(self, request, *args, **kwargs):
        return Response({"error": "Utilisez /matricules/importer/."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(detail=False, methods=['post'], url_path='importer', parser_classes=[MultiPartParser])
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
