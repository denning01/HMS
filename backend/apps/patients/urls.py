from django.urls import path

from . import views

urlpatterns = [
    path("registration/", views.registration_home, name="registration_home"),
    path("registration/search/", views.patient_search, name="patient_search"),
    path("registration/new/", views.patient_create, name="patient_create"),
    path("patients/<int:pk>/", views.patient_detail, name="patient_detail"),
    path("patients/<int:pk>/start-visit/", views.start_visit, name="start_visit"),
]
