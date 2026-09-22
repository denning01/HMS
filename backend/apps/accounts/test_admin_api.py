"""Administration over the API: the price list, the stock list, the staff register."""

from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.billing.models import Service
from apps.pharmacy.models import StockItem


@pytest.fixture
def roles(db):
    call_command("seed_roles")
    call_command("seed_services")
    call_command("seed_stock_items")


def make_user(username, *role_list, **fields):
    user = User.objects.create_user(
        username=username, password="pw-for-tests-only",
        first_name=fields.pop("first_name", "Asha"),
        last_name=fields.pop("last_name", "Njoroge"),
        **fields,
    )
    for role in role_list:
        user.groups.add(Group.objects.get(name=role.value))
    return user


@pytest.fixture
def administrator(roles):
    return make_user("boss", Role.ADMINISTRATOR)


def post(client, url, payload=None):
    return client.post(url, payload or {}, content_type="application/json")


def patch(client, url, payload):
    return client.patch(url, payload, content_type="application/json")


# --- who may administer ------------------------------------------------------


def test_administration_refuses_anonymous_callers(client, db):
    assert client.get(reverse("api_admin_services")).status_code == 403


def test_the_finance_manager_reads_prices_but_does_not_set_them(roles, client):
    client.force_login(make_user("finance", Role.FINANCE_MANAGER))

    assert client.get(reverse("api_services")).status_code == 200
    assert client.get(reverse("api_admin_services")).status_code == 403


def test_only_the_administrator_touches_the_staff_register(roles, client):
    client.force_login(make_user("doctor", Role.DOCTOR))
    assert client.get(reverse("api_staff")).status_code == 403


# --- the price list ----------------------------------------------------------


def test_the_administrator_adds_a_service_to_the_price_list(administrator, client):
    client.force_login(administrator)

    response = post(
        client,
        reverse("api_admin_services"),
        {"code": "lab-esr", "name": "ESR", "department": "laboratory", "unit_price": "400.00"},
    )

    assert response.status_code == 201
    # Codes are stored as the reports and seeders match them.
    assert response.json()["code"] == "LAB-ESR"
    assert Service.objects.get(code="LAB-ESR").is_active is True


def test_a_price_change_does_not_rewrite_a_bill_already_issued(administrator, client, db):
    from datetime import date

    from apps.billing.services import charge
    from apps.patients.models import Patient, Visit

    patient = Patient.objects.create(
        first_name="Amina", last_name="Hassan", date_of_birth=date(1992, 3, 14), sex="F"
    )
    visit = Visit.objects.create(patient=patient)
    service = Service.objects.get(code="LAB-MPS")
    charge(visit, service)

    client.force_login(administrator)
    patch(client, reverse("api_admin_service", args=[service.pk]), {"unit_price": "450.00"})

    assert visit.invoice.total == Decimal("300.00")
    assert Service.objects.get(pk=service.pk).unit_price == Decimal("450.00")


def test_a_code_is_set_once_and_never_changed(administrator, client):
    service = Service.objects.get(code="LAB-MPS")
    client.force_login(administrator)

    patch(client, reverse("api_admin_service", args=[service.pk]), {"code": "LAB-OTHER"})

    service.refresh_from_db()
    assert service.code == "LAB-MPS"


def test_retiring_a_service_takes_it_off_the_order_screens_and_leaves_the_bills(
    administrator, client
):
    service = Service.objects.get(code="LAB-MPS")
    client.force_login(administrator)

    patch(client, reverse("api_admin_service", args=[service.pk]), {"is_active": False})

    offered = [row["code"] for row in client.get(reverse("api_services")).json()]
    listed = [row["code"] for row in client.get(reverse("api_admin_services")).json()]
    assert "LAB-MPS" not in offered
    assert "LAB-MPS" in listed


def test_a_negative_price_is_refused(administrator, client):
    client.force_login(administrator)

    response = post(
        client,
        reverse("api_admin_services"),
        {"code": "BAD", "name": "Bad", "department": "other", "unit_price": "-5.00"},
    )

    assert response.status_code == 400


# --- the stock list ----------------------------------------------------------


def test_the_pharmacist_adds_a_consumable_to_the_stock_list(roles, client):
    client.force_login(make_user("counter", Role.PHARMACIST))

    response = post(
        client,
        reverse("api_admin_stock_items"),
        {"name": "Sterile water 10ml", "form": "consumable", "unit": "vial", "reorder_level": 20},
    )

    assert response.status_code == 201
    assert StockItem.objects.get(name="Sterile water 10ml").reorder_level == 20


def test_a_reorder_level_can_be_corrected(roles, client):
    item = StockItem.objects.get(service__code="PHA-PARA")
    client.force_login(make_user("counter2", Role.PHARMACIST))

    patch(client, reverse("api_admin_stock_item", args=[item.pk]), {"reorder_level": 500})

    item.refresh_from_db()
    assert item.reorder_level == 500


# --- the staff register ------------------------------------------------------


def test_creating_an_account_assigns_the_roles_it_was_given(administrator, client):
    client.force_login(administrator)

    response = post(
        client,
        reverse("api_staff"),
        {
            "username": "new.nurse",
            "first_name": "Tom",
            "last_name": "Mwangi",
            "password": "a-strong-enough-password-42",
            "roles": [Role.TRIAGE_NURSE.value, Role.PROCEDURE_NURSE.value],
        },
    )

    assert response.status_code == 201
    assert response.json()["roles"] == ["Procedure Nurse", "Triage Nurse"]
    # And the new account can sign in with what was set.
    assert client.login(username="new.nurse", password="a-strong-enough-password-42")


def test_a_weak_password_is_refused_before_it_reaches_a_colleague(administrator, client):
    client.force_login(administrator)

    response = post(
        client,
        reverse("api_staff"),
        {"username": "weak", "password": "password", "roles": []},
    )

    assert response.status_code == 400
    assert "password" in response.json()


def test_a_username_is_not_reused(administrator, client):
    client.force_login(administrator)

    response = post(
        client,
        reverse("api_staff"),
        {"username": "BOSS", "password": "a-strong-enough-password-42"},
    )

    assert response.status_code == 400
    assert "username" in response.json()


def test_roles_are_replaced_by_what_the_screen_sends(administrator, client, roles):
    nurse = make_user("nurse", Role.TRIAGE_NURSE)
    client.force_login(administrator)

    response = patch(
        client, reverse("api_staff_detail", args=[nurse.pk]), {"roles": [Role.CASHIER.value]}
    )

    assert response.json()["roles"] == ["Cashier"]
    assert nurse.has_role(Role.TRIAGE_NURSE) is False


def test_an_account_can_be_switched_off_without_being_deleted(administrator, client, roles):
    leaver = make_user("leaver", Role.CASHIER)
    client.force_login(administrator)

    patch(client, reverse("api_staff_detail", args=[leaver.pk]), {"is_active": False})

    leaver.refresh_from_db()
    assert leaver.is_active is False
    # The record stays, because their name is on receipts.
    assert User.objects.filter(pk=leaver.pk).exists()


def test_an_administrator_cannot_lock_themselves_out(administrator, client):
    client.force_login(administrator)

    removed = patch(
        client, reverse("api_staff_detail", args=[administrator.pk]), {"roles": []}
    )
    deactivated = patch(
        client, reverse("api_staff_detail", args=[administrator.pk]), {"is_active": False}
    )

    assert removed.status_code == 409
    assert deactivated.status_code == 409
    administrator.refresh_from_db()
    assert administrator.is_active is True
    assert administrator.has_role(Role.ADMINISTRATOR)


def test_a_forgotten_password_is_reset_by_the_administrator(administrator, client, roles):
    colleague = make_user("forgetful", Role.RECEPTIONIST)
    client.force_login(administrator)

    response = post(
        client,
        reverse("api_staff_password", args=[colleague.pk]),
        {"password": "another-strong-password-77"},
    )

    assert response.status_code == 204
    assert client.login(username="forgetful", password="another-strong-password-77")
