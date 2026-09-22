"""The revenue report over the API: who may read it, and what it says."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.billing.models import Service
from apps.billing.services import take_payment
from apps.orders.services import place_order
from apps.patients.models import BillingMode, Patient, Visit, VisitStatus
from apps.pharmacy.models import StockItem
from apps.pharmacy.services import dispense, receive_stock


@pytest.fixture
def roles(db):
    call_command("seed_roles")
    call_command("seed_services")
    call_command("seed_stock_items")


def make_user(username, *role_list):
    user = User.objects.create_user(
        username=username, password="pw-for-tests-only", first_name="Faith", last_name="Mutiso"
    )
    for role in role_list:
        user.groups.add(Group.objects.get(name=role.value))
    return user


@pytest.fixture
def finance(roles):
    return make_user("owner", Role.FINANCE_MANAGER)


@pytest.fixture
def a_days_trading(roles):
    item = StockItem.objects.get(service__code="PHA-PARA")
    receive_stock(
        item, quantity=100, unit_cost=Decimal("3.00"),
        expires_on=timezone.localdate() + timedelta(days=400),
    )

    patient = Patient.objects.create(
        first_name="Amina", last_name="Hassan", date_of_birth=date(1992, 3, 14), sex="F"
    )
    visit = Visit.objects.create(
        patient=patient, status=VisitStatus.IN_CONSULTATION,
        billing_mode=BillingMode.CONSOLIDATED,
    )
    drug = place_order(
        visit=visit, service=Service.objects.get(code="PHA-PARA"), quantity=12
    )
    take_payment(
        invoice=visit.invoice, line_ids=[drug.invoice_line_id],
        method="cash", received_by=make_user("till", Role.CASHIER),
    )
    drug.refresh_from_db()
    dispense(drug)
    return visit


def test_the_report_refuses_anonymous_callers(client, db):
    assert client.get(reverse("api_revenue_report")).status_code == 403


def test_the_cashier_reconciles_but_does_not_read_the_owners_figure(roles, client):
    client.force_login(make_user("cashier", Role.CASHIER))

    assert client.get(reverse("api_revenue_report")).status_code == 403
    # Collections is still theirs — a different question of the same payments.
    assert client.get(reverse("api_collections")).status_code == 200


def test_the_doctor_has_no_business_in_the_revenue_report(roles, client):
    client.force_login(make_user("doctor", Role.DOCTOR))
    assert client.get(reverse("api_revenue_report")).status_code == 403


def test_the_report_puts_revenue_cost_and_profit_side_by_side(finance, client, a_days_trading):
    client.force_login(finance)

    figures = client.get(reverse("api_revenue_report")).json()

    assert figures["revenue"] == "120.00"
    assert figures["cost"] == "36.00"
    assert figures["profit"] == "84.00"
    assert figures["receipts"] == 1


def test_the_default_range_is_the_week_ending_today(finance, client):
    client.force_login(finance)

    figures = client.get(reverse("api_revenue_report")).json()

    assert figures["to"] == timezone.localdate().isoformat()
    assert figures["days"] == 7
    assert len(figures["daily"]) == 7


def test_a_range_the_wrong_way_round_is_read_as_a_typo(finance, client):
    client.force_login(finance)
    today = timezone.localdate()
    earlier = today - timedelta(days=3)

    figures = client.get(
        reverse("api_revenue_report") + f"?from={today}&to={earlier}"
    ).json()

    assert figures["from"] == earlier.isoformat()
    assert figures["to"] == today.isoformat()


def test_an_unreadable_date_falls_back_rather_than_failing(finance, client):
    client.force_login(finance)

    figures = client.get(reverse("api_revenue_report") + "?from=not-a-date").json()

    assert figures["invalid_range"] is True
    assert figures["days"] == 7


def test_the_split_names_the_department_the_method_and_the_cashier(finance, client, a_days_trading):
    client.force_login(finance)

    figures = client.get(reverse("api_revenue_report")).json()

    assert [row["key"] for row in figures["by_department"]] == ["pharmacy"]
    assert figures["by_department"][0]["total"] == "120.00"
    assert {row["key"]: row["total"] for row in figures["by_method"]}["cash"] == "120.00"
    assert figures["by_cashier"][0]["name"] == "Faith Mutiso"
    assert [row["key"] for row in figures["cost_by_reason"]] == ["dispensed"]
