"""Orders: the charge they raise, the gate they wait on, and undoing them."""

from datetime import date
from decimal import Decimal

import pytest
from django.core.management import call_command

from apps.billing.models import Department, LineStatus, Service
from apps.billing.services import take_payment
from apps.orders.models import Order, OrderStatus
from apps.orders.selectors import worklist
from apps.orders.services import OrderError, cancel_order, place_order
from apps.patients.models import BillingMode, Patient, Visit, VisitStatus


@pytest.fixture
def catalogue(db):
    call_command("seed_services")


@pytest.fixture
def visit(catalogue):
    patient = Patient.objects.create(
        first_name="Amina", last_name="Hassan", date_of_birth=date(1992, 3, 14), sex="F"
    )
    return Visit.objects.create(patient=patient, status=VisitStatus.IN_CONSULTATION)


@pytest.fixture
def malaria_test(catalogue):
    return Service.objects.get(code="LAB-MPS")


def test_an_order_raises_one_charge_at_the_catalogue_price(visit, malaria_test):
    order = place_order(visit=visit, service=malaria_test)

    assert order.invoice_line.unit_price == malaria_test.unit_price
    assert order.invoice_line.description == malaria_test.name
    assert visit.invoice.total == malaria_test.unit_price


def test_the_charge_follows_the_quantity_ordered(visit, catalogue):
    order = place_order(visit=visit, service=Service.objects.get(code="PHA-PARA"), quantity=12)

    assert order.invoice_line.quantity == 12
    assert order.invoice_line.line_total == Decimal("120.00")


def test_pay_per_service_holds_the_department_until_the_line_is_paid(visit, malaria_test):
    order = place_order(visit=visit, service=malaria_test)
    assert order.is_cleared is False
    assert list(worklist(Department.LABORATORY)) == []

    take_payment(
        invoice=visit.invoice,
        line_ids=[order.invoice_line_id],
        method="cash",
        received_by=None,
    )

    order.refresh_from_db()
    assert order.is_cleared is True
    assert list(worklist(Department.LABORATORY)) == [order]


def test_consolidated_billing_never_holds_work_up(catalogue, malaria_test):
    patient = Patient.objects.create(
        first_name="Staff", last_name="Member", date_of_birth=date(1988, 1, 1), sex="M"
    )
    visit = Visit.objects.create(patient=patient, billing_mode=BillingMode.CONSOLIDATED)

    order = place_order(visit=visit, service=malaria_test)

    assert order.is_cleared is True
    assert list(worklist(Department.LABORATORY)) == [order]


def test_a_worklist_holds_only_its_own_department(visit, catalogue):
    lab = place_order(visit=visit, service=Service.objects.get(code="LAB-MPS"))
    pharmacy = place_order(visit=visit, service=Service.objects.get(code="PHA-PARA"))
    take_payment(
        invoice=visit.invoice,
        line_ids=[lab.invoice_line_id, pharmacy.invoice_line_id],
        method="cash",
        received_by=None,
    )

    assert list(worklist(Department.LABORATORY)) == [lab]
    assert list(worklist(Department.PHARMACY)) == [pharmacy]


def test_urgent_visits_come_first_on_a_worklist(catalogue, malaria_test):
    orders = []
    for index, urgent in enumerate([False, True]):
        patient = Patient.objects.create(
            first_name=f"Patient{index}", last_name="Test",
            date_of_birth=date(1990, 1, 1), sex="M",
        )
        visit = Visit.objects.create(
            patient=patient, billing_mode=BillingMode.CONSOLIDATED, is_urgent=urgent
        )
        orders.append(place_order(visit=visit, service=malaria_test))

    routine, urgent = orders
    assert list(worklist(Department.LABORATORY)) == [urgent, routine]


def test_cancelling_an_order_voids_its_charge(visit, malaria_test):
    order = place_order(visit=visit, service=malaria_test)

    cancel_order(order)

    order.refresh_from_db()
    assert order.status == OrderStatus.CANCELLED
    assert order.invoice_line.status == LineStatus.CANCELLED
    # The bill no longer carries a charge for work that will not happen.
    assert visit.invoice.total == Decimal("0.00")


def test_a_paid_order_is_a_refund_not_a_cancellation(visit, malaria_test):
    order = place_order(visit=visit, service=malaria_test)
    take_payment(
        invoice=visit.invoice,
        line_ids=[order.invoice_line_id],
        method="mpesa",
        received_by=None,
    )

    with pytest.raises(OrderError, match="refund"):
        cancel_order(order)

    order.refresh_from_db()
    assert order.status == OrderStatus.ORDERED


def test_nothing_can_be_ordered_on_a_closed_visit(visit, malaria_test):
    visit.close()

    with pytest.raises(OrderError, match="closed"):
        place_order(visit=visit, service=malaria_test)

    assert Order.objects.count() == 0


def test_a_retired_service_cannot_be_ordered_again(visit, malaria_test):
    malaria_test.is_active = False
    malaria_test.save(update_fields=["is_active"])

    with pytest.raises(OrderError, match="retired"):
        place_order(visit=visit, service=malaria_test)
