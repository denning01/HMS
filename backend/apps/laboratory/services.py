"""The bench: collect the specimen, record the result, release it.

Three steps, in that order, each one refusing to run before the one before it.
The specification's sequence — order, sample, result, verified, released — is
the sequence here, because a result released without a specimen collected is a
result nobody took.
"""

from django.db import transaction
from django.utils import timezone

from apps.billing.models import Department
from apps.orders.models import Order, OrderStatus
from apps.orders.services import begin, complete

from .models import LabResult, Specimen


class LabError(Exception):
    """A refused laboratory operation, with a message fit to show the user."""


def _specimen_for(order):
    """What this test is taken in, from the lab's own detail for the service."""
    lab_test = getattr(order.service, "lab_test", None)
    return lab_test.specimen if lab_test else Specimen.OTHER


def result_for(order):
    """The result record for an order, created empty on first use."""
    if order.department != Department.LABORATORY:
        raise LabError(f"{order.service.name} is not a laboratory test.")

    result, _ = LabResult.objects.get_or_create(
        order=order, defaults={"specimen": _specimen_for(order)}
    )
    return result


@transaction.atomic
def collect_specimen(order, *, specimen=None, collected_by=None):
    """Record that the sample is taken. Nothing happens in the lab before it."""
    if not order.is_cleared:
        raise LabError(
            f"{order.service.name} has not been paid for — the patient is still at the till."
        )
    if order.status == OrderStatus.CANCELLED:
        raise LabError(f"{order.service.name} was cancelled.")

    result = result_for(order)
    if result.is_collected:
        raise LabError(
            f"The specimen for {order.service.name} was already collected "
            f"at {timezone.localtime(result.collected_at):%H:%M}."
        )

    result.specimen = specimen or result.specimen
    result.collected_at = timezone.now()
    result.collected_by = collected_by
    result.save(update_fields=["specimen", "collected_at", "collected_by"])

    begin(order)
    return result


@transaction.atomic
def record_result(order, *, findings, is_abnormal=False, recorded_by=None):
    """Write the result. Can be corrected until it is released, not after."""
    result = result_for(order)

    if not result.is_collected:
        raise LabError("Collect the specimen before recording a result.")
    if result.is_released:
        raise LabError(
            "That result has been released to the doctor and can no longer be changed."
        )
    if not findings.strip():
        raise LabError("A result needs something written in it.")

    result.findings = findings
    result.is_abnormal = is_abnormal
    result.recorded_at = timezone.now()
    result.recorded_by = recorded_by
    result.save(update_fields=["findings", "is_abnormal", "recorded_at", "recorded_by"])
    return result


@transaction.atomic
def release_result(order, *, released_by=None):
    """Send the result back to the visit, and close the lab's part of the order.

    Releasing is the verification step: it is the moment someone puts their name
    to the result as fit for the doctor to treat on.
    """
    result = result_for(order)

    if not result.is_recorded:
        raise LabError("There is no result to release yet.")
    if result.is_released:
        raise LabError("That result has already been released.")

    result.released_at = timezone.now()
    result.released_by = released_by
    result.save(update_fields=["released_at", "released_by"])

    complete(order)
    return result


def worklist_queryset(queryset):
    """The lab reads its queue with the result attached, or the queue is one
    query plus one per row."""
    return queryset.select_related("lab_result", "service__lab_test")


def order_queryset():
    return Order.objects.select_related(
        "visit__patient", "service__lab_test", "invoice_line__invoice__visit", "lab_result"
    )
