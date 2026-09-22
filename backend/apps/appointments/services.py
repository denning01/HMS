"""Booking an appointment, and the four things that can become of it."""

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.billing.services import charge_consultation
from apps.patients.models import OPEN_VISIT_STATUSES, Visit

from .models import Appointment, AppointmentStatus


class AppointmentError(Exception):
    """A refused booking operation, with a message fit to show the user."""


def book(*, patient, scheduled_for, department, clinician=None, reason="", created_by=None):
    """Put a patient in the diary."""
    if scheduled_for < timezone.now():
        raise AppointmentError("That time has already passed — book a later one.")

    clash = Appointment.objects.filter(
        patient=patient,
        scheduled_for=scheduled_for,
        status__in=[AppointmentStatus.BOOKED, AppointmentStatus.CONFIRMED],
    ).exists()
    if clash:
        raise AppointmentError(
            f"{patient.full_name} is already booked for that time."
        )

    return Appointment.objects.create(
        patient=patient,
        scheduled_for=scheduled_for,
        department=department,
        clinician=clinician,
        reason=reason,
        created_by=created_by,
    )


def confirm(appointment):
    """The patient has said they are coming."""
    if appointment.status != AppointmentStatus.BOOKED:
        raise AppointmentError(
            f"That appointment is {appointment.get_status_display().lower()} — "
            "only a booked one can be confirmed."
        )

    appointment.status = AppointmentStatus.CONFIRMED
    appointment.save(update_fields=["status"])
    return appointment


def cancel(appointment, *, note=""):
    if not appointment.is_open:
        raise AppointmentError(
            f"That appointment is already {appointment.get_status_display().lower()}."
        )

    appointment.status = AppointmentStatus.CANCELLED
    appointment.outcome_note = note
    appointment.save(update_fields=["status", "outcome_note"])
    return appointment


def mark_no_show(appointment, *, note=""):
    """Only once the time has passed. Before that the patient is simply not here yet."""
    if not appointment.is_open:
        raise AppointmentError(
            f"That appointment is already {appointment.get_status_display().lower()}."
        )
    if appointment.scheduled_for > timezone.now():
        raise AppointmentError(
            "That appointment has not come round yet — the patient is not late."
        )

    appointment.status = AppointmentStatus.NO_SHOW
    appointment.outcome_note = note
    appointment.save(update_fields=["status", "outcome_note"])
    return appointment


@transaction.atomic
def arrive(appointment, *, billing_mode=None, arrived_by=None):
    """The patient is here: open the visit the appointment was for.

    This is the point of booking ahead — the front desk does not retype a
    patient who is already in the diary, and the visit that opens carries the
    appointment with it.
    """
    if not appointment.is_open:
        raise AppointmentError(
            f"That appointment is {appointment.get_status_display().lower()} — "
            "it cannot be arrived."
        )

    patient = appointment.patient
    if patient.visits.filter(status__in=OPEN_VISIT_STATUSES).exists():
        raise AppointmentError(
            f"{patient.full_name} already has an open visit — continue that one."
        )

    fields = {"patient": patient, "created_by": arrived_by}
    if billing_mode:
        fields["billing_mode"] = billing_mode

    try:
        visit = Visit.objects.create(**fields)
    except IntegrityError:
        raise AppointmentError(
            f"{patient.full_name} already has an open visit — continue that one."
        ) from None

    charge_consultation(visit, ordered_by=arrived_by)

    appointment.visit = visit
    appointment.status = AppointmentStatus.ARRIVED
    appointment.save(update_fields=["visit", "status"])

    return appointment, visit
