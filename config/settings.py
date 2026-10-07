from pathlib import Path
from decouple import config
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = [host.strip() for host in config(
    'ALLOWED_HOSTS', default='127.0.0.1,localhost'
).split(',') if host.strip()]
RENDER_EXTERNAL_HOSTNAME = config('RENDER_EXTERNAL_HOSTNAME', default='')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# URL de base utilisée dans les emails (réinitialisation de mot de passe, codes
# d'invitation...). En production, se déduit automatiquement du nom d'hôte Render ;
# peut être surchargée explicitement via la variable d'environnement FRONTEND_BASE_URL.
FRONTEND_BASE_URL = config(
    'FRONTEND_BASE_URL',
    default=f"https://{RENDER_EXTERNAL_HOSTNAME}" if RENDER_EXTERNAL_HOSTNAME else "http://127.0.0.1:8000",
)

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_filters',

    # Apps tierces
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
     'channels',

    # Apps du projet
    'utilisateurs',
    'clubs',
    'activites',
    'inscriptions',
    'participations',
    'recommandations',
    'analytics',
    'notifications',
    'messagerie',
    'annees_scolaires',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

import dj_database_url

DATABASE_URL_LOCAL = (
    f"mysql://{config('DB_USER', default='root')}:{config('DB_PASSWORD', default='')}"
    f"@{config('DB_HOST', default='localhost')}:{config('DB_PORT', default='3306')}"
    f"/{config('DB_NAME', default='gestion_clubs_db')}"
)

DATABASES = {
    'default': dj_database_url.config(
        default=DATABASE_URL_LOCAL,
        conn_max_age=600,
    )
}

# Le workaround InnoDB ne s'applique qu'en local MySQL, pas sur Postgres (Render)
if DATABASES['default']['ENGINE'] == 'django.db.backends.mysql':
    DATABASES['default'].setdefault('OPTIONS', {})
    DATABASES['default']['OPTIONS']['charset'] = 'utf8mb4'
    DATABASES['default']['OPTIONS']['init_command'] = 'SET default_storage_engine=INNODB'
AUTH_USER_MODEL = 'utilisateurs.Utilisateur'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'utilisateurs.authentication.JWTAuthenticationStatutValide',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'config.pagination.PaginationOptionnelle',
    'PAGE_SIZE': 50,
    'NUM_PROXIES': config('NUM_PROXIES', default=1 if RENDER_EXTERNAL_HOSTNAME else 0, cast=int),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '20/minute',
        'user': '120/minute',
        'login': '5/minute',
        'password_change': '5/minute',
    },
}

# L'API navigable de DRF n'est exposée qu'en développement.
if not DEBUG:
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = ('rest_framework.renderers.JSONRenderer',)

# Un lien de réinitialisation de mot de passe expire après 1 heure (3 jours par défaut).
PASSWORD_RESET_TIMEOUT = 60 * 60

# Chemin de l'admin Django configurable (évite le scan automatique de /admin/).
ADMIN_URL = config('ADMIN_URL', default='admin/')

# Les compteurs anti brute-force doivent être partagés entre processus : Redis si disponible.
if config('REDIS_URL', default=''):
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': config('REDIS_URL'),
        }
    }

# Tests : hachage rapide (les tests créent beaucoup de comptes). Jamais utilisé hors tests.
import sys
if 'test' in sys.argv:
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# L'interface est servie depuis le même domaine que l'API : CORS n'est donc pas
# nécessaire par défaut. Les origines externes doivent être déclarées explicitement.
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in config(
    'CORS_ALLOWED_ORIGINS', default=''
).split(',') if origin.strip()]
if RENDER_EXTERNAL_HOSTNAME:
    CORS_ALLOWED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")
CORS_ALLOW_CREDENTIALS = False

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Douala'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
# Sur Render, monter un disque persistant et pointer MEDIA_ROOT dessus (ou utiliser S3, ci-dessous).
MEDIA_ROOT = Path(config('MEDIA_ROOT', default=str(BASE_DIR / 'media')))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Stockage objet compatible S3 (optionnel) : activé si AWS_STORAGE_BUCKET_NAME est défini.
# Les URL sont signées et expirent (AWS_QUERYSTRING_AUTH) ; les pièces jointes du chat et les
# justificatifs sont de toute façon servis via des vues authentifiées.
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='')
if AWS_STORAGE_BUCKET_NAME:
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
    AWS_S3_ENDPOINT_URL = config('AWS_S3_ENDPOINT_URL', default=None)
    AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default=None)
    AWS_QUERYSTRING_AUTH = True
    AWS_QUERYSTRING_EXPIRE = 3600
    AWS_DEFAULT_ACL = None
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}
WHITENOISE_MANIFEST_STRICT = False

# En-têtes applicables dans tous les environnements. Les options HTTPS ne sont
# activées qu'en production afin de ne pas casser le serveur de développement.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
USE_X_FORWARDED_FOR = config('USE_X_FORWARDED_FOR', default=bool(RENDER_EXTERNAL_HOSTNAME), cast=bool)

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=31536000, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=2),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    # Un changement de mot de passe invalide immédiatement les JWT existants.
    'CHECK_REVOKE_TOKEN': True,
}


ASGI_APPLICATION = 'config.asgi.application'

# Redis obligatoire dès qu'il y a plusieurs instances/processus ; InMemory suffit pour 1 processus (dev).
REDIS_URL = config('REDIS_URL', default='')
if REDIS_URL:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [REDIS_URL]},
        },
    }
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }

# Configuration email : SMTP dès qu'un EMAIL_HOST est défini, sinon les emails
# s'affichent dans le terminal/les logs (mode développement, rien n'est envoyé).

EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.smtp.EmailBackend' if EMAIL_HOST
    else 'django.core.mail.backends.console.EmailBackend',
)
EMAIL_TIMEOUT = config('EMAIL_TIMEOUT', default=15, cast=int)
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@educlubia.cm')

IA_MODELES_DIR = Path(config('IA_MODELES_DIR', default=str(BASE_DIR / 'ia_modeles')))
IA_MODELES_DIR.mkdir(parents=True, exist_ok=True)
