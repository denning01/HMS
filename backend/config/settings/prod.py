"""Production settings.

Host-agnostic: every platform-specific value arrives as an environment variable,
so this file does not change when the deployment target is chosen.
"""

from .base import *  # noqa: F403

DEBUG = False

# Must be set explicitly in the environment — no wildcard default.
ALLOWED_HOSTS = env("ALLOWED_HOSTS")  # noqa: F405

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])  # noqa: F405

# HTTPS / cookie hardening. The platform terminates TLS and forwards this header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Errors go to stdout, where every managed platform collects them.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
