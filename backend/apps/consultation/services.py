"""The two operations the consulting room owns beyond writing the note:
starting the consultation, and closing the visit at the end of it.
"""

from django.db import transaction

from apps.orders.models import OPEN_ORDER_STATUSES
from apps.patients.models import VisitStatus

from .models import Consultation


class ConsultationError(Exception):
    """A refused consultation operation, with a message fit to show the user."""


@transaction.atomic
def open_note(visit, *, doctor=None):
    """The visit's note, created the first time the doctor writes anything.

    Creating it also moves the visit out of the waiting queue, because the two
    are the same event: this patient is now being seen.
    """
    note, created = Consultation.objects.get_or_create(
        visit=visit, defaults={"doctor": doctor}
    )

    if visit.status == VisitStatus.AWAITING_CONSULTATION:
        visit.status = VisitStatus.IN_CONSULTATION
        visit.save(update_fields=["status"])

    return note, created


@transaction.atomic
def close_visit(visit):
    """End the visit — but only once nothing is left hanging off it.

    Two things can be outstanding, and both would be lost rather than resolved by
    closing: work a department has not done yet, and money the patient still owes.
    A closed visit drops off the till and off every worklist, so closing over
    either one hides it from the only people who could have settled it.
    """
    if not visit.is_open:
        raise ConsultationError("That visit is already closed.")

    pending = [
        order.service.name
        for order in visit.orders.filter(status__in=OPEN_ORDER_STATUSES).select_related("service")
    ]
    if pending:
        raise ConsultationError(
            "Still outstanding: " + ", ".join(pending) + ". Cancel or complete it first."
        )

    invoice = getattr(visit, "invoice", None)
    if invoice is not None and invoice.balance:
        raise ConsultationError(
            f"KES {invoice.balance} is still owing on {invoice.number} — "
            "send the patient to the cashier before closing the visit."
        )

    visit.close()
    return visit
