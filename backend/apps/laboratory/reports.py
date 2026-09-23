"""How long the laboratory takes.

Every stamp this needs is already on the result: ordered, collected, recorded,
released. Nothing new is measured — the question is only ever asked of what the
bench already wrote down, which is why a slow week cannot be argued with.

The total is what the patient experiences: ordered to released. The three legs
underneath it are what the lab can act on, because they fail for different
reasons — a long wait for a specimen is a queue at the door, a long bench time
is the work itself, and a long wait to release is a result written and nobody
signing it off.
"""

from statistics import median

from django.utils import timezone

from apps.billing.models import Department, cleared_lines_q
from apps.orders.models import OPEN_ORDER_STATUSES, Order
from apps.patients.models import OPEN_VISIT_STATUSES

from .models import LabResult

SLOWEST_LISTED = 5


def released_between(start, end):
    return (
        LabResult.objects.filter(
            released_at__date__gte=start, released_at__date__lte=end
        )
        .select_related("order__service", "order__visit__patient", "released_by")
        .order_by("released_at")
    )


def _minutes(earlier, later):
    if earlier is None or later is None:
        return None
    return int((later - earlier).total_seconds() // 60)


def legs(result):
    """The three stretches that add up to the total, in minutes."""
    return {
        "to_specimen": _minutes(result.order.ordered_at, result.collected_at),
        "on_the_bench": _minutes(result.collected_at, result.recorded_at),
        "to_release": _minutes(result.recorded_at, result.released_at),
        "total": _minutes(result.order.ordered_at, result.released_at),
    }


def _median(values):
    present = [value for value in values if value is not None]
    return int(median(present)) if present else None


def by_test(results):
    """Per test, because one slow assay does not make a slow laboratory."""
    grouped = {}
    for result in results:
        service = result.order.service
        row = grouped.setdefault(
            service.code, {"code": service.code, "name": service.name, "minutes": []}
        )
        row["minutes"].append(legs(result)["total"])

    rows = [
        {
            "code": row["code"],
            "name": row["name"],
            "count": len(row["minutes"]),
            "median_minutes": _median(row["minutes"]),
            "slowest_minutes": max((m for m in row["minutes"] if m is not None), default=None),
        }
        for row in grouped.values()
    ]
    return sorted(rows, key=lambda row: row["median_minutes"] or 0, reverse=True)


def still_waiting():
    """What is open right now, and how long it has been.

    Orders held at the till are listed too, marked as held. The patient is
    waiting either way, and a laboratory judged only on the work it was allowed
    to start is one measuring the wrong thing.
    """
    orders = (
        Order.objects.filter(
            service__department=Department.LABORATORY,
            status__in=OPEN_ORDER_STATUSES,
            visit__status__in=OPEN_VISIT_STATUSES,
        )
        .select_related("visit__patient", "service", "invoice_line__invoice__visit", "lab_result")
        .order_by("ordered_at")
    )

    cleared = set(
        orders.filter(cleared_lines_q("invoice_line")).values_list("pk", flat=True)
    )
    now = timezone.now()

    return [
        {
            "order_id": order.pk,
            "patient_name": order.visit.patient.full_name,
            "mrn": order.visit.patient.mrn,
            "test": order.service.name,
            "stage": getattr(order, "lab_result", None).stage
            if getattr(order, "lab_result", None)
            else "awaiting specimen",
            "is_cleared": order.pk in cleared,
            "waiting_minutes": int((now - order.ordered_at).total_seconds() // 60),
        }
        for order in orders
    ]


def summary(start, end):
    results = list(released_between(start, end))
    measured = [legs(result) for result in results]

    slowest = sorted(
        (
            {
                "test": result.order.service.name,
                "mrn": result.order.visit.patient.mrn,
                "released_at": result.released_at,
                "minutes": legs(result)["total"],
            }
            for result in results
            if legs(result)["total"] is not None
        ),
        key=lambda row: row["minutes"],
        reverse=True,
    )[:SLOWEST_LISTED]

    return {
        "released": len(results),
        "median_minutes": _median([row["total"] for row in measured]),
        "longest_minutes": max(
            (row["total"] for row in measured if row["total"] is not None), default=None
        ),
        "legs": {
            "to_specimen": _median([row["to_specimen"] for row in measured]),
            "on_the_bench": _median([row["on_the_bench"] for row in measured]),
            "to_release": _median([row["to_release"] for row in measured]),
        },
        "by_test": by_test(results),
        "slowest": slowest,
        "still_waiting": still_waiting(),
    }
