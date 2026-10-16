"""Project-level views: the health check and the shell that serves the client."""

import logging

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.defaults import page_not_found, server_error

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


# Error pages. Under /api/ they have to be JSON.
#
# urls.py keeps /api/ out of the client catch-all so an unknown endpoint 404s
# instead of being answered with the app shell. That gets the status right but
# not the body: Django's own error pages are HTML, and the client parses every
# response as JSON, so an HTML body raises a parse error in the fetch wrapper
# rather than surfacing the status the server actually gave. The key is `detail`
# to match what DRF sends, so ApiError reads it the same way either way.


def api_aware_404(request, exception=None):
    """JSON for the API, Django's page for every client route."""
    if request.path.startswith("/api/"):
        return JsonResponse({"detail": "Not found."}, status=404)
    return page_not_found(request, exception)


def api_aware_500(request):
    """Same again for an unhandled error, which a screen must still be able to read."""
    if request.path.startswith("/api/"):
        return JsonResponse({"detail": "Server error."}, status=500)
    return server_error(request)
