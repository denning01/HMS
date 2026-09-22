"""The bench: the order of the three steps, and what each one refuses."""

from datetime import date

import pytest
from django.core.management import call_command

from apps.billing.models import Service
from apps.billing.services import take_payment
from apps.laboratory.models import Specimen
from apps.laboratory.services import (
    LabError,
    collect_specimen,
    record_result,
    release_result,
)
from apps.orders.models import OrderStatus
from apps.orders.services import place_order
from apps.patients.models import BillingMode, Patient, Visit, VisitStatus


@pytest.fixture
def catalogue(db):
    call_command("seed_services")
    call_command("seed_lab_tests")


def make_visit(mode=BillingMode.PAY_PER_SERVICE, name="Amina"):
    patient = Patient.objects.create(
        first_name=name, last_name="Hassan", date_of_birth=date(1992, 3, 14), sex="F"
    )
    return Visit.objects.create(
        patient=patient, status=VisitStatus.IN_CONSULTATION, billing_mode=mode
    )


@pytest.fixture
def order(catalogue):
    return place_order(visit=make_visit(), service=Service.objects.get(code="LAB-MPS"))


def pay_for(order):
    take_payment(
        invoice=order.visit.invoice,
        line_ids=[order.invoice_line_id],
        method="cash",
        received_by=None,
    )
    order.refresh_from_db()


def test_nothing_is_collected_before_the_charge_is_paid(order):
    with pytest.raises(LabError, match="till"):
        collect_specimen(order)


def test_collecting_takes_the_specimen_the_test_needs(order):
    pay_for(order)

    result = collect_specimen(order)

    order.refresh_from_db()
    assert result.specimen == Specimen.BLOOD
    assert result.is_collected
    assert order.status == OrderStatus.IN_PROGRESS


def test_a_specimen_is_collected_once(order):
    pay_for(order)
    collect_specimen(order)

    with pytest.raises(LabError, match="already collected"):
        collect_specimen(order)


def test_a_result_needs_a_specimen_first(order):
    pay_for(order)

    with pytest.raises(LabError, match="Collect the specimen"):
        record_result(order, findings="No parasites seen")


def test_a_result_needs_something_written_in_it(order):
    pay_for(order)
    collect_specimen(order)

    with pytest.raises(LabError, match="something written"):
        record_result(order, findings="   ")


def test_there_is_nothing_to_release_until_a_result_is_written(order):
    pay_for(order)
    collect_specimen(order)

    with pytest.raises(LabError, match="no result to release"):
        release_result(order)


def test_a_result_can_be_corrected_until_it_is_released(order):
    pay_for(order)
    collect_specimen(order)
    record_result(order, findings="Parasites seen", is_abnormal=True)

    corrected = record_result(order, findings="No parasites seen", is_abnormal=False)

    assert corrected.findings == "No parasites seen"
    assert corrected.is_abnormal is False


def test_releasing_closes_the_labs_part_of_the_order(order):
    pay_for(order)
    collect_specimen(order)
    record_result(order, findings="No parasites seen")

    result = release_result(order)

    order.refresh_from_db()
    assert result.is_released
    assert result.turnaround_minutes is not None
    assert order.status == OrderStatus.COMPLETED


def test_a_released_result_can_no_longer_be_changed(order):
    pay_for(order)
    collect_specimen(order)
    record_result(order, findings="No parasites seen")
    release_result(order)

    with pytest.raises(LabError, match="released"):
        record_result(order, findings="Actually, parasites seen")

    with pytest.raises(LabError, match="already been released"):
        release_result(order)


def test_consolidated_billing_lets_the_bench_start_at_once(catalogue):
    visit = make_visit(BillingMode.CONSOLIDATED, name="Staff")
    order = place_order(visit=visit, service=Service.objects.get(code="LAB-MPS"))

    result = collect_specimen(order)

    assert result.is_collected


def test_a_pharmacy_order_is_not_the_labs_to_touch(catalogue):
    order = place_order(
        visit=make_visit(BillingMode.CONSOLIDATED, name="Other"),
        service=Service.objects.get(code="PHA-PARA"),
    )

    with pytest.raises(LabError, match="not a laboratory test"):
        collect_specimen(order)
