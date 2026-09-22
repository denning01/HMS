"""The procedure room: one action, and what it refuses."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.billing.models import Service
from apps.billing.services import take_payment
from apps.orders.models import OrderStatus
from apps.orders.services import place_order
from apps.patients.models import BillingMode, Patient, Visit, VisitStatus
from apps.pharmacy.models import MovementReason, StockItem, StockMovement
from apps.pharmacy.services import receive_stock
from apps.procedures.services import ProcedureError, perform


@pytest.fixture
def clinic(db):
    call_command("seed_services")
    call_command("seed_stock_items")


@pytest.fixture
def gauze(clinic):
    item = StockItem.objects.get(name="Gauze swabs")
    receive_stock(
        item, quantity=100, unit_cost=Decimal("12.00"),
        expires_on=timezone.localdate() + timedelta(days=400), batch_number="G-1",
    )
    return item


@pytest.fixture
def gloves(clinic):
    item = StockItem.objects.get(name="Examination gloves")
    receive_stock(
        item, quantity=50, unit_cost=Decimal("20.00"),
        expires_on=timezone.localdate() + timedelta(days=400),
    )
    return item


def make_order(code="PRO-DRESS", mode=BillingMode.CONSOLIDATED, name="Amina"):
    patient = Patient.objects.create(
        first_name=name, last_name="Hassan", date_of_birth=date(1992, 3, 14), sex="F"
    )
    visit = Visit.objects.create(
        patient=patient, status=VisitStatus.IN_CONSULTATION, billing_mode=mode
    )
    return place_order(visit=visit, service=Service.objects.get(code=code))


def test_performing_records_who_did_it_and_closes_the_order(clinic):
    order = make_order()

    record = perform(order, notes="Dressing changed, wound clean")

    order.refresh_from_db()
    assert record.is_performed
    assert record.notes == "Dressing changed, wound clean"
    assert order.status == OrderStatus.COMPLETED


def test_consumables_come_off_the_shelf_at_what_they_cost(clinic, gauze, gloves):
    order = make_order()

    record = perform(order, consumables=[(gauze.pk, 4), (gloves.pk, 2)])

    gauze.refresh_from_db()
    gloves.refresh_from_db()
    assert gauze.quantity_in_stock == 96
    assert gloves.quantity_in_stock == 48
    # 4 × 12.00 + 2 × 20.00 — the cost that makes profit per procedure possible.
    assert record.consumable_cost == Decimal("88.00")
    assert record.stock_movements.count() == 2
    assert record.stock_movements.first().reason == MovementReason.CONSUMED


def test_nothing_is_done_before_the_charge_is_paid(clinic):
    order = make_order(mode=BillingMode.PAY_PER_SERVICE)

    with pytest.raises(ProcedureError, match="till"):
        perform(order)

    take_payment(
        invoice=order.visit.invoice, line_ids=[order.invoice_line_id],
        method="cash", received_by=None,
    )
    order.refresh_from_db()
    assert perform(order).is_performed


def test_a_procedure_is_not_done_twice(clinic):
    order = make_order()
    perform(order)

    with pytest.raises(ProcedureError, match="already done"):
        perform(order)


def test_short_consumables_refuse_the_whole_thing(clinic, gauze):
    order = make_order()

    with pytest.raises(ProcedureError, match="Only 100"):
        perform(order, notes="Dressing", consumables=[(gauze.pk, 200)])

    order.refresh_from_db()
    gauze.refresh_from_db()
    # Nothing recorded, nothing taken: the transaction rolled back whole.
    assert order.status == OrderStatus.ORDERED
    assert gauze.quantity_in_stock == 100
    assert not hasattr(order, "procedure_record") or not order.procedure_record.is_performed


def test_one_short_consumable_takes_none_of_the_others(clinic, gauze, gloves):
    order = make_order()

    with pytest.raises(ProcedureError):
        perform(order, consumables=[(gauze.pk, 4), (gloves.pk, 500)])

    gauze.refresh_from_db()
    assert gauze.quantity_in_stock == 100
    assert StockMovement.objects.filter(reason=MovementReason.CONSUMED).count() == 0


def test_a_lab_order_is_not_the_procedure_rooms_to_do(clinic):
    order = make_order(code="LAB-MPS")

    with pytest.raises(ProcedureError, match="not done in the procedure room"):
        perform(order)
