"""Tests for the cashier's screens."""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.billing.models import LineStatus, PaymentMethod, Service
from apps.billing.services import charge, take_payment
from apps.patients.models import Patient, Visit, VisitStatus


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
def cashier(roles):
    return make_user("till", Role.CASHIER)


@pytest.fixture
def visit(roles):
    patient = Patient.objects.create(
        first_name="Amina",
        last_name="Hassan",
        date_of_birth=date(1992, 3, 14),
        sex="F",
    )
    return Visit.objects.create(patient=patient)


@pytest.fixture
def billed_visit(visit):
    charge(visit, Service.objects.get(code="CONS-GEN"))
    charge(visit, Service.objects.get(code="LAB-MPS"))
    return visit


# --- access ----------------------------------------------------------------


def test_the_till_requires_login(client, db):
    response = client.get(reverse("till"))

    assert response.status_code == 302
    assert reverse("login") in response.url


@pytest.mark.parametrize("role", [Role.TRIAGE_NURSE, Role.PHARMACIST, Role.RECEPTIONIST])
def test_the_till_is_closed_to_other_roles(roles, client, role):
    client.force_login(make_user(f"user-{role.value}", role))

    assert client.get(reverse("till")).status_code == 403


def test_the_finance_manager_reads_bills_but_cannot_take_payment(roles, billed_visit, client):
    manager = make_user("finance", Role.FINANCE_MANAGER)
    client.force_login(manager)
    invoice = billed_visit.invoice

    assert client.get(reverse("till")).status_code == 200
    assert client.get(reverse("invoice_detail", args=[invoice.pk])).status_code == 200

    line = invoice.lines.first()
    response = client.post(
        reverse("pay", args=[invoice.pk]),
        {"lines": [line.pk], "method": PaymentMethod.CASH},
    )

    assert response.status_code == 403
    line.refresh_from_db()
    assert line.status == LineStatus.UNPAID


# --- the till --------------------------------------------------------------


def test_the_till_lists_outstanding_bills(cashier, billed_visit, client):
    client.force_login(cashier)

    response = client.get(reverse("till"))

    assert response.status_code == 200
    assert billed_visit.invoice.number in response.content.decode()
    assert "800.00" in response.content.decode()


def test_a_settled_bill_drops_off_the_till(cashier, billed_visit, client):
    invoice = billed_visit.invoice
    take_payment(
        invoice=invoice,
        line_ids=list(invoice.lines.values_list("pk", flat=True)),
        method=PaymentMethod.CASH,
        received_by=cashier,
    )
    client.force_login(cashier)

    response = client.get(reverse("till"))

    assert invoice.number not in response.content.decode()


def test_the_till_searches_by_mrn_and_name(cashier, billed_visit, client):
    client.force_login(cashier)
    mrn = billed_visit.patient.mrn

    assert mrn in client.get(reverse("till"), {"q": "Amina"}).content.decode()
    assert mrn in client.get(reverse("till"), {"q": mrn}).content.decode()
    assert mrn not in client.get(reverse("till"), {"q": "Nobody"}).content.decode()


# --- taking payment --------------------------------------------------------


def test_paying_selected_lines_issues_a_receipt(cashier, billed_visit, client):
    client.force_login(cashier)
    invoice = billed_visit.invoice
    consultation = invoice.lines.get(service__code="CONS-GEN")

    response = client.post(
        reverse("pay", args=[invoice.pk]),
        {"lines": [consultation.pk], "method": PaymentMethod.MPESA, "reference": "QGH7X2K9LM"},
        follow=True,
    )

    assert response.status_code == 200
    consultation.refresh_from_db()
    assert consultation.status == LineStatus.PAID
    assert invoice.balance == Decimal("300.00")
    assert b"Official receipt" in response.content
    assert b"QGH7X2K9LM" in response.content


def test_payment_without_a_method_is_refused(cashier, billed_visit, client):
    client.force_login(cashier)
    invoice = billed_visit.invoice
    line = invoice.lines.first()

    response = client.post(
        reverse("pay", args=[invoice.pk]), {"lines": [line.pk], "method": ""}, follow=True
    )

    line.refresh_from_db()
    assert line.status == LineStatus.UNPAID
    assert b"Choose how the payment was made" in response.content


def test_payment_with_nothing_selected_is_refused(cashier, billed_visit, client):
    client.force_login(cashier)

    response = client.post(
        reverse("pay", args=[billed_visit.invoice.pk]),
        {"method": PaymentMethod.CASH},
        follow=True,
    )

    assert b"Select at least one charge" in response.content


def test_paying_a_line_twice_is_refused_with_a_message(cashier, billed_visit, client):
    """The second cashier through must be told, not silently take the money."""
    client.force_login(cashier)
    invoice = billed_visit.invoice
    line = invoice.lines.first()
    payload = {"lines": [line.pk], "method": PaymentMethod.CASH}

    client.post(reverse("pay", args=[invoice.pk]), payload)
    response = client.post(reverse("pay", args=[invoice.pk]), payload, follow=True)

    assert b"Already settled" in response.content
    assert invoice.payments.count() == 1


def test_a_get_cannot_take_payment(cashier, billed_visit, client):
    client.force_login(cashier)

    response = client.get(reverse("pay", args=[billed_visit.invoice.pk]))

    assert response.status_code == 405


# --- the receipt -----------------------------------------------------------


def test_the_receipt_shows_only_the_lines_it_paid_for(cashier, billed_visit, client):
    invoice = billed_visit.invoice
    consultation = invoice.lines.get(service__code="CONS-GEN")
    payment = take_payment(
        invoice=invoice,
        line_ids=[consultation.pk],
        method=PaymentMethod.CASH,
        received_by=cashier,
    )
    client.force_login(cashier)

    body = client.get(reverse("receipt", args=[payment.pk])).content.decode()

    assert "General consultation" in body
    assert "Malaria parasite smear" not in body
    assert payment.receipt_number in body
    assert "300.00" in body  # the balance still owing is stated on the receipt
