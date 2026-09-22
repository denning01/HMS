"""The consulting room over the API: who may use it, and what it refuses."""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.billing.models import LineStatus, Service
from apps.billing.services import charge_consultation, take_payment
from apps.orders.models import Order, OrderStatus
from apps.orders.services import place_order
from apps.patients.models import Patient, Visit, VisitStatus
from apps.triage.models import Vitals


@pytest.fixture
def roles(db):
    call_command("seed_roles")
    call_command("seed_services")


def make_user(username, *role_list):
    user = User.objects.create_user(
        username=username, password="pw-for-tests-only", first_name="Esther", last_name="Njoki"
    )
    for role in role_list:
        user.groups.add(Group.objects.get(name=role.value))
    return user


@pytest.fixture
def doctor(roles):
    return make_user("doctor", Role.DOCTOR)


@pytest.fixture
def waiting_visit(roles):
    patient = Patient.objects.create(
        first_name="Amina", last_name="Hassan", date_of_birth=date(1992, 3, 14), sex="F"
    )
    visit = Visit.objects.create(patient=patient, status=VisitStatus.AWAITING_CONSULTATION)
    charge_consultation(visit)
    return visit


def sign_in(client, user):
    client.force_login(user)
    return client


def post(client, url, payload):
    return client.post(url, payload, content_type="application/json")


# --- who may reach the consulting room -------------------------------------


def test_the_consultation_api_refuses_anonymous_callers(client, db):
    assert client.get(reverse("api_consultation_queue")).status_code == 403


def test_a_receptionist_is_refused_the_doctors_queue(roles, client):
    sign_in(client, make_user("front-desk", Role.RECEPTIONIST))
    assert client.get(reverse("api_consultation_queue")).status_code == 403


def test_a_triage_nurse_may_read_the_record_but_not_write_it(roles, client, waiting_visit):
    sign_in(client, make_user("nurse", Role.TRIAGE_NURSE))
    url = reverse("api_consultation", args=[waiting_visit.pk])

    read = client.get(url)
    assert read.status_code == 200
    assert read.json()["can_edit"] is False

    assert post(client, url, {"chief_complaint": "Fever"}).status_code == 403


def test_a_nurse_cannot_order_or_close(roles, client, waiting_visit):
    sign_in(client, make_user("nurse2", Role.TRIAGE_NURSE))

    assert post(
        client, reverse("api_place_order", args=[waiting_visit.pk]), {"service": 1}
    ).status_code == 403
    assert post(
        client, reverse("api_close_visit", args=[waiting_visit.pk]), {}
    ).status_code == 403


# --- the queue --------------------------------------------------------------


def test_the_queue_shows_vitals_and_puts_urgent_cases_first(roles, client, doctor):
    for name, urgent in [("Routine", False), ("Urgent", True)]:
        patient = Patient.objects.create(
            first_name=name, last_name="Case", date_of_birth=date(1990, 1, 1), sex="M"
        )
        visit = Visit.objects.create(
            patient=patient, status=VisitStatus.AWAITING_CONSULTATION, is_urgent=urgent
        )
        Vitals.objects.create(
            visit=visit, systolic_bp=120, diastolic_bp=80, pulse_rate=70,
            temperature=Decimal("37.0"), spo2=90 if urgent else 98,
            respiratory_rate=16, weight=Decimal("70.00"), height=Decimal("1.70"),
            presenting_complaint="Headache",
        )

    sign_in(client, doctor)
    rows = client.get(reverse("api_consultation_queue")).json()

    assert [row["patient"]["full_name"] for row in rows] == ["Urgent Case", "Routine Case"]
    assert rows[0]["vitals"]["blood_pressure"] == "120/80"
    assert "SpO₂ 90%" in rows[0]["urgency_reasons"]


# --- the note ---------------------------------------------------------------


def test_saving_the_note_starts_the_consultation(roles, client, doctor, waiting_visit):
    sign_in(client, doctor)

    response = post(
        client,
        reverse("api_consultation", args=[waiting_visit.pk]),
        {"chief_complaint": "Fever for three days", "diagnosis": "Malaria"},
    )

    assert response.status_code == 201
    assert response.json()["doctor_name"] == "Esther Njoki"

    waiting_visit.refresh_from_db()
    assert waiting_visit.status == VisitStatus.IN_CONSULTATION


def test_the_note_is_added_to_rather_than_replaced(roles, client, doctor, waiting_visit):
    sign_in(client, doctor)
    url = reverse("api_consultation", args=[waiting_visit.pk])

    post(client, url, {"chief_complaint": "Fever for three days"})
    second = post(client, url, {"diagnosis": "Malaria"})

    assert second.status_code == 200
    assert second.json()["chief_complaint"] == "Fever for three days"
    assert second.json()["diagnosis"] == "Malaria"


def test_the_complaint_cannot_be_erased(roles, client, doctor, waiting_visit):
    sign_in(client, doctor)
    url = reverse("api_consultation", args=[waiting_visit.pk])
    post(client, url, {"chief_complaint": "Fever"})

    response = post(client, url, {"chief_complaint": "   "})

    assert response.status_code == 400
    assert "chief_complaint" in response.json()


def test_a_male_patients_record_never_carries_a_gynae_history(roles, client, doctor):
    patient = Patient.objects.create(
        first_name="Joseph", last_name="Kariuki", date_of_birth=date(1975, 6, 2), sex="M"
    )
    visit = Visit.objects.create(patient=patient, status=VisitStatus.AWAITING_CONSULTATION)

    sign_in(client, doctor)
    response = post(
        client,
        reverse("api_consultation", args=[visit.pk]),
        {"chief_complaint": "Cough", "gynaecological_history": "posted anyway"},
    )

    assert response.status_code == 201
    assert response.json()["gynaecological_history"] == ""
    assert response.json()["applies_gynae_obstetric_history"] is False


def test_the_note_cannot_be_changed_after_the_visit_closes(roles, client, doctor, waiting_visit):
    waiting_visit.close()
    sign_in(client, doctor)

    response = post(
        client, reverse("api_consultation", args=[waiting_visit.pk]), {"chief_complaint": "Fever"}
    )
    assert response.status_code == 409


# --- ordering ---------------------------------------------------------------


def test_ordering_a_test_bills_it_at_the_catalogue_price(roles, client, doctor, waiting_visit):
    sign_in(client, doctor)
    test = Service.objects.get(code="LAB-MPS")

    response = post(
        client,
        reverse("api_place_order", args=[waiting_visit.pk]),
        # A client that posts its own price is posting into a field that does
        # not exist; the price comes from the catalogue.
        {"service": test.pk, "quantity": 1, "unit_price": "1.00", "clinical_details": "Fever"},
    )

    assert response.status_code == 201
    assert response.json()["unit_price"] == "300.00"
    assert response.json()["is_cleared"] is False

    waiting_visit.refresh_from_db()
    assert waiting_visit.invoice.total == Decimal("800.00")
    assert waiting_visit.status == VisitStatus.IN_CONSULTATION


def test_an_order_is_cleared_once_the_cashier_takes_the_money(roles, client, doctor, waiting_visit):
    order = place_order(visit=waiting_visit, service=Service.objects.get(code="LAB-MPS"))
    take_payment(
        invoice=waiting_visit.invoice,
        line_ids=[order.invoice_line_id],
        method="mpesa",
        received_by=None,
    )

    sign_in(client, doctor)
    record = client.get(reverse("api_consultation", args=[waiting_visit.pk])).json()

    assert record["orders"][0]["is_cleared"] is True
    assert record["orders"][0]["payment_status"] == LineStatus.PAID


def test_cancelling_an_order_takes_its_charge_off_the_bill(roles, client, doctor, waiting_visit):
    order = place_order(visit=waiting_visit, service=Service.objects.get(code="LAB-MPS"))

    sign_in(client, doctor)
    response = post(client, reverse("api_cancel_order", args=[order.pk]), {})

    assert response.status_code == 200
    order.refresh_from_db()
    assert order.status == OrderStatus.CANCELLED
    assert waiting_visit.invoice.total == Decimal("500.00")


def test_a_paid_order_cannot_be_cancelled(roles, client, doctor, waiting_visit):
    order = place_order(visit=waiting_visit, service=Service.objects.get(code="LAB-MPS"))
    take_payment(
        invoice=waiting_visit.invoice,
        line_ids=[order.invoice_line_id],
        method="cash",
        received_by=None,
    )

    sign_in(client, doctor)
    response = post(client, reverse("api_cancel_order", args=[order.pk]), {})

    assert response.status_code == 409
    assert "refund" in response.json()["detail"]
    order.refresh_from_db()
    assert order.status == OrderStatus.ORDERED


# --- closing ----------------------------------------------------------------


def test_closing_is_refused_while_the_bill_is_unpaid(roles, client, doctor, waiting_visit):
    sign_in(client, doctor)

    response = post(client, reverse("api_close_visit", args=[waiting_visit.pk]), {})

    assert response.status_code == 409
    assert "cashier" in response.json()["detail"]
    waiting_visit.refresh_from_db()
    assert waiting_visit.is_open


def test_closing_is_refused_while_a_department_still_has_work(roles, client, doctor, waiting_visit):
    place_order(visit=waiting_visit, service=Service.objects.get(code="LAB-MPS"))
    take_payment(
        invoice=waiting_visit.invoice,
        line_ids=[line.pk for line in waiting_visit.invoice.lines.all()],
        method="cash",
        received_by=None,
    )

    sign_in(client, doctor)
    response = post(client, reverse("api_close_visit", args=[waiting_visit.pk]), {})

    assert response.status_code == 409
    assert "Malaria parasite smear" in response.json()["detail"]


def test_a_settled_visit_with_nothing_outstanding_closes(roles, client, doctor, waiting_visit):
    take_payment(
        invoice=waiting_visit.invoice,
        line_ids=[line.pk for line in waiting_visit.invoice.lines.all()],
        method="cash",
        received_by=None,
    )

    sign_in(client, doctor)
    response = post(client, reverse("api_close_visit", args=[waiting_visit.pk]), {})

    assert response.status_code == 200
    assert response.json()["status"] == VisitStatus.COMPLETED
    # And it leaves the queue.
    assert client.get(reverse("api_consultation_queue")).json() == []


# --- the catalogue the doctor orders from -----------------------------------


def test_the_doctor_reads_the_price_list_by_department(roles, client, doctor):
    sign_in(client, doctor)

    rows = client.get(reverse("api_services") + "?department=laboratory").json()

    assert rows
    assert {row["department"] for row in rows} == {"laboratory"}
    assert all(Decimal(row["unit_price"]) > 0 for row in rows)


def test_a_retired_service_is_not_offered(roles, client, doctor):
    Service.objects.filter(code="LAB-MPS").update(is_active=False)
    sign_in(client, doctor)

    codes = [row["code"] for row in client.get(reverse("api_services")).json()]

    assert "LAB-MPS" not in codes


def test_the_price_list_is_not_open_to_the_front_desk(roles, client):
    sign_in(client, make_user("desk", Role.RECEPTIONIST))
    assert client.get(reverse("api_services")).status_code == 403


def test_nothing_can_be_ordered_on_a_closed_visit(roles, client, doctor, waiting_visit):
    waiting_visit.close()
    sign_in(client, doctor)

    response = post(
        client,
        reverse("api_place_order", args=[waiting_visit.pk]),
        {"service": Service.objects.get(code="LAB-MPS").pk},
    )

    assert response.status_code == 409
    assert Order.objects.count() == 0
