"""The operations that move money, kept out of the views.

Departments raise charges and cashiers settle them. Both go through here so the
invariants — a bill exists before it is charged, a payment matches the lines it
settles, a line is never paid twice — hold no matter which screen called.
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import Invoice, InvoiceLine, LineStatus, Payment, Service

logger = logging.getLogger(__name__)

# The charge every attendance starts with. Held here rather than in the view so
# there is one place to change it when the clinic splits new from review rates.
CONSULTATION_CODE = "CONS-GEN"


class BillingError(Exception):
    """A refused billing operation, with a message fit to show the user."""


def invoice_for(visit):
    """The visit's bill, created on first use.

    Lazily rather than with the visit, so a visit that never incurs a charge
    never grows an empty invoice, and so any department can raise the first one.
    """
    invoice, _ = Invoice.objects.get_or_create(visit=visit)
    return invoice


def charge(visit, service, *, quantity=1, ordered_by=None):
    """Raise a charge against a visit, at the price the service carries today."""
    if quantity < 1:
        raise BillingError("A charge needs a quantity of at least one.")

    return InvoiceLine.objects.create(
        invoice=invoice_for(visit),
        service=service,
        description=service.name,
        unit_price=service.unit_price,
        quantity=quantity,
        ordered_by=ordered_by,
    )


@transaction.atomic
def take_payment(*, invoice, line_ids, method, received_by, reference=""):
    """Settle the named lines and issue one receipt covering them.

    The amount is computed from the lines rather than accepted from the form: a
    typed amount that disagrees with the charges is a reconciliation problem
    later, and there is no reason to allow it in the first place.
    """
    # Locked, because two cashiers can have the same bill open. The second one
    # through finds the lines already paid and is refused rather than taking the
    # money twice.
    lines = list(
        InvoiceLine.objects.select_for_update()
        .filter(pk__in=line_ids, invoice=invoice)
    )

    if not lines:
        raise BillingError("Select at least one charge to pay for.")

    if len(lines) != len(set(line_ids)):
        raise BillingError("Some of those charges are not on this bill.")

    already = [line for line in lines if line.status != LineStatus.UNPAID]
    if already:
        raise BillingError(
            "Already settled or cancelled: "
            + ", ".join(line.description for line in already)
            + ". Reload the bill."
        )

    amount = sum((line.line_total for line in lines), Decimal("0.00"))

    payment = Payment.objects.create(
        invoice=invoice,
        amount=amount,
        method=method,
        reference=reference,
        received_by=received_by,
    )

    InvoiceLine.objects.filter(pk__in=[line.pk for line in lines]).update(
        status=LineStatus.PAID,
        payment=payment,
        paid_at=timezone.now(),
    )

    return payment


@transaction.atomic
def cancel_line(line):
    """Void a charge raised in error. A paid charge needs a refund, not a void."""
    if line.status == LineStatus.PAID:
        raise BillingError(
            f"{line.description} has been paid — it needs a refund, not a cancellation."
        )

    line.status = LineStatus.CANCELLED
    line.save(update_fields=["status"])
    return line


def charge_consultation(visit, *, ordered_by=None):
    """Raise the consultation fee that opens every bill.

    Returns None if the catalogue has no active consultation service. Registration
    must not fail because the price list has not been seeded — the clerk would be
    left unable to admit a patient over a configuration problem, and the charge
    can still be raised by hand afterwards.
    """
    service = Service.objects.filter(code=CONSULTATION_CODE, is_active=True).first()
    if service is None:
        logger.warning(
            "No active service %s in the catalogue; visit %s opened with no "
            "consultation charge.",
            CONSULTATION_CODE,
            visit.pk,
        )
        return None

    return charge(visit, service, ordered_by=ordered_by)
