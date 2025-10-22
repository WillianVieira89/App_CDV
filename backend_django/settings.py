# backend_django/settings.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ------------------ Básico ------------------
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() == "true"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-dev-key")

# Hosts e CSRF (Render define RENDER_EXTERNAL_HOSTNAME; em outras plataformas use variáveis abaixo)
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
ALLOWED_HOSTS = []

if RENDER_EXTERNAL_HOSTNAME:
    # Ex.: app-cdv.onrender.com
    ALLOWED_HOSTS += [RENDER_EXTERNAL_HOSTNAME]
else:
    # Permite configurar manualmente (separar por vírgula) ou cair no dev.
    ALLOWED_HOSTS += os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# CSRF deve conter o domínio **com esquema** (https://…)
CSRF_TRUSTED_ORIGINS = []
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")
# Opcional: permitir configurar explicitamente (útil fora do Render / múltiplos domínios)
extra_csrf = os.getenv("DJANGO_ALLOWED_ORIGIN")
if extra_csrf:
    # aceitar lista separada por vírgula
    CSRF_TRUSTED_ORIGINS += [s.strip() for s in extra_csrf.split(",") if s.strip()]

# ------------------ Auth ------------------
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"          # <- crítico para evitar 500 após login
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
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
        # Mantém /templates como pasta global (além dos templates dentro dos apps)
        "DIRS": [BASE_DIR / "templates"],
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

# ------------------ Arquivos estáticos ------------------
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
if (BASE_DIR / "static").exists():
    STATICFILES_DIRS = [BASE_DIR / "static"]

# ------------------ Banco de dados ------------------
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

# ------------------ i18n ------------------
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------ Segurança produção ------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # importante atrás de proxy

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ------------------ Logging útil pra 500 ------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "loggers": {
        "django.request": {  # erros 500 entram aqui
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": True,
        },
        "cdv_api": {  # teu app
            "handlers": ["console"],
            "level": "INFO",
        },
    },
}
