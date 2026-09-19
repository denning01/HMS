"""Project-level views: the health check and the shell that serves the client."""

import logging

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

logger = logging.getLogger(__name__)


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


# Never cached: the built index.html names this deploy's hashed bundles, and a
# cached copy would go on pointing at the previous deploy's files after a release.
@never_cache
def spa(request):
    """Serve the React client for every route it owns.

    The bundle it names is content-hashed by Vite, so the assets cache hard and
    only this one small document is fetched fresh.
    """
    return render(request, "index.html")
