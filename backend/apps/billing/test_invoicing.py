"""Tests for the bill: charges, snapshots, totals, payment and gating."""

from datetime import date
from decimal import Decimal

import pytest
from django.core.management import call_command

from apps.accounts.models import Role, User
from apps.billing.models import (
    Invoice,
    InvoiceLine,
    LineStatus,
    PaymentMethod,
    Service,
)
from apps.billing.services import (
    BillingError,
    cancel_line,
    charge,
    charge_consultation,
    invoice_for,
    take_payment,
)
from apps.patients.models import BillingMode, Patient, Visit


@pytest.fixture
def services(db):
    call_command("seed_services")


@pytest.fixture
def cashier(db):
    call_command("seed_roles")
    from django.contrib.auth.models import Group

    user = User.objects.create_user(username="till", password="pw-for-tests-only")
    user.groups.add(Group.objects.get(name=Role.CASHIER.value))
    return user


@pytest.fixture
def visit(db):
    patient = Patient.objects.create(
        first_name="Amina",
        last_name="Hassan",
        date_of_birth=date(1992, 3, 14),
        sex="F",
    )
    return Visit.objects.create(patient=patient)


@pytest.fixture
def consultation(services):
    return Service.objects.get(code="CONS-GEN")


@pytest.fixture
def malaria_test(services):
    return Service.objects.get(code="LAB-MPS")


# --- the bill itself -------------------------------------------------------


def test_a_visit_gets_one_invoice_however_many_departments_charge(visit, consultation, malaria_test):
    charge(visit, consultation)
    charge(visit, malaria_test)

    assert Invoice.objects.count() == 1
    assert visit.invoice.lines.count() == 2


def test_invoice_number_is_assigned_and_stable(visit, consultation):
    charge(visit, consultation)
    invoice = visit.invoice

    assert invoice.number.startswith("INV")
    number = invoice.number
    invoice.save()
    invoice.refresh_from_db()
    assert invoice.number == number


def test_a_visit_with_no_charges_has_no_invoice(visit):
    """An empty bill is noise on the cashier's screen, so it is not created."""
    assert not Invoice.objects.filter(visit=visit).exists()


# --- price snapshots -------------------------------------------------------


def test_the_line_copies_the_price_it_was_raised_at(visit, consultation):
    line = charge(visit, consultation)

    assert line.unit_price == Decimal("500.00")
    assert line.description == "General consultation"


def test_changing_the_price_list_does_not_rewrite_an_existing_charge(visit, consultation):
    line = charge(visit, consultation)

    consultation.unit_price = Decimal("900.00")
    consultation.save()

    line.refresh_from_db()
    assert line.unit_price == Decimal("500.00")
    assert visit.invoice.total == Decimal("500.00")


def test_renaming_a_service_does_not_make_an_old_bill_unreadable(visit, consultation):
    line = charge(visit, consultation)

    consultation.name = "Outpatient attendance"
    consultation.save()

    line.refresh_from_db()
    assert line.description == "General consultation"


# --- totals ----------------------------------------------------------------


def test_quantity_multiplies_the_line(visit, services):
    paracetamol = Service.objects.get(code="PHA-PARA")

    line = charge(visit, paracetamol, quantity=12)

    assert line.line_total == Decimal("120.00")


def test_totals_add_up_across_departments(visit, consultation, malaria_test):
    charge(visit, consultation)
    charge(visit, malaria_test)

    assert visit.invoice.total == Decimal("800.00")
    assert visit.invoice.balance == Decimal("800.00")
    assert visit.invoice.paid_total == Decimal("0.00")


def test_a_quantity_below_one_is_refused(visit, consultation):
    with pytest.raises(BillingError):
        charge(visit, consultation, quantity=0)


# --- payment ---------------------------------------------------------------


def test_paying_a_line_settles_it_and_issues_a_receipt(visit, consultation, cashier):
    line = charge(visit, consultation)
    invoice = visit.invoice

    payment = take_payment(
        invoice=invoice,
        line_ids=[line.pk],
        method=PaymentMethod.MPESA,
        received_by=cashier,
        reference="QGH7X2K9LM",
    )

    line.refresh_from_db()
    assert line.status == LineStatus.PAID
    assert line.payment == payment
    assert line.paid_at is not None
    assert payment.amount == Decimal("500.00")
    assert payment.receipt_number.startswith("RCT")
    assert invoice.balance == Decimal("0.00")
    assert invoice.is_settled


def test_the_amount_is_computed_from_the_lines_not_supplied(visit, consultation, malaria_test, cashier):
    """The cashier cannot enter an amount that disagrees with the charges."""
    first = charge(visit, consultation)
    second = charge(visit, malaria_test)

    payment = take_payment(
        invoice=visit.invoice,
        line_ids=[first.pk, second.pk],
        method=PaymentMethod.CASH,
        received_by=cashier,
    )

    assert payment.amount == Decimal("800.00")


def test_paying_some_lines_leaves_the_rest_outstanding(visit, consultation, malaria_test, cashier):
    line = charge(visit, consultation)
    charge(visit, malaria_test)

    take_payment(
        invoice=visit.invoice,
        line_ids=[line.pk],
        method=PaymentMethod.CASH,
        received_by=cashier,
    )

    invoice = visit.invoice
    assert invoice.paid_total == Decimal("500.00")
    assert invoice.balance == Decimal("300.00")
    assert invoice.status_label == "Part paid"


def test_a_line_cannot_be_paid_twice(visit, consultation, cashier):
    """Two cashiers with the same bill open must not both take the money."""
    line = charge(visit, consultation)
    take_payment(
        invoice=visit.invoice,
        line_ids=[line.pk],
        method=PaymentMethod.CASH,
        received_by=cashier,
    )

    with pytest.raises(BillingError, match="Already settled"):
        take_payment(
            invoice=visit.invoice,
            line_ids=[line.pk],
            method=PaymentMethod.CASH,
            received_by=cashier,
        )


def test_paying_nothing_is_refused(visit, consultation, cashier):
    charge(visit, consultation)

    with pytest.raises(BillingError, match="at least one"):
        take_payment(
            invoice=visit.invoice,
            line_ids=[],
            method=PaymentMethod.CASH,
            received_by=cashier,
        )


def test_a_line_from_another_bill_cannot_be_paid_here(visit, consultation, malaria_test, cashier):
    charge(visit, consultation)

    other_patient = Patient.objects.create(
        first_name="Brian", last_name="Otieno", date_of_birth=date(1990, 5, 2), sex="M"
    )
    other_visit = Visit.objects.create(patient=other_patient)
    other_line = charge(other_visit, malaria_test)

    with pytest.raises(BillingError):
        take_payment(
            invoice=visit.invoice,
            line_ids=[other_line.pk],
            method=PaymentMethod.CASH,
            received_by=cashier,
        )


# --- gating: what the departments are allowed to act on --------------------


def test_pay_per_service_holds_work_until_the_line_is_paid(visit, malaria_test, cashier):
    line = charge(visit, malaria_test)

    assert not line.is_cleared

    take_payment(
        invoice=visit.invoice,
        line_ids=[line.pk],
        method=PaymentMethod.CASH,
        received_by=cashier,
    )

    line.refresh_from_db()
    assert line.is_cleared


def test_consolidated_billing_never_holds_work_up(visit, malaria_test):
    """Staff and corporate accounts settle at the end, by arrangement."""
    visit.billing_mode = BillingMode.CONSOLIDATED
    visit.save(update_fields=["billing_mode"])

    line = charge(visit, malaria_test)

    assert line.status == LineStatus.UNPAID
    assert line.is_cleared
    assert visit.invoice.balance == Decimal("300.00")


# --- cancelling ------------------------------------------------------------


def test_a_charge_raised_in_error_can_be_voided(visit, malaria_test):
    line = charge(visit, malaria_test)

    cancel_line(line)

    line.refresh_from_db()
    assert line.status == LineStatus.CANCELLED
    assert not line.is_cleared
    assert visit.invoice.total == Decimal("0.00")


def test_a_paid_charge_cannot_be_voided(visit, malaria_test, cashier):
    line = charge(visit, malaria_test)
    take_payment(
        invoice=visit.invoice,
        line_ids=[line.pk],
        method=PaymentMethod.CASH,
        received_by=cashier,
    )
    line.refresh_from_db()

    with pytest.raises(BillingError, match="refund"):
        cancel_line(line)


# --- the consultation charge that opens every bill -------------------------


def test_starting_a_visit_raises_the_consultation_charge(visit, services):
    charge_consultation(visit)

    assert visit.invoice.total == Decimal("500.00")
    assert visit.invoice.lines.get().description == "General consultation"


def test_registration_still_works_with_an_unseeded_price_list(visit, db):
    """A missing catalogue must not stop the clerk admitting a patient."""
    assert charge_consultation(visit) is None
    assert not Invoice.objects.filter(visit=visit).exists()
