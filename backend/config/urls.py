from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", views.healthz, name="healthz"),
    path("", include("apps.accounts.urls")),
    path("", include("apps.patients.urls")),
    path("", include("apps.triage.urls")),
    path("", include("apps.billing.urls")),
    path("", views.home, name="home"),
]
