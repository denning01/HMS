"""
Base settings shared by every environment.

Environment-specific modules (dev.py, prod.py) import from here and override.
Anything secret or machine-specific comes from the environment, never from code.
"""

from pathlib import Path

import environ

# The Django code lives under backend/, the templates and assets under frontend/.
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
BASE_DIR = BACKEND_DIR.parent  # repo root: holds manage.py, .env, backend/, frontend/
FRONTEND_DIR = BASE_DIR / "frontend"
# Vite writes the built client here; it is what Django serves in production.
SPA_DIST = FRONTEND_DIR / "app" / "dist"

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
)

# Read .env if present. In production the platform supplies real env vars instead.
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")

DEBUG = env("DEBUG")

ALLOWED_HOSTS = env("ALLOWED_HOSTS")


# Application definition

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
]

# Project apps are added here as each module of the HMS is built.
LOCAL_APPS = [
    "apps.accounts",
    "apps.patients",
    "apps.triage",
    "apps.billing",
    "apps.orders",
    "apps.consultation",
    "apps.laboratory",
    "apps.pharmacy",
    "apps.procedures",
    "apps.appointments",
    "apps.reporting",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

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

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Only one template is rendered now — the client's index.html, which
        # names this build's hashed bundles.
        "DIRS": [SPA_DIST],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database — driven entirely by DATABASE_URL so dev and prod differ only in env.

DATABASES = {
    "default": env.db("DATABASE_URL"),
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization — the clinic is in Kenya, so times and money are local.

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Africa/Nairobi"

USE_I18N = True

USE_TZ = True


# Static files

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [FRONTEND_DIR / "static"]

# The built client is served straight from dist/ rather than through
# collectstatic. Vite already content-hashes every asset, and running them
# through the manifest storage would rename them without rewriting the
# references in index.html.
WHITENOISE_ROOT = SPA_DIST
WHITENOISE_INDEX_FILE = False

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}


# Custom user model — staff accounts carry roles as Groups (see apps.accounts).

AUTH_USER_MODEL = "accounts.User"


# API — the React client is served from the same origin (Vite proxies /api in
# development, WhiteNoise serves the built bundle in production), so session
# cookies authenticate it. No tokens are stored in the browser, and no CORS.

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}
