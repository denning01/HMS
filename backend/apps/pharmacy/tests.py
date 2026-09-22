"""The shelf and the ledger: they move together, or neither moves."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db.models import Sum
from django.utils import timezone

from apps.billing.models import Service
from apps.billing.services import take_payment
from apps.orders.models import OrderStatus
from apps.orders.services import place_order
from apps.patients.models import BillingMode, Patient, Visit, VisitStatus
from apps.pharmacy.models import MovementReason, StockItem, StockMovement
from apps.pharmacy.selectors import expiring_batches, low_stock
from apps.pharmacy.services import (
    PharmacyError,
    available,
    dispense,
    receive_stock,
    write_off,
)


@pytest.fixture
def shelf(db):
    call_command("seed_services")
    call_command("seed_stock_items")


@pytest.fixture
def paracetamol(shelf):
    return StockItem.objects.get(service__code="PHA-PARA")


def in_months(months):
    return timezone.localdate() + timedelta(days=30 * months)


def make_order(quantity=12, mode=BillingMode.CONSOLIDATED, code="PHA-PARA", name="Amina"):
    patient = Patient.objects.create(
        first_name=name, last_name="Hassan", date_of_birth=date(1992, 3, 14), sex="F"
    )
    visit = Visit.objects.create(
        patient=patient, status=VisitStatus.IN_CONSULTATION, billing_mode=mode
    )
    return place_order(
        visit=visit, service=Service.objects.get(code=code), quantity=quantity
    )


# --- stock in ---------------------------------------------------------------


def test_receiving_stock_writes_the_batch_and_the_ledger_together(paracetamol):
    batch = receive_stock(
        paracetamol, quantity=500, unit_cost=Decimal("3.50"),
        expires_on=in_months(12), batch_number="PB-1", supplier="Dawa Ltd",
    )

    assert batch.quantity_remaining == 500
    assert paracetamol.quantity_in_stock == 500

    movement = StockMovement.objects.get(batch=batch)
    assert movement.quantity == 500
    assert movement.reason == MovementReason.RECEIVED
    assert movement.unit_cost == Decimal("3.50")


def test_expired_stock_is_not_received(paracetamol):
    with pytest.raises(PharmacyError, match="expired"):
        receive_stock(
            paracetamol, quantity=10, unit_cost=Decimal("3.00"),
            expires_on=timezone.localdate() - timedelta(days=1),
        )


# --- dispensing -------------------------------------------------------------


def test_dispensing_takes_the_batch_that_expires_first(paracetamol):
    later = receive_stock(paracetamol, quantity=100, unit_cost=Decimal("4.00"), expires_on=in_months(12))
    sooner = receive_stock(paracetamol, quantity=10, unit_cost=Decimal("3.00"), expires_on=in_months(2))

    _, movements = dispense(make_order(quantity=12))

    sooner.refresh_from_db()
    later.refresh_from_db()
    assert sooner.quantity_remaining == 0
    assert later.quantity_remaining == 98
    # Two movements, each carrying the cost of the batch it came out of, which
    # is what makes the profit figure possible at all.
    assert [movement.quantity for movement in movements] == [-10, -2]
    assert [movement.unit_cost for movement in movements] == [Decimal("3.00"), Decimal("4.00")]


def test_dispensing_completes_the_order_and_stamps_the_prescription(paracetamol):
    receive_stock(paracetamol, quantity=100, unit_cost=Decimal("4.00"), expires_on=in_months(12))
    order = make_order(quantity=12)

    prescription, _ = dispense(order)

    order.refresh_from_db()
    assert prescription.is_dispensed
    assert order.status == OrderStatus.COMPLETED


def test_nothing_is_dispensed_twice(paracetamol):
    receive_stock(paracetamol, quantity=100, unit_cost=Decimal("4.00"), expires_on=in_months(12))
    order = make_order(quantity=12)
    dispense(order)

    with pytest.raises(PharmacyError, match="already dispensed"):
        dispense(order)


def test_nothing_is_dispensed_before_the_charge_is_paid(paracetamol):
    receive_stock(paracetamol, quantity=100, unit_cost=Decimal("4.00"), expires_on=in_months(12))
    order = make_order(quantity=12, mode=BillingMode.PAY_PER_SERVICE)

    with pytest.raises(PharmacyError, match="till"):
        dispense(order)

    take_payment(
        invoice=order.visit.invoice, line_ids=[order.invoice_line_id],
        method="cash", received_by=None,
    )
    order.refresh_from_db()
    prescription, _ = dispense(order)
    assert prescription.is_dispensed


def test_expired_stock_is_never_given_to_a_patient(paracetamol):
    batch = receive_stock(
        paracetamol, quantity=100, unit_cost=Decimal("4.00"), expires_on=in_months(1)
    )
    # It expires while it sits on the shelf.
    batch.expires_on = timezone.localdate() - timedelta(days=1)
    batch.save(update_fields=["expires_on"])

    assert available(paracetamol) == 0
    with pytest.raises(PharmacyError, match="Only 0"):
        dispense(make_order(quantity=1))


def test_short_stock_refuses_rather_than_dispensing_part(paracetamol):
    receive_stock(paracetamol, quantity=5, unit_cost=Decimal("4.00"), expires_on=in_months(12))
    order = make_order(quantity=12)

    with pytest.raises(PharmacyError, match="Only 5"):
        dispense(order)

    order.refresh_from_db()
    assert order.status == OrderStatus.ORDERED
    assert paracetamol.quantity_in_stock == 5


def test_a_drug_the_clinic_does_not_stock_says_so(shelf):
    StockItem.objects.filter(service__code="PHA-AMOX").delete()
    order = make_order(quantity=1, code="PHA-AMOX")

    with pytest.raises(PharmacyError, match="not on the shelf"):
        dispense(order)


def test_a_lab_order_is_not_the_pharmacys_to_dispense(shelf):
    order = make_order(quantity=1, code="LAB-MPS")

    with pytest.raises(PharmacyError, match="not dispensed by the pharmacy"):
        dispense(order)


# --- write-offs and alerts ---------------------------------------------------


def test_writing_off_reduces_the_shelf_and_leaves_a_reason(paracetamol):
    batch = receive_stock(paracetamol, quantity=100, unit_cost=Decimal("4.00"), expires_on=in_months(12))

    movement = write_off(
        batch, quantity=6, reason=MovementReason.WASTAGE, note="Dropped and broken"
    )

    batch.refresh_from_db()
    assert batch.quantity_remaining == 94
    assert movement.quantity == -6
    assert movement.note == "Dropped and broken"


def test_more_cannot_be_written_off_than_is_there(paracetamol):
    batch = receive_stock(paracetamol, quantity=5, unit_cost=Decimal("4.00"), expires_on=in_months(12))

    with pytest.raises(PharmacyError, match="Only 5 left"):
        write_off(batch, quantity=6, reason=MovementReason.EXPIRED)


def test_dispensing_is_not_a_write_off_reason(paracetamol):
    batch = receive_stock(paracetamol, quantity=5, unit_cost=Decimal("4.00"), expires_on=in_months(12))

    with pytest.raises(PharmacyError):
        write_off(batch, quantity=1, reason=MovementReason.DISPENSED)


def test_low_stock_is_what_has_to_be_ordered_today(paracetamol):
    receive_stock(paracetamol, quantity=100, unit_cost=Decimal("4.00"), expires_on=in_months(12))

    # Reorder level for paracetamol is 200, so 100 on the shelf is low.
    assert paracetamol in low_stock()

    receive_stock(paracetamol, quantity=400, unit_cost=Decimal("4.00"), expires_on=in_months(12))
    assert paracetamol not in low_stock()


def test_stock_about_to_expire_is_flagged_while_it_can_still_be_used(paracetamol):
    soon = receive_stock(paracetamol, quantity=10, unit_cost=Decimal("4.00"), expires_on=in_months(1))
    receive_stock(paracetamol, quantity=10, unit_cost=Decimal("4.00"), expires_on=in_months(12))

    assert list(expiring_batches()) == [soon]


def test_the_ledger_and_the_shelf_always_agree(paracetamol):
    """The balance on a batch is stored; the movements are the truth. Every
    operation writes both, so the two must reconcile after any sequence."""
    batch = receive_stock(paracetamol, quantity=100, unit_cost=Decimal("4.00"), expires_on=in_months(12))
    dispense(make_order(quantity=12, name="One"))
    write_off(batch, quantity=3, reason=MovementReason.WASTAGE)
    dispense(make_order(quantity=5, name="Two"))

    batch.refresh_from_db()
    ledger = StockMovement.objects.filter(batch=batch).aggregate(total=Sum("quantity"))["total"]
    assert batch.quantity_remaining == ledger == 80
