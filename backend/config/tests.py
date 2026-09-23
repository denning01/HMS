"""Project-level tests: health, the shell that serves the client, and the
settings a deployment runs under."""

from pathlib import Path

import pytest
from django.urls import reverse


def test_healthz_reports_the_database(client, db):
    response = client.get(reverse("healthz"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.parametrize(
    "path",
    ["/", "/registration", "/triage/3", "/billing/invoices/7", "/anything-else"],
)
def test_client_routes_all_serve_the_app(client, path):
    """React Router owns the URL bar, so a reload or a pasted deep link has to
    serve the app rather than 404 — the client then renders that screen."""
    response = client.get(path)

    assert response.status_code == 200
    assert b'<div id="root">' in response.content


def test_the_app_shell_is_never_cached():
    """It names this deploy's hashed bundles; a cached copy would go on pointing
    at the previous deploy's files after a release."""
    from django.test import Client

    response = Client().get("/")

    assert "no-cache" in response.headers.get("Cache-Control", "")


def test_the_api_is_not_swallowed_by_the_catch_all(client, db):
    """An unknown /api/ path must still be a 404, not the app shell."""
    response = client.get("/api/does-not-exist/")

    assert response.status_code == 404
    assert b'<div id="root">' not in response.content


# --- the deployment itself --------------------------------------------------


def prod_settings():
    """The production settings as a deployment resolves them.

    django.conf.Settings layers the module over Django's own defaults, so this
    sees what the running process would see rather than only what prod.py
    happens to name.
    """
    import os

    from django.conf import Settings

    os.environ.setdefault("SECRET_KEY", "long-enough-secret-for-a-settings-import-only")
    os.environ.setdefault("ALLOWED_HOSTS", "hms.example")

    return Settings("config.settings.prod")


def test_production_settings_fail_closed():
    """The defaults that would be a breach if a deploy forgot them.

    wsgi.py points at these settings, so a deployment that sets no
    DJANGO_SETTINGS_MODULE gets this file rather than the development one.
    """
    settings = prod_settings()

    assert settings.DEBUG is False
    assert settings.SECURE_SSL_REDIRECT is True
    assert settings.SESSION_COOKIE_SECURE is True
    assert settings.CSRF_COOKIE_SECURE is True
    assert settings.SECURE_HSTS_SECONDS >= 31536000
    assert settings.X_FRAME_OPTIONS == "DENY"
    # The client reads the CSRF cookie to attach the token, so that one cookie
    # is deliberately not httpOnly; the session cookie always is.
    assert settings.SESSION_COOKIE_HTTPONLY is True


def test_a_shared_screen_signs_itself_out():
    settings = prod_settings()

    assert settings.SESSION_COOKIE_AGE <= 12 * 60 * 60
    # Sliding, so a busy till is not signed out mid-shift.
    assert settings.SESSION_SAVE_EVERY_REQUEST is True


def test_the_wsgi_entrypoint_defaults_to_production():
    """A deploy that forgets DJANGO_SETTINGS_MODULE must fail closed, not serve
    with DEBUG on."""
    source = (Path(__file__).resolve().parent / "wsgi.py").read_text().replace("'", '"')

    assert 'setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")' in source
