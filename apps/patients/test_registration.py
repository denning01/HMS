"""Tests for the Registration screens."""

from datetime import date

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.patients.models import Patient, Visit, VisitStatus


@pytest.fixture
def roles(db):
    call_command("seed_roles")


def make_user(username, *role_list):
    user = User.objects.create_user(username=username, password="pw-for-tests-only")
    for role in role_list:
        user.groups.add(Group.objects.get(name=role.value))
    return user


@pytest.fixture
def receptionist(roles):
    return make_user("clerk", Role.RECEPTIONIST)


@pytest.fixture
def patient(db):
    return Patient.objects.create(
        first_name="Amina",
        last_name="Otieno",
        date_of_birth=date(1990, 6, 15),
        sex="F",
        phone_number="0712345678",
    )


def test_registration_requires_login(client):
    response = client.get(reverse("registration_home"))

    assert response.status_code == 302
    assert reverse("login") in response["Location"]


def test_registration_forbidden_for_other_roles(roles, client):
    """A signed-in user without the role gets 403, not a login loop."""
    nurse = make_user("nurse", Role.TRIAGE_NURSE)
    client.force_login(nurse)

    response = client.get(reverse("registration_home"))

    assert response.status_code == 403


def test_receptionist_can_open_registration(receptionist, client):
    client.force_login(receptionist)

    response = client.get(reverse("registration_home"))

    assert response.status_code == 200
    assert b"Search for the patient first" in response.content


@pytest.mark.parametrize("term", ["Amina", "Otieno", "0712345678", "MRN"])
def test_search_matches_name_phone_and_mrn(receptionist, patient, client, term):
    client.force_login(receptionist)

    response = client.get(reverse("patient_search"), {"q": term})

    assert response.status_code == 200
    assert b"Amina Otieno" in response.content


def test_search_offers_registration_when_nothing_matches(receptionist, patient, client):
    client.force_login(receptionist)

    response = client.get(reverse("patient_search"), {"q": "Nobody"})

    assert b"No patient matches" in response.content
    assert b"Register as new patient" in response.content


def test_empty_search_returns_nothing(receptionist, patient, client):
    client.force_login(receptionist)

    response = client.get(reverse("patient_search"), {"q": "   "})

    assert b"Amina Otieno" not in response.content
    assert b"No patient matches" not in response.content


def test_registering_a_patient_records_the_clerk(receptionist, client):
    client.force_login(receptionist)

    response = client.post(
        reverse("patient_create"),
        {
            "first_name": "Brian",
            "middle_name": "",
            "last_name": "Kamau",
            "date_of_birth": "1985-03-02",
            "sex": "M",
            "phone_number": "0700111222",
            "residence": "Kasarani",
            "national_id": "12345678",
            "next_of_kin_name": "Grace Kamau",
            "next_of_kin_relationship": "spouse",
            "next_of_kin_phone": "0700333444",
        },
    )

    created = Patient.objects.get(last_name="Kamau")
    assert response.status_code == 302
    assert response["Location"] == reverse("patient_detail", args=[created.pk])
    assert created.created_by == receptionist
    assert created.mrn


def test_future_date_of_birth_is_rejected(receptionist, client):
    client.force_login(receptionist)

    response = client.post(
        reverse("patient_create"),
        {
            "first_name": "Time",
            "last_name": "Traveller",
            "date_of_birth": "2999-01-01",
            "sex": "M",
        },
    )

    assert response.status_code == 200
    assert b"cannot be in the future" in response.content
    assert not Patient.objects.filter(last_name="Traveller").exists()


def test_starting_a_visit_sends_the_patient_to_triage(receptionist, patient, client):
    client.force_login(receptionist)

    client.post(reverse("start_visit", args=[patient.pk]), {"billing_mode": "pay_per_service"})

    visit = patient.visits.get()
    assert visit.status == VisitStatus.AWAITING_TRIAGE
    assert visit.created_by == receptionist
    assert visit.billing_mode == "pay_per_service"


def test_consolidated_billing_can_be_chosen_at_registration(receptionist, patient, client):
    client.force_login(receptionist)

    client.post(reverse("start_visit", args=[patient.pk]), {"billing_mode": "consolidated"})

    assert patient.visits.get().billing_mode == "consolidated"


def test_a_second_open_visit_is_refused(receptionist, patient, client):
    """Two open visits would split one attendance's charges across two bills."""
    client.force_login(receptionist)
    Visit.objects.create(patient=patient)

    client.post(reverse("start_visit", args=[patient.pk]))

    assert patient.visits.count() == 1


def test_a_new_visit_is_allowed_once_the_previous_one_closed(receptionist, patient, client):
    client.force_login(receptionist)
    previous = Visit.objects.create(patient=patient)
    previous.close()

    client.post(reverse("start_visit", args=[patient.pk]))

    assert patient.visits.count() == 2


def test_start_visit_rejects_get(receptionist, patient, client):
    client.force_login(receptionist)

    response = client.get(reverse("start_visit", args=[patient.pk]))

    assert response.status_code == 405
    assert patient.visits.count() == 0
