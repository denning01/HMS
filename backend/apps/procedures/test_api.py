"""The procedure room over the API."""

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
        username=username, password="pw-for-tests-only", first_name="Pauline", last_name="Cherono"
    )
    for role in role_list:
        user.groups.add(Group.objects.get(name=role.value))
    return user


@pytest.fixture
def nurse(roles):
    return make_user("room", Role.PROCEDURE_NURSE)


@pytest.fixture
def gauze(roles):
    item = StockItem.objects.get(name="Gauze swabs")
    receive_stock(
        item, quantity=100, unit_cost=Decimal("12.00"),
        expires_on=timezone.localdate() + timedelta(days=400), batch_number="G-1",
    )
    return item


def make_order(mode=BillingMode.CONSOLIDATED, name="Amina", code="PRO-DRESS"):
    patient = Patient.objects.create(
        first_name=name, last_name="Hassan", date_of_birth=date(1992, 3, 14), sex="F"
    )
    visit = Visit.objects.create(
        patient=patient, status=VisitStatus.IN_CONSULTATION, billing_mode=mode
    )
    charge_consultation(visit)
    return place_order(
        visit=visit,
        service=Service.objects.get(code=code),
        clinical_details="Dress the wound on the left forearm",
    )


def post(client, url, payload=None):
    return client.post(url, payload or {}, content_type="application/json")


def test_the_procedure_api_refuses_anonymous_callers(client, db):
    assert client.get(reverse("api_procedure_worklist")).status_code == 401


def test_the_doctor_who_ordered_it_does_not_do_it(roles, client):
    order = make_order()
    client.force_login(make_user("doctor", Role.DOCTOR))

    assert client.get(reverse("api_procedure_worklist")).status_code == 403
    assert post(client, reverse("api_perform_procedure", args=[order.pk])).status_code == 403


def test_the_queue_shows_what_is_ready_and_what_is_held(nurse, client):
    ready = make_order(name="Ready")
    make_order(BillingMode.PAY_PER_SERVICE, name="Held")
    client.force_login(nurse)

    queue = client.get(reverse("api_procedure_worklist")).json()

    assert [row["id"] for row in queue["ready"]] == [ready.pk]
    assert len(queue["awaiting_payment"]) == 1
    assert queue["ready"][0]["clinical_details"].startswith("Dress the wound")


def test_the_room_is_offered_only_consumables_it_actually_has(nurse, client, gauze):
    order = make_order()
    client.force_login(nurse)

    offered = client.get(reverse("api_procedure_order", args=[order.pk])).json()["consumables"]

    assert [item["name"] for item in offered] == ["Gauze swabs"]


def test_performing_records_the_procedure_and_the_stock_it_used(nurse, client, gauze):
    order = make_order()
    client.force_login(nurse)

    response = post(
        client,
        reverse("api_perform_procedure", args=[order.pk]),
        {
            "notes": "Cleaned and redressed; patient tolerated it well",
            "consumables": [{"item": gauze.pk, "quantity": 4}],
        },
    )

    assert response.status_code == 200
    record = response.json()["record"]
    assert record["is_performed"] is True
    assert record["performed_by_name"] == "Pauline Cherono"
    assert record["consumable_cost"] == "48.00"
    assert record["consumables"][0]["quantity"] == -4

    gauze.refresh_from_db()
    assert gauze.quantity_in_stock == 96
    assert client.get(reverse("api_procedure_worklist")).json()["ready"] == []


def test_short_consumables_are_refused_with_the_number_on_the_shelf(nurse, client, gauze):
    order = make_order()
    client.force_login(nurse)

    response = post(
        client,
        reverse("api_perform_procedure", args=[order.pk]),
        {"consumables": [{"item": gauze.pk, "quantity": 500}]},
    )

    assert response.status_code == 409
    assert "Only 100" in response.json()["detail"]
    gauze.refresh_from_db()
    assert gauze.quantity_in_stock == 100


def test_the_doctor_reads_back_what_the_room_did(roles, client, nurse, gauze):
    order = make_order()
    client.force_login(nurse)
    post(
        client,
        reverse("api_perform_procedure", args=[order.pk]),
        {"notes": "Cleaned and redressed", "consumables": [{"item": gauze.pk, "quantity": 2}]},
    )

    client.force_login(make_user("doctor2", Role.DOCTOR))
    record = client.get(reverse("api_consultation", args=[order.visit_id])).json()

    procedure = next(o for o in record["orders"] if o["id"] == order.pk)["procedure"]
    assert procedure["notes"] == "Cleaned and redressed"
    assert procedure["performed_by_name"] == "Pauline Cherono"
