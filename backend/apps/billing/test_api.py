"""Tests for the API the React client calls.

The server-rendered screens are gone, so these are the only guard on the rules
that used to live in the views: who may call what, and what the server refuses.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.billing.models import LineStatus, PaymentMethod, Service
from apps.billing.services import charge, take_payment
from apps.patients.models import Patient, Visit


@pytest.fixture
def roles(db):
    call_command("seed_roles")
    call_command("seed_services")


def make_user(username, *role_list):
    user = User.objects.create_user(
        username=username, password="pw-for-tests-only", first_name="Caleb", last_name="Omondi"
    )
    for role in role_list:
        user.groups.add(Group.objects.get(name=role.value))
    return user


@pytest.fixture
def cashier(roles):
    return make_user("till", Role.CASHIER)


@pytest.fixture
def billed_visit(roles):
    patient = Patient.objects.create(
        first_name="Amina", last_name="Hassan", date_of_birth=date(1992, 3, 14), sex="F"
    )
    visit = Visit.objects.create(patient=patient)
    charge(visit, Service.objects.get(code="CONS-GEN"))
    charge(visit, Service.objects.get(code="LAB-MPS"))
    return visit


# --- authentication --------------------------------------------------------


def test_the_api_refuses_anonymous_callers(client, db):
    assert client.get(reverse("api_till")).status_code == 401


def test_signed_out_and_not_allowed_are_different_answers(cashier, client, db):
    """The client shows a sign-in screen for one and an explanation for the
    other, and cannot tell them apart if both come back 403."""
    signed_out = client.get(reverse("api_till"))

    client.force_login(cashier)
    not_allowed = client.get(reverse("api_revenue_report"))

    assert signed_out.status_code == 401
    assert not_allowed.status_code == 403


def test_login_starts_a_session_and_returns_the_user(cashier, client):
    response = client.post(
        reverse("api_login"),
        {"username": "till", "password": "pw-for-tests-only"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["roles"] == [Role.CASHIER.value]
    assert response.json()["primary_role"] == Role.CASHIER.value
    # The session cookie now authenticates further calls without a token.
    assert client.get(reverse("api_me")).status_code == 200


def test_a_wrong_password_does_not_reveal_whether_the_account_exists(cashier, client):
    missing = client.post(
        reverse("api_login"),
        {"username": "nobody", "password": "wrong"},
        content_type="application/json",
    )
    wrong = client.post(
        reverse("api_login"),
        {"username": "till", "password": "wrong"},
        content_type="application/json",
    )

    assert missing.status_code == wrong.status_code == 400
    assert missing.json()["detail"] == wrong.json()["detail"]


def test_logout_ends_the_session(cashier, client):
    client.force_login(cashier)

    assert client.post(reverse("api_logout")).status_code == 204
    # 401, not 403: the next request finds nobody signed in, which is what sends
    # the client back to the sign-in screen.
    assert client.get(reverse("api_me")).status_code == 401


# --- roles -----------------------------------------------------------------


@pytest.mark.parametrize("role", [Role.TRIAGE_NURSE, Role.PHARMACIST, Role.RECEPTIONIST])
def test_the_till_is_closed_to_other_roles(roles, client, role):
    client.force_login(make_user(f"user-{role.value}", role))

    assert client.get(reverse("api_till")).status_code == 403


def test_the_finance_manager_reads_bills_but_cannot_take_payment(roles, billed_visit, client):
    client.force_login(make_user("finance", Role.FINANCE_MANAGER))
    invoice = billed_visit.invoice
    line = invoice.lines.first()

    detail = client.get(reverse("api_invoice", args=[invoice.pk]))
    assert detail.status_code == 200
    assert detail.json()["can_take_payment"] is False

    response = client.post(
        reverse("api_pay", args=[invoice.pk]),
        {"lines": [line.pk], "method": PaymentMethod.CASH},
        content_type="application/json",
    )

    assert response.status_code == 403
    line.refresh_from_db()
    assert line.status == LineStatus.UNPAID


# --- the till and payment --------------------------------------------------


def test_the_till_lists_outstanding_bills(cashier, billed_visit, client):
    client.force_login(cashier)

    rows = client.get(reverse("api_till")).json()

    assert len(rows) == 1
    assert rows[0]["number"] == billed_visit.invoice.number
    assert rows[0]["balance"] == "800.00"


def test_a_settled_bill_drops_off_the_till(cashier, billed_visit, client):
    invoice = billed_visit.invoice
    take_payment(
        invoice=invoice,
        line_ids=list(invoice.lines.values_list("pk", flat=True)),
        method=PaymentMethod.CASH,
        received_by=cashier,
    )
    client.force_login(cashier)

    assert client.get(reverse("api_till")).json() == []


def test_paying_selected_lines_returns_the_receipt(cashier, billed_visit, client):
    client.force_login(cashier)
    invoice = billed_visit.invoice
    consultation = invoice.lines.get(service__code="CONS-GEN")

    response = client.post(
        reverse("api_pay", args=[invoice.pk]),
        {"lines": [consultation.pk], "method": PaymentMethod.MPESA, "reference": "QGH7X2K9LM"},
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["amount"] == "500.00"
    assert body["receipt_number"].startswith("RCT")
    assert body["reference"] == "QGH7X2K9LM"
    # Only the line it settled, not the whole bill.
    assert [line["description"] for line in body["lines"]] == ["General consultation"]
    assert invoice.balance == Decimal("300.00")


def test_the_amount_cannot_be_dictated_by_the_client(cashier, billed_visit, client):
    """A posted amount is ignored; the server prices the lines itself."""
    client.force_login(cashier)
    invoice = billed_visit.invoice
    line = invoice.lines.get(service__code="CONS-GEN")

    response = client.post(
        reverse("api_pay", args=[invoice.pk]),
        {"lines": [line.pk], "method": PaymentMethod.CASH, "amount": "1.00"},
        content_type="application/json",
    )

    assert response.json()["amount"] == "500.00"


def test_paying_a_line_twice_is_refused(cashier, billed_visit, client):
    client.force_login(cashier)
    invoice = billed_visit.invoice
    line = invoice.lines.first()
    payload = {"lines": [line.pk], "method": PaymentMethod.CASH}

    client.post(reverse("api_pay", args=[invoice.pk]), payload, content_type="application/json")
    again = client.post(
        reverse("api_pay", args=[invoice.pk]), payload, content_type="application/json"
    )

    assert again.status_code == 409
    assert "Already settled" in again.json()["detail"]
    assert invoice.payments.count() == 1


def test_paying_nothing_is_refused(cashier, billed_visit, client):
    client.force_login(cashier)

    response = client.post(
        reverse("api_pay", args=[billed_visit.invoice.pk]),
        {"lines": [], "method": PaymentMethod.CASH},
        content_type="application/json",
    )

    assert response.status_code == 400


def test_money_is_serialised_as_a_string_not_a_float(cashier, billed_visit, client):
    """Floats would render bills like 919.9999999; money stays exact."""
    client.force_login(cashier)

    rows = client.get(reverse("api_till")).json()

    assert isinstance(rows[0]["balance"], str)


# --- collections -----------------------------------------------------------


def test_collections_reports_the_days_takings(cashier, billed_visit, client):
    invoice = billed_visit.invoice
    take_payment(
        invoice=invoice,
        line_ids=[invoice.lines.get(service__code="CONS-GEN").pk],
        method=PaymentMethod.MPESA,
        received_by=cashier,
    )
    client.force_login(cashier)

    body = client.get(reverse("api_collections")).json()

    assert body["total"] == "500.00"
    assert body["outstanding"] == "300.00"
    assert body["is_today"] is True
    assert {"key": "mpesa", "label": "M-Pesa", "total": "500.00"} in body["by_method"]
    assert body["by_cashier"] == [{"name": "Caleb Omondi", "total": "500.00"}]


def test_an_unparseable_date_falls_back_to_today(cashier, client):
    client.force_login(cashier)

    body = client.get(reverse("api_collections"), {"day": "not-a-date"}).json()

    assert body["invalid_day"] is True
    assert body["is_today"] is True
