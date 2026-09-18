from django.contrib import admin
from django.urls import path

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", views.healthz, name="healthz"),
    path("", views.home, name="home"),
]
