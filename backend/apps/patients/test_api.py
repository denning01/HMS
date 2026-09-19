"""Tests for the Registration and Triage API."""

from datetime import date

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.patients.models import BillingMode, Patient, Visit, VisitStatus


@pytest.fixture
def roles(db):
    call_command("seed_roles")
    call_command("seed_services")


def make_user(username, *role_list):
    user = User.objects.create_user(username=username, password="pw-for-tests-only")
    for role in role_list:
        user.groups.add(Group.objects.get(name=role.value))
    return user


@pytest.fixture
def receptionist(roles):
    return make_user("clerk", Role.RECEPTIONIST)


@pytest.fixture
def nurse(roles):
    return make_user("nurse", Role.TRIAGE_NURSE)


@pytest.fixture
def patient(roles):
    return Patient.objects.create(
        first_name="Amina",
        last_name="Hassan",
        date_of_birth=date(1992, 3, 14),
        sex="F",
        phone_number="0722000111",
    )


NORMAL_VITALS = {
    "systolic_bp": 120, "diastolic_bp": 80, "pulse_rate": 72, "temperature": "36.6",
    "spo2": 98, "respiratory_rate": 16, "weight": "70.00", "height": "1.75",
}


# --- registration ----------------------------------------------------------


def test_search_requires_the_receptionist_role(roles, client):
    client.force_login(make_user("pharm", Role.PHARMACIST))

    assert client.get(reverse("api_patients"), {"q": "Amina"}).status_code == 403


@pytest.mark.parametrize("term", ["Amina", "Hassan", "0722000111"])
def test_search_matches_name_and_phone(receptionist, patient, client, term):
    client.force_login(receptionist)

    rows = client.get(reverse("api_patients"), {"q": term}).json()

    assert [row["mrn"] for row in rows] == [patient.mrn]


def test_an_empty_search_returns_nothing(receptionist, patient, client):
    """Search before create: a blank box must not list the whole register."""
    client.force_login(receptionist)

    assert client.get(reverse("api_patients"), {"q": ""}).json() == []


def test_registering_a_patient_assigns_an_mrn_and_records_the_clerk(receptionist, client):
    client.force_login(receptionist)

    response = client.post(
        reverse("api_patients"),
        {"first_name": "Brian", "last_name": "Otieno", "date_of_birth": "1990-05-02", "sex": "M"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["mrn"].startswith("MRN")
    assert Patient.objects.get(last_name="Otieno").created_by == receptionist


def test_a_future_date_of_birth_is_rejected(receptionist, client):
    client.force_login(receptionist)

    response = client.post(
        reverse("api_patients"),
        {"first_name": "Time", "last_name": "Traveller", "date_of_birth": "2999-01-01", "sex": "F"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "date_of_birth" in response.json()


# --- opening a visit -------------------------------------------------------


def test_starting_a_visit_sends_the_patient_to_triage_and_raises_the_fee(receptionist, patient, client):
    client.force_login(receptionist)

    response = client.post(
        reverse("api_start_visit", args=[patient.pk]), {}, content_type="application/json"
    )

    assert response.status_code == 201
    visit = patient.visits.get()
    assert visit.status == VisitStatus.AWAITING_TRIAGE
    assert visit.billing_mode == BillingMode.PAY_PER_SERVICE
    assert visit.invoice.total == 500


def test_consolidated_billing_can_be_chosen(receptionist, patient, client):
    client.force_login(receptionist)

    client.post(
        reverse("api_start_visit", args=[patient.pk]),
        {"billing_mode": "consolidated"},
        content_type="application/json",
    )

    assert patient.visits.get().billing_mode == BillingMode.CONSOLIDATED


def test_an_unrecognised_billing_mode_is_refused(receptionist, patient, client):
    client.force_login(receptionist)

    response = client.post(
        reverse("api_start_visit", args=[patient.pk]),
        {"billing_mode": "free-for-me"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not patient.visits.exists()


def test_a_second_open_visit_is_refused(receptionist, patient, client):
    client.force_login(receptionist)
    Visit.objects.create(patient=patient)

    response = client.post(
        reverse("api_start_visit", args=[patient.pk]), {}, content_type="application/json"
    )

    assert response.status_code == 409
    assert patient.visits.count() == 1


# --- triage ----------------------------------------------------------------


def test_the_triage_queue_is_closed_to_the_receptionist(receptionist, client):
    client.force_login(receptionist)

    assert client.get(reverse("api_triage_queue")).status_code == 403


def test_the_queue_lists_only_visits_awaiting_triage(nurse, patient, client):
    waiting = Visit.objects.create(patient=patient)
    other = Patient.objects.create(
        first_name="Brian", last_name="Otieno", date_of_birth=date(1990, 5, 2), sex="M"
    )
    Visit.objects.create(patient=other, status=VisitStatus.AWAITING_CONSULTATION)
    client.force_login(nurse)

    rows = client.get(reverse("api_triage_queue")).json()

    assert [row["id"] for row in rows] == [waiting.pk]


def test_recording_vitals_moves_the_visit_on_and_returns_the_bmi(nurse, patient, client):
    visit = Visit.objects.create(patient=patient)
    client.force_login(nurse)

    response = client.post(
        reverse("api_vitals", args=[visit.pk]), NORMAL_VITALS, content_type="application/json"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["vitals"]["bmi"] == "22.9"
    assert body["vitals"]["is_urgent"] is False
    assert body["visit"]["status"] == VisitStatus.AWAITING_CONSULTATION


def test_out_of_range_vitals_flag_the_visit_urgent_with_reasons(nurse, patient, client):
    visit = Visit.objects.create(patient=patient)
    client.force_login(nurse)

    response = client.post(
        reverse("api_vitals", args=[visit.pk]),
        {**NORMAL_VITALS, "spo2": 90, "temperature": "38.9"},
        content_type="application/json",
    )

    body = response.json()
    assert body["vitals"]["is_urgent"] is True
    assert body["visit"]["is_urgent"] is True
    assert any("SpO" in reason for reason in body["vitals"]["urgency_reasons"])


def test_diastolic_above_systolic_is_rejected(nurse, patient, client):
    visit = Visit.objects.create(patient=patient)
    client.force_login(nurse)

    response = client.post(
        reverse("api_vitals", args=[visit.pk]),
        {**NORMAL_VITALS, "systolic_bp": 80, "diastolic_bp": 120},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "diastolic_bp" in response.json()


def test_vitals_cannot_be_recorded_twice(nurse, patient, client):
    visit = Visit.objects.create(patient=patient)
    client.force_login(nurse)
    client.post(reverse("api_vitals", args=[visit.pk]), NORMAL_VITALS, content_type="application/json")

    again = client.post(
        reverse("api_vitals", args=[visit.pk]), NORMAL_VITALS, content_type="application/json"
    )

    assert again.status_code == 409


def test_vitals_cannot_be_recorded_on_a_closed_visit(nurse, patient, client):
    visit = Visit.objects.create(patient=patient)
    visit.close()
    client.force_login(nurse)

    response = client.post(
        reverse("api_vitals", args=[visit.pk]), NORMAL_VITALS, content_type="application/json"
    )

    assert response.status_code == 409
