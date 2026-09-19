"""The cashier's screens: the till, one bill, and the receipt it produces."""

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import Role
from apps.accounts.permissions import role_required
from apps.patients.models import OPEN_VISIT_STATUSES

from .models import Invoice, LineStatus, Payment, PaymentMethod
from .services import BillingError, take_payment

# The Finance Manager reads the bills but does not work the till.
TILL_ROLES = (Role.CASHIER, Role.ADMINISTRATOR)
VIEW_ROLES = TILL_ROLES + (Role.FINANCE_MANAGER,)

SEARCH_RESULT_LIMIT = 20


@role_required(*VIEW_ROLES)
def till(request):
    """Bills with something still to pay, oldest first.

    Searching is by the things a cashier has to hand — the patient in front of
    them, or the number on a bill they are holding.
    """
    term = request.GET.get("q", "").strip()

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

    # Settled bills are not the cashier's work, but they are still open visits,
    # so they are filtered out here rather than in the query.
    outstanding = [invoice for invoice in invoices[:SEARCH_RESULT_LIMIT] if not invoice.is_settled]

    return render(
        request,
        "billing/till.html",
        {"invoices": outstanding, "term": term},
    )


@role_required(*VIEW_ROLES)
def invoice_detail(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related("visit__patient"), pk=pk
    )
    lines = invoice.lines.select_related("service", "payment").all()
    unpaid_lines = [line for line in lines if line.status == LineStatus.UNPAID]

    return render(
        request,
        "billing/invoice_detail.html",
        {
            "invoice": invoice,
            "lines": lines,
            "unpaid_lines": unpaid_lines,
            # The running total on screen is a convenience; the amount charged is
            # computed server-side from the same lines when the form is posted.
            "line_amounts": {str(line.pk): float(line.line_total) for line in unpaid_lines},
            "payments": invoice.payments.select_related("received_by"),
            "methods": PaymentMethod.choices,
            "can_take_payment": request.user.is_superuser
            or any(request.user.has_role(role) for role in TILL_ROLES),
        },
    )


@require_POST
@role_required(*TILL_ROLES)
def pay(request, pk):
    """Settle the selected charges and issue one receipt covering them."""
    invoice = get_object_or_404(Invoice, pk=pk)

    line_ids = [int(value) for value in request.POST.getlist("lines") if value.isdigit()]
    method = request.POST.get("method", "")

    if method not in PaymentMethod.values:
        messages.error(request, "Choose how the payment was made.")
        return redirect("invoice_detail", pk=invoice.pk)

    try:
        payment = take_payment(
            invoice=invoice,
            line_ids=line_ids,
            method=method,
            received_by=request.user,
            reference=request.POST.get("reference", "").strip(),
        )
    except BillingError as exc:
        messages.error(request, str(exc))
        return redirect("invoice_detail", pk=invoice.pk)

    messages.success(
        request, f"Receipt {payment.receipt_number} — KES {payment.amount} received."
    )
    return redirect("receipt", pk=payment.pk)


@role_required(*VIEW_ROLES)
def receipt(request, pk):
    """The printable receipt for one payment."""
    payment = get_object_or_404(
        Payment.objects.select_related("invoice__visit__patient", "received_by"), pk=pk
    )

    return render(
        request,
        "billing/receipt.html",
        {"payment": payment, "lines": payment.lines.all(), "invoice": payment.invoice},
    )
