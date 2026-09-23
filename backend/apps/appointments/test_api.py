"""The diary over the API: who may book, who may run the desk."""

from datetime import date, timedelta

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.appointments.models import Appointment, AppointmentStatus
from apps.appointments.services import book
from apps.patients.models import Patient, Visit


@pytest.fixture
def roles(db):
    call_command("seed_roles")
    call_command("seed_services")


def make_user(username, *role_list):
    user = User.objects.create_user(
        username=username, password="pw-for-tests-only", first_name="Ruth", last_name="Wanjiku"
    )
    for role in role_list:
        user.groups.add(Group.objects.get(name=role.value))
    return user


@pytest.fixture
def desk(roles):
    return make_user("front-desk", Role.RECEPTIONIST)


@pytest.fixture
def patient(roles):
    return Patient.objects.create(
        first_name="Amina", last_name="Hassan", date_of_birth=date(1992, 3, 14), sex="F"
    )


def tomorrow_at(hour=10):
    when = timezone.localtime() + timedelta(days=1)
    return when.replace(hour=hour, minute=0, second=0, microsecond=0)


def post(client, url, payload=None):
    return client.post(url, payload or {}, content_type="application/json")


def test_the_diary_refuses_anonymous_callers(client, db):
    assert client.get(reverse("api_appointments")).status_code == 401


def test_the_lab_has_no_business_in_the_diary(roles, client):
    client.force_login(make_user("bench", Role.LAB_TECHNICIAN))
    assert client.get(reverse("api_appointments")).status_code == 403


def test_the_desk_books_a_patient(desk, client, patient):
    client.force_login(desk)

    response = post(
        client,
        reverse("api_appointments"),
        {
            "patient": patient.pk,
            "scheduled_for": tomorrow_at().isoformat(),
            "department": "consultation",
            "reason": "Review after treatment",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == AppointmentStatus.BOOKED
    assert response.json()["patient"]["mrn"] == patient.mrn


def test_the_doctor_books_the_follow_up_but_does_not_run_the_desk(roles, client, patient):
    client.force_login(make_user("doctor", Role.DOCTOR))

    booked = post(
        client,
        reverse("api_appointments"),
        {
            "patient": patient.pk,
            "scheduled_for": tomorrow_at(14).isoformat(),
            "department": "consultation",
            "reason": "Review in one week",
        },
    )
    assert booked.status_code == 201

    # Confirming, cancelling and admitting are the front desk's work.
    appointment_id = booked.json()["id"]
    assert post(client, reverse("api_confirm_appointment", args=[appointment_id])).status_code == 403
    assert post(client, reverse("api_arrive_appointment", args=[appointment_id])).status_code == 403


def test_a_time_in_the_past_is_refused(desk, client, patient):
    client.force_login(desk)

    response = post(
        client,
        reverse("api_appointments"),
        {
            "patient": patient.pk,
            "scheduled_for": (timezone.now() - timedelta(hours=2)).isoformat(),
            "department": "consultation",
        },
    )

    assert response.status_code == 409
    assert "passed" in response.json()["detail"]


def test_the_day_list_shows_the_day_and_the_chase_list_shows_the_late(desk, client, patient):
    booked = book(patient=patient, scheduled_for=tomorrow_at(), department="consultation")
    late = book(
        patient=Patient.objects.create(
            first_name="Late", last_name="Comer", date_of_birth=date(1980, 1, 1), sex="M"
        ),
        scheduled_for=timezone.now() + timedelta(minutes=1),
        department="consultation",
    )
    Appointment.objects.filter(pk=late.pk).update(
        scheduled_for=timezone.now() - timedelta(minutes=20)
    )

    client.force_login(desk)
    diary = client.get(reverse("api_appointments") + f"?day={booked.scheduled_for.date()}").json()

    assert [row["id"] for row in diary["day_list"]] == [booked.pk]
    assert [row["id"] for row in diary["overdue"]] == [late.pk]
    assert diary["can_run_desk"] is True


def test_arriving_opens_the_visit_without_retyping_the_patient(desk, client, patient):
    appointment = book(patient=patient, scheduled_for=tomorrow_at(), department="consultation")
    client.force_login(desk)

    response = post(client, reverse("api_arrive_appointment", args=[appointment.pk]),
                    {"billing_mode": "pay_per_service"})

    assert response.status_code == 201
    assert response.json()["appointment"]["status"] == AppointmentStatus.ARRIVED
    visit_id = response.json()["visit"]["id"]
    assert Visit.objects.get(pk=visit_id).invoice.total > 0

    # It leaves the chase list and carries the visit it became.
    diary = client.get(reverse("api_appointments")).json()
    assert all(row["id"] != appointment.pk for row in diary["upcoming"])


def test_a_patient_already_in_the_building_is_not_admitted_twice(desk, client, patient):
    appointment = book(patient=patient, scheduled_for=tomorrow_at(), department="consultation")
    Visit.objects.create(patient=patient)
    client.force_login(desk)

    response = post(client, reverse("api_arrive_appointment", args=[appointment.pk]))

    assert response.status_code == 409
    assert "already has an open visit" in response.json()["detail"]


def test_cancelling_records_why(desk, client, patient):
    appointment = book(patient=patient, scheduled_for=tomorrow_at(), department="consultation")
    client.force_login(desk)

    response = post(
        client,
        reverse("api_cancel_appointment", args=[appointment.pk]),
        {"note": "Patient rang to cancel"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == AppointmentStatus.CANCELLED
    assert response.json()["outcome_note"] == "Patient rang to cancel"


def test_a_no_show_is_refused_before_the_appointment_comes_round(desk, client, patient):
    appointment = book(patient=patient, scheduled_for=tomorrow_at(), department="consultation")
    client.force_login(desk)

    response = post(client, reverse("api_no_show_appointment", args=[appointment.pk]))

    assert response.status_code == 409
    assert "not late" in response.json()["detail"]
