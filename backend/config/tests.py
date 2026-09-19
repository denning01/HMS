"""Tests for the project-level routes: health, and the shell that serves the client."""

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
