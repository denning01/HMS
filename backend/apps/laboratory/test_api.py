"""The laboratory over the API: the worklist, the three steps, and who may act."""

from datetime import date

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.billing.models import Service
from apps.billing.services import charge_consultation, take_payment
from apps.orders.services import place_order
from apps.patients.models import Patient, Visit, VisitStatus


@pytest.fixture
def roles(db):
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


@pytest.fixture
def technician(roles):
    return make_user("bench", Role.LAB_TECHNICIAN)


@pytest.fixture
def order(roles):
    patient = Patient.objects.create(
        first_name="Amina", last_name="Hassan", date_of_birth=date(1992, 3, 14), sex="F"
    )
    visit = Visit.objects.create(patient=patient, status=VisitStatus.IN_CONSULTATION)
    charge_consultation(visit)
    return place_order(
        visit=visit,
        service=Service.objects.get(code="LAB-MPS"),
        clinical_details="Fever, query malaria",
    )


def pay_for(order):
    take_payment(
        invoice=order.visit.invoice,
        line_ids=[order.invoice_line_id],
        method="cash",
        received_by=None,
    )
    order.refresh_from_db()


def post(client, url, payload=None):
    return client.post(url, payload or {}, content_type="application/json")


# --- who may reach the bench ------------------------------------------------


def test_the_lab_api_refuses_anonymous_callers(client, db):
    assert client.get(reverse("api_lab_worklist")).status_code == 403


def test_the_doctor_who_ordered_it_does_not_work_the_bench(roles, client, order):
    client.force_login(make_user("doctor", Role.DOCTOR))

    assert client.get(reverse("api_lab_worklist")).status_code == 403
    assert post(client, reverse("api_lab_collect", args=[order.pk])).status_code == 403


# --- the worklist -----------------------------------------------------------


def test_an_unpaid_test_is_listed_as_waiting_on_money_not_hidden(technician, client, order):
    client.force_login(technician)

    worklist = client.get(reverse("api_lab_worklist")).json()

    assert worklist["ready"] == []
    assert [row["name"] for row in worklist["awaiting_payment"]] == ["Malaria parasite smear"]
    # The technician can tell the patient exactly what is holding it up.
    assert worklist["awaiting_payment"][0]["payment_status"] == "unpaid"


def test_a_paid_test_reaches_the_bench_with_what_the_doctor_asked(technician, client, order):
    pay_for(order)
    client.force_login(technician)

    row = client.get(reverse("api_lab_worklist")).json()["ready"][0]

    assert row["mrn"] == order.visit.patient.mrn
    assert row["clinical_details"] == "Fever, query malaria"
    assert row["specimen"] == "blood"
    assert row["reference_range"] == "No parasites seen"
    assert row["result"] is None


# --- the three steps --------------------------------------------------------


def test_the_bench_walks_specimen_to_released_result(technician, client, order):
    pay_for(order)
    client.force_login(technician)

    collected = post(client, reverse("api_lab_collect", args=[order.pk]))
    assert collected.status_code == 200
    assert collected.json()["result"]["stage"] == "specimen collected"

    recorded = post(
        client,
        reverse("api_lab_result", args=[order.pk]),
        {"findings": "Plasmodium falciparum seen", "is_abnormal": True},
    )
    assert recorded.status_code == 200
    assert recorded.json()["result"]["stage"] == "awaiting release"

    released = post(client, reverse("api_lab_release", args=[order.pk]))
    assert released.status_code == 200
    assert released.json()["result"]["released_by_name"] == "Lena Achieng"
    assert released.json()["status"] == "completed"

    # And it leaves the bench.
    assert client.get(reverse("api_lab_worklist")).json()["ready"] == []


def test_a_result_cannot_be_written_before_the_specimen_is_taken(technician, client, order):
    pay_for(order)
    client.force_login(technician)

    response = post(
        client, reverse("api_lab_result", args=[order.pk]), {"findings": "Negative"}
    )

    assert response.status_code == 409
    assert "Collect the specimen" in response.json()["detail"]


def test_an_unpaid_test_cannot_be_started(technician, client, order):
    client.force_login(technician)

    response = post(client, reverse("api_lab_collect", args=[order.pk]))

    assert response.status_code == 409
    assert "till" in response.json()["detail"]


# --- back to the doctor -----------------------------------------------------


def test_the_doctor_sees_nothing_until_the_result_is_released(roles, client, order, technician):
    pay_for(order)
    client.force_login(technician)
    post(client, reverse("api_lab_collect", args=[order.pk]))
    post(client, reverse("api_lab_result", args=[order.pk]), {"findings": "Negative"})

    client.force_login(make_user("doctor2", Role.DOCTOR))
    record = client.get(reverse("api_consultation", args=[order.visit_id])).json()
    assert record["orders"][0]["result"] is None

    client.force_login(technician)
    post(client, reverse("api_lab_release", args=[order.pk]))

    client.force_login(make_user("doctor3", Role.DOCTOR))
    record = client.get(reverse("api_consultation", args=[order.visit_id])).json()
    assert record["orders"][0]["result"]["findings"] == "Negative"
    assert record["orders"][0]["result"]["is_released"] is True


def test_a_released_result_calls_the_patient_back_into_the_queue(roles, client, order, technician):
    pay_for(order)
    client.force_login(technician)
    post(client, reverse("api_lab_collect", args=[order.pk]))
    post(client, reverse("api_lab_result", args=[order.pk]), {"findings": "Negative"})
    post(client, reverse("api_lab_release", args=[order.pk]))

    client.force_login(make_user("doctor4", Role.DOCTOR))
    row = next(
        r for r in client.get(reverse("api_consultation_queue")).json()
        if r["id"] == order.visit_id
    )

    assert row["results_ready"] == 1
    assert row["open_orders"] == 0
