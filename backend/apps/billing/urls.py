from django.urls import path

from . import views

urlpatterns = [
    path("billing/", views.till, name="till"),
    path("billing/invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("billing/invoices/<int:pk>/pay/", views.pay, name="pay"),
    path("billing/receipts/<int:pk>/", views.receipt, name="receipt"),
    path("billing/collections/", views.collections, name="collections"),
]
