"""
Django settings for jobrec project.

Environment-driven configuration so the same codebase runs in development
and on PythonAnywhere (production). All secrets and hosts are read from
environment variables or an optional .env file.

For more information, see:
- https://docs.djangoproject.com/en/6.0/topics/settings/
- https://help.pythonanywhere.com/pages/environment-variables/
"""

import os
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = Path(os.environ.get('EI_LAB_RUNTIME_ROOT', str(BASE_DIR)))
EATL_DATA_ROOT = Path(os.environ.get('EATL_DATA_ROOT', str(BASE_DIR.parent / 'data')))


# ─── Minimal .env loader (no third-party dependency) ────────────────────────
def _load_dotenv(path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ.setdefault(key, value)


_load_dotenv(BASE_DIR / '.env')


def _env_bool(name, default=False):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ('1', 'true', 'yes', 'on')


def _env_list(name, default=None):
    val = os.environ.get(name)
    if not val:
        return list(default or [])
    return [item.strip() for item in val.split(',') if item.strip()]


# ─── Security ─────────────────────────────────────────────────────────────────
# WARNING: set DJANGO_SECRET_KEY to a real random value in production!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-dev-only-not-for-production')

# Turn this off in production: DJANGO_DEBUG=0
DEBUG = _env_bool('DJANGO_DEBUG', default=True)

ALLOWED_HOSTS = _env_list('DJANGO_ALLOWED_HOSTS', default=['*'] if DEBUG else [])
CSRF_TRUSTED_ORIGINS = _env_list('DJANGO_CSRF_TRUSTED_ORIGINS', default=[])

# TLS is terminated upstream (PythonAnywhere / reverse proxy).
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_COOKIE_SECURE = _env_bool('DJANGO_SECURE_COOKIES', default=not DEBUG)
SESSION_COOKIE_SECURE = _env_bool('DJANGO_SECURE_COOKIES', default=not DEBUG)

# OCR microservice (optional; unreachable degrades to mock mode).
#   auto   — try the PaddleOCR microservice, fall back to in-process RapidOCR, then mock
#   paddle — use the PaddleOCR FastAPI microservice only
#   rapid  — use in-process RapidOCR (onnxruntime); works on PythonAnywhere free tier
#   mock   — graceful no-crash fallback returning empty results
OCR_SERVICE_URL = os.environ.get('OCR_SERVICE_URL', 'http://ocr:8000')
OCR_PROVIDER = os.environ.get('OCR_PROVIDER', 'auto')

# Unit catalog for scope equipment units (JSON: {"Scope Name": [{"name","symbol"}]}).
# When unset/unreachable, the bundled catalog in core/unit_catalog.py is used.
UNITS_CATALOG_URL = os.environ.get('UNITS_CATALOG_URL', '')


# ─── Application definition ───────────────────────────────────────────────────

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.integrated_auth.AdminPasswordRequirementMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'jobrec.urls'
AUTHENTICATION_BACKENDS = ['core.integrated_auth.IntegratedAdminBackend']

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [RUNTIME_ROOT / 'core/templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.notification_count',
                'core.context_processors.company_logo',
                'core.context_processors.record_removal_controls',
                'core.context_processors.breadcrumb_navigation',
            ],
        },
    },
]

WSGI_APPLICATION = 'jobrec.wsgi.application'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
    },
}


# ─── Database ─────────────────────────────────────────────────────────────────


def _database_config():
    """Use FlowLab PostgreSQL when configured; retain SQLite as a safe fallback."""
    if _env_bool('EI_LAB_FORCE_SQLITE', default=False):
        database_url = ''
    else:
        database_url = (
            os.environ.get('EI_LAB_DATABASE_URL')
            or os.environ.get('FLOWLAB_DATABASE_URL')
            or os.environ.get('DATABASE_URL')
            or ''
        ).strip()

    if database_url.lower().startswith(('postgresql://', 'postgres://')):
        parsed = urlparse(database_url)
        options = dict(parse_qsl(parsed.query, keep_blank_values=True))
        return {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': unquote(parsed.path.lstrip('/')),
            'USER': unquote(parsed.username or ''),
            'PASSWORD': unquote(parsed.password or ''),
            'HOST': parsed.hostname or '',
            'PORT': str(parsed.port or ''),
            'OPTIONS': options,
        }

    return {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('DJANGO_DB_PATH', str(BASE_DIR / 'db.sqlite3')),
        'OPTIONS': {'timeout': 30},
    }


DATABASES = {'default': _database_config()}


# ─── Password validation ──────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# ─── Internationalization ─────────────────────────────────────────────────────

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Africa/Lagos'

USE_I18N = True

USE_TZ = True


# ─── Static files & media ─────────────────────────────────────────────────────
# Production (PythonAnywhere): run `python manage.py collectstatic`, then map
#   URL /static/  ->  <project>/static   and   URL /media/  ->  <project>/media
# in the PA "Static files" tab. See AGENTS.md.

URL_PREFIX = os.environ.get('DJANGO_URL_PREFIX', '').strip().rstrip('/')

# E&I Lab can run by itself (empty prefix) or be mounted inside FlowLab Pro.
# Keeping the prefix environment-driven avoids changing any Django routes or
# authentication behaviour when the two WSGI applications share one port.
STATIC_URL = f'{URL_PREFIX}/static/' if URL_PREFIX else '/static/'
STATICFILES_DIRS = [RUNTIME_ROOT / 'core/static']
STATIC_ROOT = os.environ.get('DJANGO_STATIC_ROOT', str(BASE_DIR / 'static'))

MEDIA_URL = f'{URL_PREFIX}/media/' if URL_PREFIX else '/media/'
MEDIA_ROOT = os.environ.get(
    'DJANGO_MEDIA_ROOT',
    str(EATL_DATA_ROOT / 'shared_files' / 'ei-lab'),
)
EI_PRIVATE_STORAGE_ROOT = os.environ.get('EI_PRIVATE_STORAGE_ROOT', str(EATL_DATA_ROOT / 'private' / 'ei-lab'))
EI_UPLOAD_MAX_BYTES = 20 * 1024 * 1024
EI_ALLOW_SELF_APPROVAL = False


# ─── Auth ─────────────────────────────────────────────────────────────────────

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

# The applications deliberately keep independent login sessions. Restricting
# Django's cookies to its mounted path also prevents similarly named cookies
# from leaking into FlowLab Pro requests.
SESSION_COOKIE_PATH = f'{URL_PREFIX}/' if URL_PREFIX else '/'
CSRF_COOKIE_PATH = f'{URL_PREFIX}/' if URL_PREFIX else '/'
# Browsers that visited the former standalone E&I server may still hold
# root-path Django cookies. Cookie headers do not preserve cookie paths, so
# duplicate "sessionid"/"csrftoken" names can mask the mounted app's cookies.
if URL_PREFIX:
    SESSION_COOKIE_NAME = 'ei_lab_sessionid'
    CSRF_COOKIE_NAME = 'ei_lab_csrftoken'
