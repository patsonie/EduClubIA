from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import RelationParentEleve
from .serializers import ParentSerializer, RelationParentEleveSerializer
from .permissions import EstAdminOuProviseur
from .services import construire_dashboard_parent
from rest_framework.decorators import action
from .models import CodeInvitation
from .serializers import CompteEnAttenteSerializer, CodeInvitationSerializer
from .serializers import UtilisateurAdminSerializer
from .models import Utilisateur, JournalActivite
from django.http import FileResponse, Http404
import os
from .permissions import LoginRateThrottle
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.conf import settings
from .serializers import DemandeReinitialisationSerializer, ConfirmationReinitialisationSerializer
from .serializers import (
    InscriptionSerializer, UtilisateurSerializer,
    ConnexionSerializer, ChangementMotDePasseSerializer,
)


def get_ip_client(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


class InscriptionView(generics.CreateAPIView):
    """POST /api/auth/register/ — Création d'un nouveau compte utilisateur (sauf administrateur)."""
    queryset = Utilisateur.objects.all()
    serializer_class = InscriptionSerializer
    permission_classes = [permissions.AllowAny]

    MESSAGES_PAR_ROLE = {
        'eleve': "Votre compte a été créé. Il est en attente de validation.",
        'encadreur': "Votre demande d'inscription a été envoyée. Elle sera examinée par l'administration.",
        'proviseur': "Votre demande a été envoyée et doit être validée par un administrateur.",
        'parent': "Votre compte a été créé. Vous pouvez maintenant être associé à votre enfant.",
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
        # ... le reste de la méthode ne change pas
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


class ChangementMotDePasseView(APIView):
    """POST /api/auth/changer-mot-de-passe/ — Modifier son mot de passe."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangementMotDePasseSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        utilisateur = request.user
        utilisateur.set_password(serializer.validated_data['nouveau_mot_de_passe'])
        utilisateur.save()

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
        """POST /api/parents/{id}/lier_enfant/  body: {"enfant": <id_eleve>}"""
        parent = self.get_object()
        data = {'parent': parent.id, 'enfant': request.data.get('enfant')}
        serializer = RelationParentEleveSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(cree_par=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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
        queryset = Utilisateur.objects.filter(statut_validation=Utilisateur.StatutValidation.EN_ATTENTE)
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

        utilisateur.statut_validation = Utilisateur.StatutValidation.VALIDE
        utilisateur.valide_par = request.user
        utilisateur.date_validation = timezone.now()
        utilisateur.save()

        return Response({"message": f"Compte de {utilisateur.nom_complet} validé avec succès."}, status=status.HTTP_200_OK)


class RefuserCompteView(APIView):
    """POST /api/auth/comptes/{id}/refuser/  body: {"motif": "..."}"""
    permission_classes = [EstAdminOuProviseur]

    def post(self, request, pk):
        try:
            utilisateur = Utilisateur.objects.get(id=pk)
        except Utilisateur.DoesNotExist:
            return Response({"error": "Compte introuvable."}, status=status.HTTP_404_NOT_FOUND)

        utilisateur.statut_validation = Utilisateur.StatutValidation.REFUSE
        utilisateur.motif_refus = request.data.get('motif', '')
        utilisateur.save()

        return Response({"message": f"Compte de {utilisateur.nom_complet} refusé."}, status=status.HTTP_200_OK)


class CodeInvitationViewSet(viewsets.ModelViewSet):
    """CRUD des codes d'invitation/activation, réservé aux administrateurs."""
    queryset = CodeInvitation.objects.all()
    serializer_class = CodeInvitationSerializer
    permission_classes = [EstAdminOuProviseur]

    def perform_create(self, serializer):
        import secrets
        code = secrets.token_hex(4).upper()
        serializer.save(code=code, cree_par=self.request.user)

class UtilisateurAdminViewSet(viewsets.ModelViewSet):
    """
    CRUD complet des utilisateurs, tous rôles, réservé aux administrateurs.
    Recherche : ?search=nom  |  Filtre : ?role=eleve&statut_validation=en_attente
    """
    queryset = Utilisateur.objects.all().order_by('-date_joined')
    serializer_class = UtilisateurAdminSerializer
    permission_classes = [EstAdminOuProviseur]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['nom', 'prenom', 'email', 'matricule']
    filterset_fields = ['role', 'statut_validation', 'is_active']

    @action(detail=True, methods=['post'])
    def suspendre(self, request, pk=None):
        utilisateur = self.get_object()
        utilisateur.statut_validation = Utilisateur.StatutValidation.SUSPENDU
        utilisateur.save()
        return Response({"message": f"{utilisateur.nom_complet} suspendu."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def reactiver(self, request, pk=None):
        utilisateur = self.get_object()
        utilisateur.statut_validation = Utilisateur.StatutValidation.VALIDE
        utilisateur.save()
        return Response({"message": f"{utilisateur.nom_complet} réactivé."}, status=status.HTTP_200_OK)
    
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

        est_gestionnaire = request.user.role in ['administrateur', 'proviseur']
        est_lui_meme = request.user.id == utilisateur.id

        if not (est_gestionnaire or est_lui_meme):
            return Response(
                {"error": "Vous n'êtes pas autorisé à consulter ce document."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not utilisateur.justificatif:
            raise Http404("Aucun justificatif pour cet utilisateur.")

        chemin_fichier = utilisateur.justificatif.path
        if not os.path.exists(chemin_fichier):
            raise Http404("Fichier introuvable sur le serveur.")

        return FileResponse(open(chemin_fichier, 'rb'), as_attachment=False)
    
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

        utilisateur = Utilisateur.objects.filter(email=email).first()

        if utilisateur:
            uidb64 = urlsafe_base64_encode(force_bytes(utilisateur.pk))
            token = default_token_generator.make_token(utilisateur)
            lien_reinitialisation = f"http://127.0.0.1:8000/reinitialiser-mot-de-passe/{uidb64}/{token}/"

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

        JournalActivite.objects.create(
            utilisateur=utilisateur,
            action="Réinitialisation du mot de passe",
        )

        return Response(
            {"message": "Mot de passe réinitialisé avec succès. Vous pouvez maintenant vous connecter."},
            status=status.HTTP_200_OK,
        )