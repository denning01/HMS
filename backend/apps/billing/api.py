"""Billing over the API: the till, one bill, taking payment, and collections."""

from datetime import date

from django.db.models import Q
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasAnyRole, user_has_any_role
from apps.patients.models import OPEN_VISIT_STATUSES

from . import reports
from .models import Department, Invoice, Payment, PaymentMethod, Service
from .serializers import (
    InvoiceSerializer,
    ServiceAdminSerializer,
    InvoiceSummarySerializer,
    PaymentSerializer,
    ReceiptSerializer,
    ServiceSerializer,
    TakePaymentSerializer,
)
from .services import BillingError, take_payment
from apps.accounts.models import Role

from .roles import (
    CATALOGUE_ROLES,
    REPORT_ROLES,
    SEARCH_RESULT_LIMIT,
    TILL_ROLES,
    VIEW_ROLES,
)


class ServiceListView(generics.ListAPIView):
    """The price list, for the screens that order from it.

    Active services only: a retired one still has to read correctly on an old
    bill, but nobody should be able to order it again. Filter by department, and
    the doctor's order picker asks for one department at a time.
    """

    permission_classes = [HasAnyRole]
    roles = CATALOGUE_ROLES
    serializer_class = ServiceSerializer

    def get_queryset(self):
        queryset = Service.objects.filter(is_active=True)

        department = self.request.query_params.get("department", "").strip()
        if department in Department.values:
            queryset = queryset.filter(department=department)

        return queryset.order_by("department", "name")


class TillView(APIView):
    """Bills with something still to pay, oldest first."""

    permission_classes = [HasAnyRole]
    roles = VIEW_ROLES

    def get(self, request):
        term = request.query_params.get("q", "").strip()

        invoices = (
            Invoice.objects.filter(visit__status__in=OPEN_VISIT_STATUSES)
            .select_related("visit__patient")
            .prefetch_related("lines")
            .order_by("created_at")
        )

        if term:
            invoices = invoices.filter(
                Q(number__icontains=term)
                | Q(visit__patient__mrn__icontains=term)
                | Q(visit__patient__first_name__icontains=term)
                | Q(visit__patient__last_name__icontains=term)
            )

        # Settled bills are still open visits but are not the cashier's work.
        outstanding = [
            invoice for invoice in invoices[:SEARCH_RESULT_LIMIT] if not invoice.is_settled
        ]

        return Response(InvoiceSummarySerializer(outstanding, many=True).data)


class InvoiceDetailView(generics.RetrieveAPIView):
    permission_classes = [HasAnyRole]
    roles = VIEW_ROLES
    serializer_class = InvoiceSerializer
    queryset = Invoice.objects.select_related("visit__patient").prefetch_related(
        "lines__service", "lines__payment", "payments__received_by"
    )

    def retrieve(self, request, *args, **kwargs):
        data = self.get_serializer(self.get_object()).data
        # The client hides the payment form on this, and the server refuses the
        # post regardless — the flag only keeps a useless form off the screen.
        data["can_take_payment"] = user_has_any_role(request.user, TILL_ROLES)
        return Response(data)


class TakePaymentView(APIView):
    """Settle the selected charges and issue one receipt covering them."""

    permission_classes = [HasAnyRole]
    roles = TILL_ROLES

    def post(self, request, pk):
        invoice = generics.get_object_or_404(Invoice, pk=pk)

        form = TakePaymentSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        try:
            payment = take_payment(
                invoice=invoice,
                line_ids=form.validated_data["lines"],
                method=form.validated_data["method"],
                received_by=request.user,
                reference=form.validated_data.get("reference", ""),
            )
        except BillingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(
            ReceiptSerializer(payment).data, status=status.HTTP_201_CREATED
        )


class ReceiptView(generics.RetrieveAPIView):
    permission_classes = [HasAnyRole]
    roles = VIEW_ROLES
    serializer_class = ReceiptSerializer
    queryset = Payment.objects.select_related(
        "invoice__visit__patient", "received_by"
    ).prefetch_related("lines__service")


class CollectionsView(APIView):
    """What the clinic took on a day, and how it splits."""

    permission_classes = [HasAnyRole]
    roles = REPORT_ROLES

    def get(self, request):
        from django.utils import timezone

        day = timezone.localdate()
        invalid_day = False

        requested = request.query_params.get("day", "")
        if requested:
            try:
                day = date.fromisoformat(requested)
            except ValueError:
                invalid_day = True

        return Response(
            {
                "day": day.isoformat(),
                "is_today": day == timezone.localdate(),
                "invalid_day": invalid_day,
                "total": str(reports.total_collected(day)),
                "outstanding": str(reports.outstanding_total()),
                "by_method": [
                    {**row, "total": str(row["total"])} for row in reports.by_method(day)
                ],
                "by_department": [
                    {**row, "total": str(row["total"])} for row in reports.by_department(day)
                ],
                "by_cashier": [
                    {**row, "total": str(row["total"])} for row in reports.by_cashier(day)
                ],
                "payments": PaymentSerializer(reports.payments_on(day), many=True).data,
                "methods": [
                    {"value": value, "label": label} for value, label in PaymentMethod.choices
                ],
            }
        )


# --- the price list, as the administrator maintains it ----------------------

# Pricing changes stay with the Administrator, so they are auditable to one
# person rather than to whoever was on the desk.
PRICE_LIST_ROLES = (Role.ADMINISTRATOR,)


class ServiceAdminListView(generics.ListCreateAPIView):
    """Every service, retired ones included, and a way to add one."""

    permission_classes = [HasAnyRole]
    roles = PRICE_LIST_ROLES
    serializer_class = ServiceAdminSerializer

    def get_queryset(self):
        services = Service.objects.all()

        department = self.request.query_params.get("department", "").strip()
        if department in Department.values:
            services = services.filter(department=department)

        return services.order_by("department", "name")


class ServiceAdminDetailView(generics.RetrieveUpdateAPIView):
    """Change a price, rename a service, or retire it.

    There is no delete. A service on an issued bill cannot be removed without
    taking the bill's meaning with it, so retiring is the only way out — the
    catalogue stops offering it and every old receipt still reads correctly.
    """

    permission_classes = [HasAnyRole]
    roles = PRICE_LIST_ROLES
    serializer_class = ServiceAdminSerializer
    queryset = Service.objects.all()
