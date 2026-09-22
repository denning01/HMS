"""Stock in, stock out, and dispensing against a prescription.

Every movement of stock goes through here, and every one of them writes a
StockMovement in the same transaction that changes the batch balance. That is
the whole discipline of this module: the shelf and the ledger move together or
neither moves.
"""

from django.db import transaction
from django.utils import timezone

from apps.billing.models import Department
from apps.orders.services import complete

from .models import MovementReason, Prescription, StockBatch, StockItem, StockMovement

WRITE_OFF_REASONS = (
    MovementReason.WASTAGE,
    MovementReason.EXPIRED,
    MovementReason.CORRECTION,
)


class PharmacyError(Exception):
    """A refused pharmacy operation, with a message fit to show the user."""


def item_for(order):
    """The shelf item an order dispenses, or a refusal the pharmacist can read."""
    if order.department != Department.PHARMACY:
        raise PharmacyError(f"{order.service.name} is not dispensed by the pharmacy.")

    item = getattr(order.service, "stock_item", None)
    if item is None:
        raise PharmacyError(
            f"{order.service.name} is on the price list but not on the shelf — "
            "add it to the stock list before dispensing it."
        )
    return item


def prescription_for(order):
    """The directions for an order, created empty if the doctor wrote none.

    Deliberately does not ask whether the drug is on the shelf. A doctor may
    prescribe something the pharmacy has run out of or does not stock; that is
    the pharmacist's conversation at the counter, not a reason to refuse the
    prescription and leave the patient with nothing written down.
    """
    if order.department != Department.PHARMACY:
        raise PharmacyError(f"{order.service.name} is not dispensed by the pharmacy.")

    prescription, _ = Prescription.objects.get_or_create(order=order)
    return prescription


@transaction.atomic
def attach_prescription(order, *, dosage="", frequency="", duration="", instructions=""):
    """Record how the drug is to be taken, as the doctor orders it."""
    prescription = prescription_for(order)
    prescription.dosage = dosage
    prescription.frequency = frequency
    prescription.duration = duration
    prescription.instructions = instructions
    prescription.save(update_fields=["dosage", "frequency", "duration", "instructions"])
    return prescription


# --- stock in ---------------------------------------------------------------


@transaction.atomic
def receive_stock(
    item,
    *,
    quantity,
    unit_cost,
    expires_on,
    batch_number="",
    supplier="",
    received_by=None,
):
    """Take a delivery onto the shelf as its own batch."""
    if quantity < 1:
        raise PharmacyError("A delivery has to be at least one unit.")
    if unit_cost < 0:
        raise PharmacyError("A unit cost cannot be negative.")
    if expires_on < timezone.localdate():
        raise PharmacyError(
            f"That batch expired on {expires_on:%d %b %Y} — it cannot be received."
        )

    batch = StockBatch.objects.create(
        item=item,
        batch_number=batch_number,
        quantity_received=quantity,
        quantity_remaining=quantity,
        unit_cost=unit_cost,
        expires_on=expires_on,
        supplier=supplier,
        received_by=received_by,
    )

    StockMovement.objects.create(
        item=item,
        batch=batch,
        quantity=quantity,
        reason=MovementReason.RECEIVED,
        unit_cost=unit_cost,
        note=supplier,
        recorded_by=received_by,
    )
    return batch


@transaction.atomic
def write_off(batch, *, quantity, reason, note="", recorded_by=None):
    """Take stock off the shelf for something other than a patient."""
    if reason not in WRITE_OFF_REASONS:
        raise PharmacyError("Stock leaves the shelf for a patient or as a write-off, not both.")
    if quantity < 1:
        raise PharmacyError("A write-off has to be at least one unit.")

    locked = StockBatch.objects.select_for_update().get(pk=batch.pk)
    if quantity > locked.quantity_remaining:
        raise PharmacyError(
            f"Only {locked.quantity_remaining} left in that batch."
        )

    locked.quantity_remaining -= quantity
    locked.save(update_fields=["quantity_remaining"])

    return StockMovement.objects.create(
        item=locked.item,
        batch=locked,
        quantity=-quantity,
        reason=reason,
        note=note,
        unit_cost=locked.unit_cost,
        recorded_by=recorded_by,
    )


# --- stock out --------------------------------------------------------------


def dispensable_batches(item):
    """What may actually be given to a patient: in date, and not empty.

    Earliest expiry first, which is the order stock should leave in.
    """
    return item.batches.filter(
        quantity_remaining__gt=0, expires_on__gte=timezone.localdate()
    ).order_by("expires_on", "received_at")


def available(item):
    return sum(batch.quantity_remaining for batch in dispensable_batches(item))


@transaction.atomic
def dispense(order, *, dispensed_by=None):
    """Give out what was prescribed, oldest stock first, and write it all down.

    The quantity is the one on the order, which is the quantity the patient was
    billed for. A pharmacist who needs to give out something different is
    changing what was charged, and that goes back through the doctor and the
    till rather than quietly out of the ledger here.
    """
    item = item_for(order)

    if not order.is_cleared:
        raise PharmacyError(
            f"{order.service.name} has not been paid for — the patient is still at the till."
        )

    prescription = prescription_for(order)
    if prescription.is_dispensed:
        raise PharmacyError(
            f"{order.service.name} was already dispensed at "
            f"{timezone.localtime(prescription.dispensed_at):%H:%M}."
        )

    # Locked in expiry order, so two pharmacists dispensing the last box cannot
    # both be told it is there.
    batches = list(
        dispensable_batches(item).select_for_update()
    )

    needed = order.quantity
    on_hand = sum(batch.quantity_remaining for batch in batches)
    if on_hand < needed:
        raise PharmacyError(
            f"Only {on_hand} {item.unit}{'' if on_hand == 1 else 's'} of {item.name} "
            f"in date on the shelf, and {needed} were prescribed."
        )

    movements = []
    for batch in batches:
        if needed == 0:
            break
        taken = min(needed, batch.quantity_remaining)

        batch.quantity_remaining -= taken
        batch.save(update_fields=["quantity_remaining"])

        movements.append(
            StockMovement.objects.create(
                item=item,
                batch=batch,
                quantity=-taken,
                reason=MovementReason.DISPENSED,
                unit_cost=batch.unit_cost,
                prescription=prescription,
                recorded_by=dispensed_by,
            )
        )
        needed -= taken

    prescription.dispensed_at = timezone.now()
    prescription.dispensed_by = dispensed_by
    prescription.save(update_fields=["dispensed_at", "dispensed_by"])

    complete(order)
    return prescription, movements


@transaction.atomic
def consume(item, *, quantity, record=None, note="", recorded_by=None):
    """Take consumables off the shelf for a procedure.

    Same ledger as dispensing, and the same expiry-first order. `record` is the
    procedure they were used in, which is what lets their cost be attributed to
    it later without counting them in a second place.
    """
    batches = list(dispensable_batches(item).select_for_update())
    on_hand = sum(batch.quantity_remaining for batch in batches)
    if quantity < 1:
        raise PharmacyError("Recording a consumable takes at least one unit.")
    if on_hand < quantity:
        raise PharmacyError(
            f"Only {on_hand} {item.unit}s of {item.name} in date on the shelf, "
            f"and {quantity} were used."
        )

    movements = []
    needed = quantity
    for batch in batches:
        if needed == 0:
            break
        taken = min(needed, batch.quantity_remaining)
        batch.quantity_remaining -= taken
        batch.save(update_fields=["quantity_remaining"])
        movements.append(
            StockMovement.objects.create(
                item=item,
                batch=batch,
                quantity=-taken,
                reason=MovementReason.CONSUMED,
                unit_cost=batch.unit_cost,
                procedure_record=record,
                note=note,
                recorded_by=recorded_by,
            )
        )
        needed -= taken

    return movements
