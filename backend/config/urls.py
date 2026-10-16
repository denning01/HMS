from django.contrib import admin
from django.urls import include, path, re_path

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", views.healthz, name="healthz"),
    path("api/", include("config.api_urls")),
    # Everything else is a client route. React Router owns the URL bar, so a
    # reload or a pasted link on /billing/invoices/3 must serve the app rather
    # than 404 — the client then reads the path and renders that screen.
    #
    # api/ is excluded deliberately: an unknown endpoint must stay a JSON 404.
    # Served the app shell instead, a fetch would get HTML where it expects
    # JSON and fail on parsing rather than on the status it was given.
    re_path(r"^(?!api/|static/).*$", views.spa, name="spa"),
]

# Django's default error pages are HTML; under /api/ they have to be JSON. See
# the note in views.py.
handler404 = "config.views.api_aware_404"
handler500 = "config.views.api_aware_500"
