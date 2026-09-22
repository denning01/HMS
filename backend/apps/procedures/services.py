"""Carrying out a procedure, and the stock it uses up.

One action. The procedure is recorded, the consumables come off the shelf and
the order is closed in a single transaction: a procedure recorded without its
consumables leaves the shelf overstated, and consumables taken without the
procedure leaves them unaccounted for.
"""

from django.db import transaction
from django.utils import timezone

from apps.billing.models import Department
from apps.orders.services import complete
from apps.pharmacy.models import StockItem
from apps.pharmacy.services import PharmacyError, consume

from .models import ProcedureRecord


class ProcedureError(Exception):
    """A refused procedure operation, with a message fit to show the user."""


def record_for(order):
    """The record for an ordered procedure, created empty on first use."""
    if order.department != Department.PROCEDURE:
        raise ProcedureError(f"{order.service.name} is not done in the procedure room.")

    record, _ = ProcedureRecord.objects.get_or_create(order=order)
    return record


@transaction.atomic
def perform(order, *, notes="", consumables=(), performed_by=None):
    """Record the procedure and take what it used off the shelf.

    `consumables` is a list of (StockItem id, quantity). Anything short is a
    refusal for the whole thing rather than a procedure recorded against a shelf
    that cannot have supplied it.
    """
    if not order.is_cleared:
        raise ProcedureError(
            f"{order.service.name} has not been paid for — the patient is still at the till."
        )

    record = record_for(order)
    if record.is_performed:
        raise ProcedureError(
            f"{order.service.name} was already done at "
            f"{timezone.localtime(record.performed_at):%H:%M}."
        )

    for item_id, quantity in consumables:
        item = StockItem.objects.filter(pk=item_id).first()
        if item is None:
            raise ProcedureError("One of those consumables is not on the stock list.")

        try:
            consume(
                item,
                quantity=quantity,
                record=record,
                note=order.service.name,
                recorded_by=performed_by,
            )
        except PharmacyError as exc:
            # The whole transaction rolls back, so nothing half-consumed is left.
            raise ProcedureError(str(exc)) from exc

    record.notes = notes
    record.performed_at = timezone.now()
    record.performed_by = performed_by
    record.save(update_fields=["notes", "performed_at", "performed_by"])

    complete(order)
    return record
