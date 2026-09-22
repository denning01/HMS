"""Reads of the order book that the departmental worklists share."""

from apps.billing.models import cleared_lines_q
from apps.patients.models import OPEN_VISIT_STATUSES

from .models import OPEN_ORDER_STATUSES, Order

WORKLIST_RELATIONS = (
    "visit__patient",
    "service",
    "invoice_line__invoice__visit",
)


def orders_for(visit):
    """Everything ordered on a visit, including what was cancelled — the doctor
    needs to see that a test was withdrawn, not find it silently missing."""
    return (
        Order.objects.filter(visit=visit)
        .select_related(*WORKLIST_RELATIONS)
        .order_by("ordered_at")
    )


def worklist(department, *, cleared=True):
    """The department's queue: open orders on open visits, oldest first.

    `cleared` filters to the orders billing has released. A department that wants
    to see what is still waiting on payment asks for the rest.
    """
    queryset = (
        Order.objects.filter(
            service__department=department,
            status__in=OPEN_ORDER_STATUSES,
            visit__status__in=OPEN_VISIT_STATUSES,
        )
        .select_related(*WORKLIST_RELATIONS)
        .order_by("-visit__is_urgent", "ordered_at")
    )

    condition = cleared_lines_q("invoice_line")
    return queryset.filter(condition) if cleared else queryset.exclude(condition)
