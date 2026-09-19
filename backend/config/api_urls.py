"""The API the React client calls. Everything under /api/."""

from django.urls import path

from apps.accounts import api as accounts_api
from apps.billing import api as billing_api
from apps.patients import api as patients_api
from apps.triage import api as triage_api

urlpatterns = [
    path("auth/login/", accounts_api.LoginView.as_view(), name="api_login"),
    path("auth/logout/", accounts_api.LogoutView.as_view(), name="api_logout"),
    path("auth/me/", accounts_api.MeView.as_view(), name="api_me"),

    path("patients/", patients_api.PatientListView.as_view(), name="api_patients"),
    path("patients/<int:pk>/", patients_api.PatientDetailView.as_view(), name="api_patient"),
    path("patients/<int:pk>/start-visit/", patients_api.StartVisitView.as_view(), name="api_start_visit"),

    path("triage/queue/", triage_api.TriageQueueView.as_view(), name="api_triage_queue"),
    path("triage/<int:visit_id>/vitals/", triage_api.VitalsView.as_view(), name="api_vitals"),

    path("billing/till/", billing_api.TillView.as_view(), name="api_till"),
    path("billing/invoices/<int:pk>/", billing_api.InvoiceDetailView.as_view(), name="api_invoice"),
    path("billing/invoices/<int:pk>/pay/", billing_api.TakePaymentView.as_view(), name="api_pay"),
    path("billing/receipts/<int:pk>/", billing_api.ReceiptView.as_view(), name="api_receipt"),
    path("billing/collections/", billing_api.CollectionsView.as_view(), name="api_collections"),
]
