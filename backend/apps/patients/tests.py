"""Tests for the Patient and Visit core."""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.patients.models import BillingMode, Patient, Visit, VisitStatus


@pytest.fixture
def patient(db):
    return Patient.objects.create(
        first_name="Amina",
        last_name="Otieno",
        date_of_birth=date(1990, 6, 15),
        sex="F",
        phone_number="0712345678",
    )


def test_mrn_is_assigned_on_creation(patient):
    assert patient.mrn == f"MRN{patient.pk:06d}"


def test_mrn_is_unique_and_stable(db):
    first = Patient.objects.create(
        first_name="A", last_name="One", date_of_birth=date(2000, 1, 1), sex="M"
    )
    second = Patient.objects.create(
        first_name="B", last_name="Two", date_of_birth=date(2000, 1, 1), sex="F"
    )
    assert first.mrn != second.mrn

    original = first.mrn
    first.first_name = "Changed"
    first.save()
    first.refresh_from_db()
    assert first.mrn == original


def test_full_name_includes_middle_name_when_present(patient):
    assert patient.full_name == "Amina Otieno"

    patient.middle_name = "Akinyi"
    assert patient.full_name == "Amina Akinyi Otieno"


def test_age_counts_completed_years(db):
    today = date.today()
    # A birthday that has not happened yet this year.
    not_yet = today.replace(year=today.year - 30) + timedelta(days=1)
    patient = Patient.objects.create(
        first_name="X", last_name="Y", date_of_birth=not_yet, sex="M"
    )
    assert patient.age == 29


def test_paediatric_flag(db):
    today = date.today()
    child = Patient.objects.create(
        first_name="Kid",
        last_name="Z",
        date_of_birth=today.replace(year=today.year - 10),
        sex="M",
    )
    assert child.is_paediatric


def test_visit_defaults_to_awaiting_triage_and_pay_per_service(patient):
    visit = Visit.objects.create(patient=patient)

    assert visit.status == VisitStatus.AWAITING_TRIAGE
    assert visit.billing_mode == BillingMode.PAY_PER_SERVICE
    assert visit.is_open
    assert not visit.is_urgent


def test_first_visit_flag_distinguishes_new_from_returning(patient):
    first = Visit.objects.create(patient=patient)
    assert first.is_first_visit

    # A patient returns only after the previous attendance has been closed.
    first.close()
    second = Visit.objects.create(patient=patient)
    assert not second.is_first_visit
    assert not first.is_first_visit


def test_closing_a_visit_stamps_the_time_and_ends_it(patient):
    visit = Visit.objects.create(patient=patient)
    before = timezone.now()

    visit.close()
    visit.refresh_from_db()

    assert visit.status == VisitStatus.COMPLETED
    assert visit.closed_at >= before
    assert not visit.is_open


def test_cancelled_visit_is_not_open(patient):
    visit = Visit.objects.create(patient=patient)
    visit.close(status=VisitStatus.CANCELLED)

    assert not visit.is_open
    assert visit.status == VisitStatus.CANCELLED
