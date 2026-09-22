"""Revenue and profit over a period.

No models of its own. Revenue is read from the payments and the lines they
settled; cost is read from the stock that actually left the shelf. Both already
exist as records that someone signed for, so a report here cannot say anything
the receipts and the ledger do not.

One caveat is worth stating rather than hiding: revenue is recognised when the
money is taken and cost when the stock moves, and for a walk-in clinic those are
minutes apart. A drug paid for at 17:55 and dispensed at 18:05 lands its revenue
on one day and its cost on the next. Over a week it comes out; on the boundary of
a single day it can be a few hundred shillings out, and that is the honest limit
of a daily profit figure drawn from two different events.
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncDate

from apps.billing.models import Department, InvoiceLine, LineStatus, Payment, PaymentMethod
from apps.billing.reports import LINE_TOTAL
from apps.pharmacy.models import MovementReason, StockMovement

ZERO = Decimal("0.00")

# quantity is negative on the way out, so the cost of what left is the negated
# sum. Computed in the database: a month of movements is one query.
MOVEMENT_COST = ExpressionWrapper(
    F("quantity") * F("unit_cost"),
    output_field=DecimalField(max_digits=14, decimal_places=2),
)

# What counts as cost of sale: stock that went to a patient. Wastage, expiry and
# corrections are losses, reported separately, and folding them into cost of
# sale would make a bad month look like an expensive one.
COST_OF_SALE_REASONS = [MovementReason.DISPENSED, MovementReason.CONSUMED]
LOSS_REASONS = [MovementReason.WASTAGE, MovementReason.EXPIRED, MovementReason.CORRECTION]


def days_in(start, end):
    """Every date in the range, including days nothing happened.

    A report that omits the days with no takings is one nobody can read a trend
    from — and a closed Sunday is a fact, not a gap.
    """
    count = (end - start).days
    return [start + timedelta(days=offset) for offset in range(count + 1)]


def payments_between(start, end):
    return Payment.objects.filter(received_at__date__gte=start, received_at__date__lte=end)


def revenue_total(start, end):
    return payments_between(start, end).aggregate(total=Sum("amount"))["total"] or ZERO


def paid_lines_between(start, end, *, department=None):
    lines = InvoiceLine.objects.filter(
        status=LineStatus.PAID,
        payment__received_at__date__gte=start,
        payment__received_at__date__lte=end,
    )
    if department:
        lines = lines.filter(service__department=department)
    return lines


def movements_between(start, end, *, reasons):
    return StockMovement.objects.filter(
        reason__in=reasons,
        recorded_at__date__gte=start,
        recorded_at__date__lte=end,
    )


def cost_total(start, end):
    total = movements_between(start, end, reasons=COST_OF_SALE_REASONS).aggregate(
        total=Sum(MOVEMENT_COST)
    )["total"]
    return -(total or ZERO)


def loss_total(start, end):
    total = movements_between(start, end, reasons=LOSS_REASONS).aggregate(
        total=Sum(MOVEMENT_COST)
    )["total"]
    return -(total or ZERO)


def by_department(start, end):
    """Revenue per department, from the lines each payment settled."""
    totals = {
        row["service__department"]: row["total"]
        for row in paid_lines_between(start, end)
        .values("service__department")
        .annotate(total=Sum(LINE_TOTAL))
    }
    return [
        {"key": value, "label": label, "total": totals.get(value, ZERO)}
        for value, label in Department.choices
        if totals.get(value)
    ]


def by_method(start, end):
    totals = {
        row["method"]: row["total"]
        for row in payments_between(start, end).values("method").annotate(total=Sum("amount"))
    }
    return [
        {"key": value, "label": label, "total": totals.get(value, ZERO)}
        for value, label in PaymentMethod.choices
    ]


def by_cashier(start, end):
    rows = (
        payments_between(start, end)
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


def cost_by_reason(start, end):
    """Where the cost went: drugs dispensed, consumables used, and what was lost."""
    totals = {
        row["reason"]: -row["total"]
        for row in movements_between(
            start, end, reasons=COST_OF_SALE_REASONS + LOSS_REASONS
        )
        .values("reason")
        .annotate(total=Sum(MOVEMENT_COST))
    }
    return [
        {"key": value, "label": label, "total": totals.get(value, ZERO), "is_loss": value in LOSS_REASONS}
        for value, label in MovementReason.choices
        if totals.get(value)
    ]


def daily(start, end):
    """Revenue, cost and profit for every day in the range."""
    revenue = {
        row["day"]: row["total"]
        for row in payments_between(start, end)
        .annotate(day=TruncDate("received_at"))
        .values("day")
        .annotate(total=Sum("amount"))
    }
    costs = {
        row["day"]: -row["total"]
        for row in movements_between(start, end, reasons=COST_OF_SALE_REASONS)
        .annotate(day=TruncDate("recorded_at"))
        .values("day")
        .annotate(total=Sum(MOVEMENT_COST))
    }

    rows = []
    for day in days_in(start, end):
        earned = revenue.get(day, ZERO)
        spent = costs.get(day, ZERO)
        rows.append(
            {"day": day, "revenue": earned, "cost": spent, "profit": earned - spent}
        )
    return rows


def summary(start, end):
    """Everything the finance screen shows, in one place."""
    revenue = revenue_total(start, end)
    cost = cost_total(start, end)

    return {
        "revenue": revenue,
        "cost": cost,
        "profit": revenue - cost,
        "losses": loss_total(start, end),
        "receipts": payments_between(start, end).count(),
        "daily": daily(start, end),
        "by_department": by_department(start, end),
        "by_method": by_method(start, end),
        "by_cashier": by_cashier(start, end),
        "cost_by_reason": cost_by_reason(start, end),
    }
