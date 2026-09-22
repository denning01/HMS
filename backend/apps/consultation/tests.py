"""Closing a visit: the two things that must not be left hanging."""

from datetime import date

import pytest
from django.core.management import call_command

from apps.billing.models import Service
from apps.billing.services import charge_consultation, take_payment
from apps.consultation.models import Consultation
from apps.consultation.services import ConsultationError, close_visit, open_note
from apps.orders.services import complete, place_order
from apps.patients.models import Patient, Visit, VisitStatus


@pytest.fixture
def catalogue(db):
    call_command("seed_services")


@pytest.fixture
def visit(catalogue):
    patient = Patient.objects.create(
        first_name="Joseph", last_name="Kariuki", date_of_birth=date(1975, 6, 2), sex="M"
    )
    visit = Visit.objects.create(patient=patient, status=VisitStatus.AWAITING_CONSULTATION)
    charge_consultation(visit)
    return visit


def settle(visit):
    invoice = visit.invoice
    unpaid = [line.pk for line in invoice.lines.filter(status="unpaid")]
    take_payment(invoice=invoice, line_ids=unpaid, method="cash", received_by=None)


def test_writing_the_note_is_what_starts_the_consultation(visit):
    note, created = open_note(visit)

    visit.refresh_from_db()
    assert created is True
    assert visit.status == VisitStatus.IN_CONSULTATION
    assert Consultation.objects.count() == 1


def test_the_note_is_opened_once_and_added_to(visit):
    first, _ = open_note(visit)
    second, created = open_note(visit)

    assert created is False
    assert first.pk == second.pk


def test_a_visit_cannot_be_closed_with_work_still_outstanding(visit):
    """A paid-for test the lab has not run yet is the clearest case: the money is
    in, so only the work is outstanding — and closing would take the order off
    the lab's worklist with the patient still owed the result."""
    order = place_order(visit=visit, service=Service.objects.get(code="LAB-MPS"))
    settle(visit)

    with pytest.raises(ConsultationError, match="Still outstanding"):
        close_visit(visit)

    complete(order)
    close_visit(visit)
    assert visit.status == VisitStatus.COMPLETED


def test_a_visit_cannot_be_closed_over_money_still_owing(visit):
    # Closing would drop the bill off the till, where it is the only thing the
    # cashier would ever have seen.
    with pytest.raises(ConsultationError, match="still owing"):
        close_visit(visit)

    settle(visit)
    close_visit(visit)

    visit.refresh_from_db()
    assert visit.status == VisitStatus.COMPLETED
    assert visit.closed_at is not None


def test_a_closed_visit_cannot_be_closed_twice(visit):
    settle(visit)
    close_visit(visit)

    with pytest.raises(ConsultationError, match="already closed"):
        close_visit(visit)


def test_a_visit_that_incurred_nothing_closes_cleanly(catalogue):
    # No consultation charge at all — the price list was empty when it opened.
    patient = Patient.objects.create(
        first_name="Grace", last_name="Wambui", date_of_birth=date(1999, 9, 9), sex="F"
    )
    visit = Visit.objects.create(patient=patient)

    close_visit(visit)

    assert visit.status == VisitStatus.COMPLETED
