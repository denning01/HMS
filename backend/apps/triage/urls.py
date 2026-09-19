from django.urls import path

from . import views

urlpatterns = [
    path("triage/", views.triage_queue, name="triage_queue"),
    path("triage/<int:visit_id>/vitals/", views.record_vitals, name="record_vitals"),
]
