"""Turnaround: asked of the stamps the bench already wrote down."""

from datetime import date, timedelta

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.billing.models import Service
from apps.laboratory import reports
from apps.laboratory.models import LabResult
from apps.laboratory.services import collect_specimen, record_result, release_result
from apps.orders.services import place_order
from apps.patients.models import BillingMode, Patient, Visit, VisitStatus


@pytest.fixture
def clinic(db):
    call_command("seed_roles")
    call_command("seed_services")
    call_command("seed_lab_tests")


def make_user(username, *role_list):
    user = User.objects.create_user(
        username=username, password="pw-for-tests-only", first_name="Lena", last_name="Achieng"
    )
    for role in role_list:
        user.groups.add(Group.objects.get(name=role.value))
    return user


def run_test(code="LAB-MPS", name="Amina", minutes=None):
    """Order a test and take it through the bench, with the clock moved by hand."""
    patient = Patient.objects.create(
        first_name=name, last_name="Hassan", date_of_birth=date(1992, 3, 14), sex="F"
    )
    visit = Visit.objects.create(
        patient=patient, status=VisitStatus.IN_CONSULTATION,
        billing_mode=BillingMode.CONSOLIDATED,
    )
    order = place_order(visit=visit, service=Service.objects.get(code=code))

    collect_specimen(order)
    record_result(order, findings="No parasites seen")
    release_result(order)

    if minutes:
        # The stamps are what the report reads, so the clock is moved on them.
        now = timezone.now()
        result = LabResult.objects.get(order=order)
        order.ordered_at = now - timedelta(minutes=minutes["total"])
        order.save(update_fields=["ordered_at"])
        result.collected_at = order.ordered_at + timedelta(minutes=minutes["to_specimen"])
        result.recorded_at = result.collected_at + timedelta(minutes=minutes["on_the_bench"])
        result.released_at = now
        result.save(update_fields=["collected_at", "recorded_at", "released_at"])

    return order


def today():
    return timezone.localdate()


def test_the_total_is_what_the_patient_waited(clinic):
    run_test(minutes={"total": 90, "to_specimen": 20, "on_the_bench": 50})

    figures = reports.summary(today(), today())

    assert figures["released"] == 1
    assert figures["median_minutes"] == 90


def test_the_three_legs_fail_for_different_reasons_so_are_reported_apart(clinic):
    run_test(minutes={"total": 120, "to_specimen": 60, "on_the_bench": 30})

    legs = reports.summary(today(), today())["legs"]

    assert legs["to_specimen"] == 60
    assert legs["on_the_bench"] == 30
    # The rest is a written result nobody had signed off.
    assert legs["to_release"] == 30


def test_one_slow_assay_does_not_make_a_slow_laboratory(clinic):
    run_test(code="LAB-MPS", name="Quick", minutes={"total": 30, "to_specimen": 5, "on_the_bench": 20})
    run_test(code="LAB-FBC", name="Slow", minutes={"total": 240, "to_specimen": 10, "on_the_bench": 200})

    rows = {row["code"]: row for row in reports.summary(today(), today())["by_test"]}

    assert rows["LAB-MPS"]["median_minutes"] == 30
    assert rows["LAB-FBC"]["median_minutes"] == 240
    # Slowest first, because that is the one to do something about.
    assert reports.summary(today(), today())["by_test"][0]["code"] == "LAB-FBC"


def test_nothing_released_yet_is_not_counted_as_fast(clinic):
    order = place_order(
        visit=Visit.objects.create(
            patient=Patient.objects.create(
                first_name="Open", last_name="Case", date_of_birth=date(1990, 1, 1), sex="M"
            ),
            status=VisitStatus.IN_CONSULTATION,
            billing_mode=BillingMode.CONSOLIDATED,
        ),
        service=Service.objects.get(code="LAB-MPS"),
    )
    collect_specimen(order)

    figures = reports.summary(today(), today())

    assert figures["released"] == 0
    assert figures["median_minutes"] is None
    # It shows in what is still waiting instead, which is the honest place.
    assert [row["order_id"] for row in figures["still_waiting"]] == [order.pk]
    assert figures["still_waiting"][0]["stage"] == "specimen collected"


def test_a_test_held_at_the_till_is_still_a_patient_waiting(clinic):
    patient = Patient.objects.create(
        first_name="Held", last_name="Up", date_of_birth=date(1990, 1, 1), sex="F"
    )
    visit = Visit.objects.create(patient=patient, status=VisitStatus.IN_CONSULTATION)
    order = place_order(visit=visit, service=Service.objects.get(code="LAB-MPS"))

    waiting = reports.summary(today(), today())["still_waiting"]

    assert [row["order_id"] for row in waiting] == [order.pk]
    assert waiting[0]["is_cleared"] is False


def test_a_result_released_last_month_is_not_in_this_weeks_figure(clinic):
    order = run_test(minutes={"total": 60, "to_specimen": 10, "on_the_bench": 40})
    result = LabResult.objects.get(order=order)
    result.released_at = timezone.now() - timedelta(days=40)
    result.save(update_fields=["released_at"])

    assert reports.summary(today(), today())["released"] == 0


# --- over the API ------------------------------------------------------------


def test_the_bench_reads_its_own_figure(clinic, client):
    run_test(minutes={"total": 45, "to_specimen": 10, "on_the_bench": 25})
    client.force_login(make_user("bench", Role.LAB_TECHNICIAN))

    figures = client.get(reverse("api_lab_turnaround")).json()

    assert figures["days"] == 7
    assert figures["released"] == 1
    assert figures["median_minutes"] == 45
    assert figures["by_test"][0]["name"] == "Malaria parasite smear"


def test_the_doctor_who_ordered_it_does_not_grade_the_lab(clinic, client):
    client.force_login(make_user("doctor", Role.DOCTOR))
    assert client.get(reverse("api_lab_turnaround")).status_code == 403


def test_the_finance_manager_reads_it(clinic, client):
    client.force_login(make_user("owner", Role.FINANCE_MANAGER))
    assert client.get(reverse("api_lab_turnaround")).status_code == 200


def test_an_unreadable_date_falls_back_rather_than_failing(clinic, client):
    client.force_login(make_user("bench2", Role.LAB_TECHNICIAN))

    figures = client.get(reverse("api_lab_turnaround") + "?from=last-tuesday").json()

    assert figures["invalid_range"] is True
    assert figures["days"] == 7
