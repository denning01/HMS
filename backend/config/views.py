"""Project-level views: the landing page and the platform health check."""

import logging

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

logger = logging.getLogger(__name__)


def home(request):
    """Placeholder landing page — replaced by the role dashboards in Day 2."""
    return render(request, "home.html")


def healthz(request):
    """Liveness probe for the host: confirms the process is up and the DB answers."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # noqa: BLE001 - any DB failure means unhealthy
        # Logged, not returned: driver errors carry the host, user and database
        # name, and this endpoint answers unauthenticated callers.
        logger.exception("Health check failed: database unreachable")
        return JsonResponse({"status": "error", "database": "unreachable"}, status=503)
    return JsonResponse({"status": "ok", "database": "ok"})
