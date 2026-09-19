"""Tests for collections reporting."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.billing import reports
from apps.billing.models import Payment, PaymentMethod, Service
from apps.billing.services import charge, take_payment
from apps.patients.models import Patient, Visit


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
    user = make_user("till", Role.CASHIER)
    user.first_name, user.last_name = "Caleb", "Omondi"
    user.save()
    return user


def make_visit(first_name="Amina", last_name="Hassan"):
    patient = Patient.objects.create(
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date(1992, 3, 14),
        sex="F",
    )
    return Visit.objects.create(patient=patient)


def pay_for(visit, codes, cashier, method=PaymentMethod.CASH):
    lines = [charge(visit, Service.objects.get(code=code)) for code in codes]
    return take_payment(
        invoice=visit.invoice,
        line_ids=[line.pk for line in lines],
        method=method,
        received_by=cashier,
    )


# --- the numbers -----------------------------------------------------------


def test_total_is_what_was_received_today(cashier):
    pay_for(make_visit(), ["CONS-GEN", "LAB-MPS"], cashier)

    assert reports.total_collected(timezone.localdate()) == Decimal("800.00")


def test_yesterdays_takings_are_not_counted_today(cashier):
    payment = pay_for(make_visit(), ["CONS-GEN"], cashier)
    Payment.objects.filter(pk=payment.pk).update(
        received_at=timezone.now() - timedelta(days=1)
    )

    today = timezone.localdate()
    assert reports.total_collected(today) == Decimal("0.00")
    assert reports.total_collected(today - timedelta(days=1)) == Decimal("500.00")


def test_a_day_with_no_takings_reports_zero_not_none(cashier):
    """The template formats this, so it must be a number even when empty."""
    assert reports.total_collected(timezone.localdate()) == Decimal("0.00")


def test_split_by_method_covers_every_method(cashier):
    pay_for(make_visit("Amina"), ["CONS-GEN"], cashier, PaymentMethod.MPESA)
    pay_for(make_visit("Brian"), ["LAB-MPS"], cashier, PaymentMethod.CASH)

    rows = {row["key"]: row["total"] for row in reports.by_method(timezone.localdate())}

    assert rows[PaymentMethod.MPESA] == Decimal("500.00")
    assert rows[PaymentMethod.CASH] == Decimal("300.00")
    # Methods with nothing taken are still listed, so the reconciliation is complete.
    assert rows[PaymentMethod.CARD] == Decimal("0.00")


def test_one_receipt_splits_across_the_departments_it_paid_for(cashier):
    """A single payment routinely covers several departments; each is credited."""
    pay_for(make_visit(), ["CONS-GEN", "LAB-MPS", "PRO-INJ"], cashier)

    rows = {row["key"]: row["total"] for row in reports.by_department(timezone.localdate())}

    assert rows["consultation"] == Decimal("500.00")
    assert rows["laboratory"] == Decimal("300.00")
    assert rows["procedure"] == Decimal("200.00")


def test_department_split_respects_quantity(cashier):
    visit = make_visit()
    line = charge(visit, Service.objects.get(code="PHA-PARA"), quantity=12)
    take_payment(
        invoice=visit.invoice,
        line_ids=[line.pk],
        method=PaymentMethod.CASH,
        received_by=cashier,
    )

    rows = {row["key"]: row["total"] for row in reports.by_department(timezone.localdate())}

    assert rows["pharmacy"] == Decimal("120.00")


def test_takings_are_attributed_to_the_cashier_who_took_them(cashier, roles):
    other = make_user("till2", Role.CASHIER)
    other.first_name, other.last_name = "Ruth", "Wanjiku"
    other.save()

    pay_for(make_visit("Amina"), ["CONS-GEN"], cashier)
    pay_for(make_visit("Brian"), ["LAB-MPS"], other)

    rows = {row["name"]: row["total"] for row in reports.by_cashier(timezone.localdate())}

    assert rows["Caleb Omondi"] == Decimal("500.00")
    assert rows["Ruth Wanjiku"] == Decimal("300.00")


def test_outstanding_counts_unpaid_charges_only(cashier):
    visit = make_visit()
    charge(visit, Service.objects.get(code="CONS-GEN"))
    paid = charge(visit, Service.objects.get(code="LAB-MPS"))
    take_payment(
        invoice=visit.invoice,
        line_ids=[paid.pk],
        method=PaymentMethod.CASH,
        received_by=cashier,
    )

    assert reports.outstanding_total() == Decimal("500.00")
