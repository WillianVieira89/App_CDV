# backend_django/settings.py
import os
from pathlib import Path

import dj_database_url  # HEROKU: pip install dj-database-url

BASE_DIR = Path(__file__).resolve().parent.parent

# ------------------ Básico ------------------
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() == "true"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-dev-key")

# ------------------ Hosts e CSRF ------------------
# Para Heroku, defina no painel:
#   ALLOWED_HOSTS=seuapp.herokuapp.com
#   CSRF_TRUSTED_ORIGINS=https://seuapp.herokuapp.com
ALLOWED_HOSTS = [h.strip() for h in os.getenv(
    "ALLOWED_HOSTS",
    "localhost,127.0.0.1"
).split(",") if h.strip()]

CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv(
    "CSRF_TRUSTED_ORIGINS",
    ""
).split(",") if o.strip()]

# ------------------ Auth ------------------
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"          # crítico: bate com path('', views.index, name='index')
LOGOUT_REDIRECT_URL = "/login/"

# ------------------ Apps ------------------
INSTALLED_APPS = [
    "whitenoise.runserver_nostatic",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "cdv_api.apps.CdvApiConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # antes de SessionMiddleware é ok
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend_django.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],   # opcional; app templates continuam valendo
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "backend_django.wsgi.application"

# ------------------ Banco de dados ------------------
# Heroku injeta DATABASE_URL (Postgres). Em dev, cai no SQLite.
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,  # pool de conexões
            ssl_require=True,  # Postgres do Heroku usa SSL
        )
    }
else:
    SQLITE_PATH = os.environ.get("SQLITE_PATH", str(BASE_DIR / "db.sqlite3"))
    _sqlite_dir = os.path.dirname(SQLITE_PATH)
    if _sqlite_dir:
        os.makedirs(_sqlite_dir, exist_ok=True)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": SQLITE_PATH,
            "OPTIONS": {"timeout": 30},
        }
    }

# ------------------ Arquivos estáticos (WhiteNoise) ------------------
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
if (BASE_DIR / "static").exists():
    STATICFILES_DIRS = [BASE_DIR / "static"]

# ------------------ i18n ------------------
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------ Segurança/Proxy (Heroku) ------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # Heroku proxy

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ------------------ Logging p/ pegar 500 no log da dyno ------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": True},
        "cdv_api": {"handlers": ["console"], "level": "INFO"},
    },
}

