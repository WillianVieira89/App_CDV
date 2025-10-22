# backend_django/settings.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ------------------ Básico ------------------
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() == "true"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-dev-key")  # troque em produção!

# ------------------ Hosts / CSRF ------------------
# Aceita lista separada por vírgula. Ex.: "meuapp.pythonanywhere.com,localhost,127.0.0.1"
ALLOWED_HOSTS = [    "WillianVieira89.pythonanywhere.com",  # seu domínio PA
    "localhost", "127.0.0.1"]

# CSRF_TRUSTED_ORIGINS exige esquema (https://...)
# Ex.: "https://meuapp.pythonanywhere.com,https://meuapp.alwaysdata.net"
CSRF_TRUSTED_ORIGINS = ["https://WillianVieira89.pythonanywhere.com"]

# ------------------ Auth ------------------
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"      # <- crítico: existe e evita 500 pós-login
LOGOUT_REDIRECT_URL = "/login/"

# ------------------ Apps ------------------
INSTALLED_APPS = [
    "whitenoise.runserver_nostatic",  # mantém o runserver leve
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
    "whitenoise.middleware.WhiteNoiseMiddleware",  # logo após SecurityMiddleware
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
        # Mantém /templates como pasta global (além dos templates de cada app)
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
# Funciona com WhiteNoise e também com mapeamento de "Static files" (PA/AlwaysData)
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"        # coletados por collectstatic
# pasta "static" opcional para assets do projeto
if (BASE_DIR / "static").exists():
    STATICFILES_DIRS = [BASE_DIR / "static"]

# ------------------ Banco de dados ------------------
# 1) Se DATABASE_URL existir, usa (Neon/Render/PA etc.)
# 2) Caso contrário, cai no SQLite local
# sqlite ok no plano free
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / "db.sqlite3"),
        "OPTIONS": {"timeout": 30},
    }
}

_db_url = os.getenv("DATABASE_URL")
if _db_url:
    try:
        import dj_database_url  # certifique-se de ter no requirements.txt
        DATABASES["default"] = dj_database_url.parse(_db_url, conn_max_age=600, ssl_require=True)
    except Exception:
        # Se faltar lib, não quebra; continua no SQLite
        pass

# ------------------ i18n ------------------
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------ Segurança produção ------------------
# Atrás de proxy (PythonAnywhere / AlwaysData) isso evita problemas de scheme
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

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
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": True},
        "cdv_api": {"handlers": ["console"], "level": "INFO"},
    },
}

