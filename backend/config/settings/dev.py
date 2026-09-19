"""Local development settings."""

from .base import *  # noqa: F403

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

# Console backend so password-reset and future notification mail is readable in
# the terminal. MAILERS, not EMAIL_BACKEND: the latter is deprecated and Django
# 7.0 removes it, and defining both together is an error.
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}

# Static files are served unhashed in dev so a changed CSS file shows up on reload.
STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
}
