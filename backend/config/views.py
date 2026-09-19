"""Project-level views: the landing page and the platform health check."""

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render


def home(request):
    """Placeholder landing page — replaced by the role dashboards in Day 2."""
    return render(request, "home.html")


def healthz(request):
    """Liveness probe for the host: confirms the process is up and the DB answers."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:  # noqa: BLE001 - any DB failure means unhealthy
        return JsonResponse({"status": "error", "database": str(exc)}, status=503)
    return JsonResponse({"status": "ok", "database": "ok"})
