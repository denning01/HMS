"""Collections reporting.

The cashier's screens answer "what does this patient owe". These answer "what did
the clinic take today, through which till and for which department" — which is
what gets reconciled against the cash drawer and the M-Pesa statement at closing.

Everything is read back from the payments and the lines they settled, so a report
can never disagree with the receipts it is summarising.
"""

from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum

from .models import Department, InvoiceLine, LineStatus, Payment, PaymentMethod

# unit_price * quantity, computed in the database so a day's takings are one query.
LINE_TOTAL = ExpressionWrapper(
    F("unit_price") * F("quantity"),
    output_field=DecimalField(max_digits=12, decimal_places=2),
)

ZERO = Decimal("0.00")


def payments_on(day):
    """Every receipt issued on a given local date, newest first."""
    return (
        Payment.objects.filter(received_at__date=day)
        .select_related("received_by", "invoice__visit__patient")
        .order_by("-received_at")
    )


def total_collected(day):
    return payments_on(day).aggregate(total=Sum("amount"))["total"] or ZERO


def by_method(day):
    """Takings per payment method — the split to reconcile against, till by till."""
    totals = {
        row["method"]: row["total"]
        for row in payments_on(day).values("method").annotate(total=Sum("amount"))
    }
    return [
        {"key": value, "label": label, "total": totals.get(value, ZERO)}
        for value, label in PaymentMethod.choices
    ]


def by_cashier(day):
    rows = (
        payments_on(day)
        .values("received_by__username", "received_by__first_name", "received_by__last_name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    return [
        {
            "name": f"{row['received_by__first_name']} {row['received_by__last_name']}".strip()
            or row["received_by__username"]
            or "—",
            "total": row["total"],
        }
        for row in rows
    ]


def by_department(day):
    """Takings per department, from the lines each payment settled.

    Read from the lines rather than the payment, because one receipt routinely
    covers charges from several departments and the split is what each department
    is credited with.
    """
    totals = {
        row["service__department"]: row["total"]
        for row in (
            InvoiceLine.objects.filter(
                status=LineStatus.PAID, payment__received_at__date=day
            )
            .values("service__department")
            .annotate(total=Sum(LINE_TOTAL))
        )
    }
    return [
        {"key": value, "label": label, "total": totals.get(value, ZERO)}
        for value, label in Department.choices
        if totals.get(value)
    ]


def outstanding_total():
    """Everything charged and not yet settled, across all open bills."""
    total = InvoiceLine.objects.filter(status=LineStatus.UNPAID).aggregate(
        total=Sum(LINE_TOTAL)
    )["total"]
    return total or ZERO
