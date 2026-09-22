"""Revenue against cost, read back from the receipts and the stock ledger."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.billing.models import Service
from apps.billing.services import take_payment
from apps.orders.services import place_order
from apps.patients.models import BillingMode, Patient, Visit, VisitStatus
from apps.pharmacy.models import MovementReason, StockItem
from apps.pharmacy.services import dispense, receive_stock, write_off
from apps.procedures.services import perform
from apps.reporting import reports


@pytest.fixture
def clinic(db):
    call_command("seed_services")
    call_command("seed_stock_items")


@pytest.fixture
def paracetamol(clinic):
    item = StockItem.objects.get(service__code="PHA-PARA")
    receive_stock(
        item, quantity=500, unit_cost=Decimal("3.00"),
        expires_on=timezone.localdate() + timedelta(days=400),
    )
    return item


@pytest.fixture
def gauze(clinic):
    item = StockItem.objects.get(name="Gauze swabs")
    receive_stock(
        item, quantity=100, unit_cost=Decimal("12.00"),
        expires_on=timezone.localdate() + timedelta(days=400),
    )
    return item


def make_visit(name="Amina", mode=BillingMode.CONSOLIDATED):
    patient = Patient.objects.create(
        first_name=name, last_name="Hassan", date_of_birth=date(1992, 3, 14), sex="F"
    )
    return Visit.objects.create(
        patient=patient, status=VisitStatus.IN_CONSULTATION, billing_mode=mode
    )


def today():
    return timezone.localdate()


def test_revenue_is_what_was_actually_taken(clinic):
    visit = make_visit()
    order = place_order(visit=visit, service=Service.objects.get(code="LAB-MPS"))
    take_payment(
        invoice=visit.invoice, line_ids=[order.invoice_line_id], method="cash", received_by=None
    )

    assert reports.revenue_total(today(), today()) == Decimal("300.00")
    # And nothing is counted before it is paid for.
    place_order(visit=visit, service=Service.objects.get(code="LAB-HB"))
    assert reports.revenue_total(today(), today()) == Decimal("300.00")


def test_cost_is_what_left_the_shelf(clinic, paracetamol):
    visit = make_visit()
    order = place_order(
        visit=visit, service=Service.objects.get(code="PHA-PARA"), quantity=12
    )
    take_payment(
        invoice=visit.invoice, line_ids=[order.invoice_line_id], method="cash", received_by=None
    )
    order.refresh_from_db()
    dispense(order)

    # 12 sold at 10.00, bought at 3.00.
    assert reports.revenue_total(today(), today()) == Decimal("120.00")
    assert reports.cost_total(today(), today()) == Decimal("36.00")

    figures = reports.summary(today(), today())
    assert figures["profit"] == Decimal("84.00")


def test_consumables_used_in_a_procedure_are_a_cost(clinic, gauze):
    visit = make_visit()
    order = place_order(visit=visit, service=Service.objects.get(code="PRO-DRESS"))
    perform(order, consumables=[(gauze.pk, 4)])

    assert reports.cost_total(today(), today()) == Decimal("48.00")
    reasons = {row["key"]: row["total"] for row in reports.cost_by_reason(today(), today())}
    assert reasons[MovementReason.CONSUMED] == Decimal("48.00")


def test_wastage_is_a_loss_not_a_cost_of_sale(clinic, paracetamol):
    write_off(paracetamol.batches.first(), quantity=10, reason=MovementReason.WASTAGE)

    assert reports.cost_total(today(), today()) == Decimal("0.00")
    assert reports.loss_total(today(), today()) == Decimal("30.00")


def test_receiving_stock_is_not_a_cost_until_it_is_sold(clinic, paracetamol):
    """Buying 500 tablets is not a bad day — it is stock. Cost lands when the
    units leave the shelf for a patient."""
    assert reports.cost_total(today(), today()) == Decimal("0.00")


def test_every_day_in_the_range_is_reported_even_the_quiet_ones(clinic):
    start = today() - timedelta(days=3)

    rows = reports.daily(start, today())

    assert len(rows) == 4
    assert [row["day"] for row in rows] == reports.days_in(start, today())
    assert all(row["revenue"] == Decimal("0.00") for row in rows[:3])


def test_revenue_splits_by_department_from_the_lines_a_receipt_settled(clinic):
    visit = make_visit()
    lab = place_order(visit=visit, service=Service.objects.get(code="LAB-MPS"))
    drug = place_order(
        visit=visit, service=Service.objects.get(code="PHA-PARA"), quantity=10
    )
    # One receipt, two departments.
    take_payment(
        invoice=visit.invoice,
        line_ids=[lab.invoice_line_id, drug.invoice_line_id],
        method="mpesa",
        received_by=None,
    )

    split = {row["key"]: row["total"] for row in reports.by_department(today(), today())}

    assert split["laboratory"] == Decimal("300.00")
    assert split["pharmacy"] == Decimal("100.00")
