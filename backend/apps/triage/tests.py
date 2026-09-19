"""Tests for triage: vitals, BMI, urgency flagging and the status transition."""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.patients.models import Patient, Visit, VisitStatus
from apps.triage.models import Vitals

NORMAL_READINGS = {
    "systolic_bp": 120,
    "diastolic_bp": 80,
    "pulse_rate": 72,
    "temperature": "36.6",
    "spo2": 98,
    "respiratory_rate": 16,
    "weight": "70.00",
    "height": "1.75",
}


@pytest.fixture
def roles(db):
    call_command("seed_roles")


@pytest.fixture
def nurse(roles):
    user = User.objects.create_user(username="nurse", password="pw-for-tests-only")
    user.groups.add(Group.objects.get(name=Role.TRIAGE_NURSE.value))
    return user


@pytest.fixture
def visit(db):
    patient = Patient.objects.create(
        first_name="Amina",
        last_name="Otieno",
        date_of_birth=date(1990, 6, 15),
        sex="F",
    )
    return Visit.objects.create(patient=patient)


def make_vitals(visit, **overrides):
    values = {
        "systolic_bp": 120,
        "diastolic_bp": 80,
        "pulse_rate": 72,
        "temperature": Decimal("36.6"),
        "spo2": 98,
        "respiratory_rate": 16,
        "weight": Decimal("70.00"),
        "height": Decimal("1.75"),
    }
    values.update(overrides)
    return Vitals.objects.create(visit=visit, **values)


def test_bmi_is_derived_from_weight_and_height(visit):
    vitals = make_vitals(visit, weight=Decimal("70.00"), height=Decimal("1.75"))

    assert vitals.bmi == Decimal("22.9")
    assert vitals.bmi_category == "Normal"


@pytest.mark.parametrize(
    "weight,height,category",
    [
        ("45.00", "1.75", "Underweight"),
        ("70.00", "1.75", "Normal"),
        ("80.00", "1.75", "Overweight"),
        ("95.00", "1.75", "Obese"),
    ],
)
def test_bmi_categories(visit, weight, height, category):
    vitals = make_vitals(visit, weight=Decimal(weight), height=Decimal(height))

    assert vitals.bmi_category == category


def test_normal_readings_are_not_urgent(visit):
    assert make_vitals(visit).urgency_reasons() == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("spo2", 88),
        ("systolic_bp", 190),
        ("systolic_bp", 85),
        ("diastolic_bp", 130),
        ("temperature", Decimal("39.2")),
        ("temperature", Decimal("34.5")),
        ("pulse_rate", 135),
        ("pulse_rate", 45),
        ("respiratory_rate", 30),
        ("respiratory_rate", 8),
    ],
)
def test_out_of_range_readings_flag_urgency(visit, field, value):
    vitals = make_vitals(visit, **{field: value})

    assert vitals.is_urgent
    assert vitals.urgency_reasons()


def test_blood_pressure_is_shown_as_a_pair(visit):
    assert make_vitals(visit).blood_pressure == "120/80"


def test_triage_queue_requires_the_nurse_role(roles, client):
    clerk = User.objects.create_user(username="clerk", password="pw-for-tests-only")
    clerk.groups.add(Group.objects.get(name=Role.RECEPTIONIST.value))
    client.force_login(clerk)

    assert client.get(reverse("triage_queue")).status_code == 403


def test_queue_lists_only_visits_awaiting_triage(nurse, visit, client):
    client.force_login(nurse)
    other_patient = Patient.objects.create(
        first_name="Brian",
        last_name="Otieno",
        date_of_birth=date(1990, 5, 2),
        sex="M",
    )
    seen = Visit.objects.create(
        patient=other_patient, status=VisitStatus.AWAITING_CONSULTATION
    )

    response = client.get(reverse("triage_queue"))

    assert response.status_code == 200
    assert str(visit.pk) in response.content.decode()
    assert f"/triage/{seen.pk}/vitals/" not in response.content.decode()


def test_recording_vitals_moves_the_visit_to_consultation(nurse, visit, client):
    client.force_login(nurse)

    response = client.post(reverse("record_vitals", args=[visit.pk]), NORMAL_READINGS)

    visit.refresh_from_db()
    assert response.status_code == 302
    assert visit.status == VisitStatus.AWAITING_CONSULTATION
    assert not visit.is_urgent
    assert visit.vitals.recorded_by == nurse


def test_out_of_range_vitals_mark_the_visit_urgent(nurse, visit, client):
    client.force_login(nurse)
    readings = NORMAL_READINGS | {"spo2": 85}

    client.post(reverse("record_vitals", args=[visit.pk]), readings)

    visit.refresh_from_db()
    assert visit.is_urgent
    assert visit.status == VisitStatus.AWAITING_CONSULTATION


def test_diastolic_above_systolic_is_rejected(nurse, visit, client):
    client.force_login(nurse)
    readings = NORMAL_READINGS | {"systolic_bp": 80, "diastolic_bp": 120}

    response = client.post(reverse("record_vitals", args=[visit.pk]), readings)

    visit.refresh_from_db()
    assert response.status_code == 200
    assert b"must be lower than systolic" in response.content
    assert visit.status == VisitStatus.AWAITING_TRIAGE
    assert not hasattr(visit, "vitals")


def test_vitals_cannot_be_recorded_twice_for_one_visit(nurse, visit, client):
    client.force_login(nurse)
    client.post(reverse("record_vitals", args=[visit.pk]), NORMAL_READINGS)

    response = client.post(
        reverse("record_vitals", args=[visit.pk]), NORMAL_READINGS | {"spo2": 80}
    )

    visit.refresh_from_db()
    assert response.status_code == 302
    assert visit.vitals.spo2 == 98
    assert not visit.is_urgent


def test_vitals_cannot_be_recorded_on_a_closed_visit(nurse, visit, client):
    client.force_login(nurse)
    visit.close()

    response = client.post(reverse("record_vitals", args=[visit.pk]), NORMAL_READINGS)

    assert response.status_code == 302
    assert not Vitals.objects.filter(visit=visit).exists()
