"""Local development settings."""

from .base import *  # noqa: F403

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

# Console backend so password-reset and future notification mail is readable in the terminal.
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}

# Static files are served unhashed in dev so a changed CSS file shows up on reload.
STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
}
