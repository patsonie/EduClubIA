from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken


# Authentification JWT utilisée par toute l'API (déclarée dans settings.py, REST_FRAMEWORK).
class JWTAuthenticationStatutValide(JWTAuthentication):
    """
    Refuse les jetons d'un compte dont le statut n'est plus « valide »
    (suspendu, refusé, en attente...), même si le jeton lui-même est encore valable.
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if user.statut_validation != 'valide':
            raise AuthenticationFailed("Ce compte n'est pas actif.", code='compte_inactif')
        return user


# Coupe toutes les sessions d'un utilisateur (suspension, refus, changement de mot de passe).
def revoquer_jetons(utilisateur):
    """Blackliste tous les refresh tokens en circulation d'un utilisateur."""
    for jeton in OutstandingToken.objects.filter(user=utilisateur):
        BlacklistedToken.objects.get_or_create(token=jeton)
