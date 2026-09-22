"""Appointments: a patient expected at a time, and what became of it.

Booked either at the front desk for a future date, or by the doctor at the end
of a consultation as a follow-up. When the patient arrives it stops being an
appointment and becomes a visit — the appointment keeps the link, so the diary
can show what actually happened rather than only what was intended.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class AppointmentStatus(models.TextChoices):
    BOOKED = "booked", "Booked"
    CONFIRMED = "confirmed", "Confirmed"
    ARRIVED = "arrived", "Arrived"
    CANCELLED = "cancelled", "Cancelled"
    NO_SHOW = "no_show", "No-show"


OPEN_APPOINTMENT_STATUSES = [AppointmentStatus.BOOKED, AppointmentStatus.CONFIRMED]


class Appointment(models.Model):
    """One expected attendance."""

    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.PROTECT, related_name="appointments"
    )
    scheduled_for = models.DateTimeField()

    department = models.CharField(
        max_length=20,
        help_text="Which part of the clinic the patient is coming to.",
    )
    clinician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="appointments",
        null=True,
        blank=True,
        help_text="The named member of staff, where the clinic books by person.",
    )
    reason = models.CharField(max_length=200, blank=True)

    status = models.CharField(
        max_length=20, choices=AppointmentStatus.choices, default=AppointmentStatus.BOOKED
    )
    outcome_note = models.CharField(
        max_length=200,
        blank=True,
        help_text="Why it was cancelled, or anything said when it was missed.",
    )

    # Set when the patient arrives. One appointment becomes one visit.
    visit = models.OneToOneField(
        "patients.Visit",
        on_delete=models.PROTECT,
        related_name="appointment",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="appointments_booked",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["scheduled_for"]
        indexes = [
            models.Index(fields=["scheduled_for", "status"]),
            models.Index(fields=["patient", "scheduled_for"]),
        ]

    def __str__(self):
        return f"{self.patient.mrn} at {timezone.localtime(self.scheduled_for):%d %b %H:%M}"

    @property
    def is_open(self):
        return self.status in set(OPEN_APPOINTMENT_STATUSES)

    @property
    def is_overdue(self):
        """Still expected, and the time has passed — what the front desk chases."""
        return self.is_open and self.scheduled_for < timezone.now()
