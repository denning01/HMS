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
