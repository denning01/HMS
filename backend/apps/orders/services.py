"""Placing and cancelling orders.

An order and the charge that pays for it are created together or not at all: an
order with no charge is work the clinic gives away, and a charge with no order is
money taken for something nobody was asked to do.
"""

from django.db import transaction

from apps.billing.models import InvoiceLine
from apps.billing.services import BillingError, cancel_line, charge

from .models import Order, OrderStatus


class OrderError(Exception):
    """A refused order operation, with a message fit to show the user."""


@transaction.atomic
def place_order(*, visit, service, quantity=1, clinical_details="", ordered_by=None):
    """Order a test, a drug or a procedure, and bill for it in the same breath."""
    if not visit.is_open:
        raise OrderError("That visit is closed — nothing more can be ordered on it.")

    if not service.is_active:
        raise OrderError(f"{service.name} has been retired from the price list.")

    if quantity < 1:
        raise OrderError("An order needs a quantity of at least one.")

    line = charge(visit, service, quantity=quantity, ordered_by=ordered_by)

    return Order.objects.create(
        visit=visit,
        service=service,
        quantity=quantity,
        invoice_line=line,
        clinical_details=clinical_details,
        ordered_by=ordered_by,
    )


@transaction.atomic
def cancel_order(order):
    """Withdraw an order raised in error, and void its charge with it.

    Once a department has acted the work is done and the clinic is owed for it,
    so a completed order is a refund conversation at the till, not a cancellation
    here. The same is true of a charge already paid.
    """
    if order.status == OrderStatus.COMPLETED:
        raise OrderError(
            f"{order.service.name} has already been carried out — it cannot be cancelled."
        )
    if order.status == OrderStatus.CANCELLED:
        raise OrderError(f"{order.service.name} was already cancelled.")

    # Read the charge back under a lock rather than trusting the copy loaded
    # with the order: the cashier may have taken the money since, and a stale
    # line would let this void a charge the patient has already paid.
    line = InvoiceLine.objects.select_for_update().get(pk=order.invoice_line_id)

    try:
        cancel_line(line)
    except BillingError as exc:
        # Paid: voiding the order here would leave money on the bill for nothing.
        raise OrderError(str(exc)) from exc

    order.invoice_line = line
    order.status = OrderStatus.CANCELLED
    order.save(update_fields=["status"])
    return order


def begin(order):
    """Mark an order as being worked on, without repeating the guard everywhere."""
    if order.status != OrderStatus.ORDERED:
        return order
    order.status = OrderStatus.IN_PROGRESS
    order.save(update_fields=["status"])
    return order


def complete(order):
    order.status = OrderStatus.COMPLETED
    order.save(update_fields=["status"])
    return order
