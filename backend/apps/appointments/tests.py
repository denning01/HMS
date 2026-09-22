"""The diary: booking, and the four things that become of an appointment."""

from datetime import date, timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.appointments.models import AppointmentStatus
from apps.appointments.services import (
    AppointmentError,
    arrive,
    book,
    cancel,
    confirm,
    mark_no_show,
)
from apps.patients.models import Patient, Visit, VisitStatus


@pytest.fixture
def catalogue(db):
    call_command("seed_services")


@pytest.fixture
def patient(catalogue):
    return Patient.objects.create(
        first_name="Amina", last_name="Hassan", date_of_birth=date(1992, 3, 14), sex="F"
    )


def tomorrow():
    return timezone.now() + timedelta(days=1)


def make(patient, when=None, **kwargs):
    return book(
        patient=patient,
        scheduled_for=when or tomorrow(),
        department="consultation",
        **kwargs,
    )


def test_booking_puts_the_patient_in_the_diary(patient):
    appointment = make(patient, reason="Review after treatment")

    assert appointment.status == AppointmentStatus.BOOKED
    assert appointment.is_open


def test_nothing_is_booked_in_the_past(patient):
    with pytest.raises(AppointmentError, match="already passed"):
        make(patient, when=timezone.now() - timedelta(hours=1))


def test_the_same_patient_is_not_booked_twice_into_one_slot(patient):
    when = tomorrow()
    make(patient, when=when)

    with pytest.raises(AppointmentError, match="already booked"):
        make(patient, when=when)


def test_a_cancelled_slot_can_be_booked_again(patient):
    when = tomorrow()
    cancel(make(patient, when=when))

    assert make(patient, when=when).status == AppointmentStatus.BOOKED


def test_only_a_booked_appointment_is_confirmed(patient):
    appointment = confirm(make(patient))
    assert appointment.status == AppointmentStatus.CONFIRMED

    with pytest.raises(AppointmentError, match="only a booked one"):
        confirm(appointment)


def test_a_patient_is_not_a_no_show_before_their_time(patient):
    appointment = make(patient)

    with pytest.raises(AppointmentError, match="not late"):
        mark_no_show(appointment)


def test_a_missed_appointment_is_recorded_once_the_time_has_passed(patient):
    appointment = make(patient)
    # The slot comes and goes.
    appointment.scheduled_for = timezone.now() - timedelta(minutes=30)
    appointment.save(update_fields=["scheduled_for"])

    mark_no_show(appointment, note="Phone off")

    assert appointment.status == AppointmentStatus.NO_SHOW
    assert appointment.outcome_note == "Phone off"


def test_arriving_opens_the_visit_and_bills_the_consultation(patient):
    appointment = confirm(make(patient))

    appointment, visit = arrive(appointment)

    assert appointment.status == AppointmentStatus.ARRIVED
    assert appointment.visit == visit
    assert visit.status == VisitStatus.AWAITING_TRIAGE
    # The visit is billed exactly as a walk-in would be.
    assert visit.invoice.total > 0


def test_a_patient_already_in_the_building_is_not_admitted_twice(patient):
    Visit.objects.create(patient=patient)
    appointment = make(patient)

    with pytest.raises(AppointmentError, match="already has an open visit"):
        arrive(appointment)


def test_a_cancelled_appointment_cannot_be_arrived(patient):
    appointment = cancel(make(patient), note="Patient rang to cancel")

    with pytest.raises(AppointmentError, match="cannot be arrived"):
        arrive(appointment)


def test_an_appointment_is_only_cancelled_once(patient):
    appointment = cancel(make(patient))

    with pytest.raises(AppointmentError, match="already cancelled"):
        cancel(appointment)


def test_an_overdue_appointment_is_the_desks_chase_list(patient):
    appointment = make(patient)
    appointment.scheduled_for = timezone.now() - timedelta(minutes=10)
    appointment.save(update_fields=["scheduled_for"])

    assert appointment.is_overdue is True
    confirm(appointment)
    assert appointment.is_overdue is True
    cancel(appointment)
    assert appointment.is_overdue is False
