"""The pharmacy over the API: the queue, the shelf, and who may touch either."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.billing.models import Service
from apps.billing.services import charge_consultation
from apps.orders.services import place_order
from apps.patients.models import BillingMode, Patient, Visit, VisitStatus
from apps.pharmacy.models import StockItem
from apps.pharmacy.services import receive_stock


@pytest.fixture
def roles(db):
    call_command("seed_roles")
    call_command("seed_services")
    call_command("seed_stock_items")


def make_user(username, *role_list):
    user = User.objects.create_user(
        username=username, password="pw-for-tests-only", first_name="Peter", last_name="Muturi"
    )
    for role in role_list:
        user.groups.add(Group.objects.get(name=role.value))
    return user


@pytest.fixture
def pharmacist(roles):
    return make_user("counter", Role.PHARMACIST)


@pytest.fixture
def paracetamol(roles):
    return StockItem.objects.get(service__code="PHA-PARA")


@pytest.fixture
def stocked(paracetamol):
    receive_stock(
        paracetamol, quantity=500, unit_cost=Decimal("3.50"),
        expires_on=timezone.localdate() + timedelta(days=365), batch_number="PB-1",
    )
    return paracetamol


def make_visit(mode=BillingMode.CONSOLIDATED, name="Amina"):
    patient = Patient.objects.create(
        first_name=name, last_name="Hassan", date_of_birth=date(1992, 3, 14), sex="F"
    )
    visit = Visit.objects.create(
        patient=patient, status=VisitStatus.IN_CONSULTATION, billing_mode=mode
    )
    charge_consultation(visit)
    return visit


@pytest.fixture
def order(roles):
    return place_order(
        visit=make_visit(), service=Service.objects.get(code="PHA-PARA"), quantity=12
    )


def post(client, url, payload=None):
    return client.post(url, payload or {}, content_type="application/json")


# --- who may reach the counter ----------------------------------------------


def test_the_pharmacy_api_refuses_anonymous_callers(client, db):
    assert client.get(reverse("api_dispensing")).status_code == 401


def test_the_doctor_who_prescribed_it_does_not_dispense_it(roles, client, order):
    client.force_login(make_user("doctor", Role.DOCTOR))

    assert client.get(reverse("api_dispensing")).status_code == 403
    assert post(client, reverse("api_dispense", args=[order.pk])).status_code == 403


def test_finance_reads_the_shelf_but_does_not_move_it(roles, client, paracetamol):
    client.force_login(make_user("finance", Role.FINANCE_MANAGER))

    assert client.get(reverse("api_stock")).status_code == 200
    assert post(
        client,
        reverse("api_receive_stock", args=[paracetamol.pk]),
        {"quantity": 10, "unit_cost": "3.00", "expires_on": "2030-01-01"},
    ).status_code == 403


# --- the queue ---------------------------------------------------------------


def test_the_queue_carries_the_directions_and_what_is_on_the_shelf(pharmacist, client, stocked):
    visit = make_visit(name="Grace")
    doctor = make_user("doc2", Role.DOCTOR)
    client.force_login(doctor)
    post(
        client,
        reverse("api_place_order", args=[visit.pk]),
        {
            "service": Service.objects.get(code="PHA-PARA").pk,
            "quantity": 12,
            "directions": {
                "dosage": "1 tablet", "frequency": "three times a day",
                "duration": "4 days", "instructions": "after food",
            },
        },
    )

    client.force_login(pharmacist)
    row = client.get(reverse("api_dispensing")).json()["ready"][0]

    assert row["prescription"]["directions"] == (
        "1 tablet, three times a day, 4 days — after food"
    )
    assert row["stock"]["available"] == 500
    assert row["stock"]["is_enough"] is True


def test_an_unpaid_prescription_is_shown_as_waiting_on_the_till(pharmacist, client, stocked):
    place_order(
        visit=make_visit(BillingMode.PAY_PER_SERVICE, name="Held"),
        service=Service.objects.get(code="PHA-PARA"),
        quantity=6,
    )
    client.force_login(pharmacist)

    queue = client.get(reverse("api_dispensing")).json()

    assert queue["ready"] == []
    assert queue["awaiting_payment"][0]["quantity"] == 6


# --- dispensing --------------------------------------------------------------


def test_dispensing_moves_the_stock_and_says_which_batch(pharmacist, client, stocked, order):
    client.force_login(pharmacist)

    response = post(client, reverse("api_dispense", args=[order.pk]))

    assert response.status_code == 200
    assert response.json()["order"]["prescription"]["is_dispensed"] is True
    assert response.json()["movements"][0]["quantity"] == -12
    assert response.json()["movements"][0]["batch_number"] == "PB-1"

    stocked.refresh_from_db()
    assert stocked.quantity_in_stock == 488
    # And it leaves the queue.
    assert client.get(reverse("api_dispensing")).json()["ready"] == []


def test_short_stock_is_refused_with_the_number_the_pharmacist_needs(pharmacist, client, paracetamol, order):
    receive_stock(
        paracetamol, quantity=5, unit_cost=Decimal("3.50"),
        expires_on=timezone.localdate() + timedelta(days=200),
    )
    client.force_login(pharmacist)

    response = post(client, reverse("api_dispense", args=[order.pk]))

    assert response.status_code == 409
    assert "Only 5" in response.json()["detail"]


# --- the shelf ---------------------------------------------------------------


def test_the_shelf_reports_what_is_short_and_what_is_about_to_expire(pharmacist, client, paracetamol):
    receive_stock(
        paracetamol, quantity=10, unit_cost=Decimal("3.50"),
        expires_on=timezone.localdate() + timedelta(days=20), batch_number="NEAR",
    )
    client.force_login(pharmacist)

    shelf = client.get(reverse("api_stock")).json()

    names = [item["name"] for item in shelf["low_stock"]]
    assert "Paracetamol" in names
    assert [batch["batch_number"] for batch in shelf["expiring"]] == ["NEAR"]


def test_receiving_a_delivery_puts_it_on_the_shelf_with_its_cost(pharmacist, client, paracetamol):
    client.force_login(pharmacist)

    response = post(
        client,
        reverse("api_receive_stock", args=[paracetamol.pk]),
        {
            "quantity": 200, "unit_cost": "3.20",
            "expires_on": (timezone.localdate() + timedelta(days=400)).isoformat(),
            "batch_number": "PB-9", "supplier": "Dawa Ltd",
        },
    )

    assert response.status_code == 201
    assert response.json()["quantity_remaining"] == 200
    assert response.json()["unit_cost"] == "3.20"

    detail = client.get(reverse("api_stock_item", args=[paracetamol.pk])).json()
    assert detail["item"]["quantity"] == 200
    assert detail["movements"][0]["reason"] == "received"


def test_expired_stock_cannot_be_received(pharmacist, client, paracetamol):
    client.force_login(pharmacist)

    response = post(
        client,
        reverse("api_receive_stock", args=[paracetamol.pk]),
        {
            "quantity": 10, "unit_cost": "3.00",
            "expires_on": (timezone.localdate() - timedelta(days=1)).isoformat(),
        },
    )

    assert response.status_code == 409


def test_a_write_off_is_recorded_against_the_batch_with_its_reason(pharmacist, client, stocked):
    batch = stocked.batches.first()
    client.force_login(pharmacist)

    response = post(
        client,
        reverse("api_write_off", args=[batch.pk]),
        {"quantity": 20, "reason": "wastage", "note": "Water damage"},
    )

    assert response.status_code == 201
    assert response.json()["quantity"] == -20
    stocked.refresh_from_db()
    assert stocked.quantity_in_stock == 480


def test_the_movements_show_who_a_dispensing_was_for(pharmacist, client, stocked, order):
    client.force_login(pharmacist)
    post(client, reverse("api_dispense", args=[order.pk]))

    movements = client.get(reverse("api_stock_item", args=[stocked.pk])).json()["movements"]

    dispensed = next(m for m in movements if m["reason"] == "dispensed")
    assert dispensed["patient_mrn"] == order.visit.patient.mrn
    assert dispensed["cost_total"] == "42.00"
