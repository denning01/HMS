"""Reads of the diary."""

from django.db.models import Q
from django.utils import timezone

from .models import Appointment, OPEN_APPOINTMENT_STATUSES

SEARCH_RESULT_LIMIT = 50


def diary(day, *, term=""):
    """Everything in the book for one day, whatever became of it."""
    appointments = (
        Appointment.objects.filter(scheduled_for__date=day)
        .select_related("patient", "clinician", "visit")
        .order_by("scheduled_for")
    )
    return _searched(appointments, term)[:SEARCH_RESULT_LIMIT]


def upcoming(*, term="", limit=SEARCH_RESULT_LIMIT):
    """Still expected, from now on — what the desk works through after today."""
    appointments = (
        Appointment.objects.filter(
            status__in=OPEN_APPOINTMENT_STATUSES, scheduled_for__gte=timezone.now()
        )
        .select_related("patient", "clinician", "visit")
        .order_by("scheduled_for")
    )
    return _searched(appointments, term)[:limit]


def overdue():
    """Expected before now and still not here. The desk's chase list."""
    return (
        Appointment.objects.filter(
            status__in=OPEN_APPOINTMENT_STATUSES, scheduled_for__lt=timezone.now()
        )
        .select_related("patient", "clinician", "visit")
        .order_by("scheduled_for")[:SEARCH_RESULT_LIMIT]
    )


def _searched(queryset, term):
    term = term.strip()
    if not term:
        return queryset
    return queryset.filter(
        Q(patient__first_name__icontains=term)
        | Q(patient__last_name__icontains=term)
        | Q(patient__mrn__icontains=term)
        | Q(patient__phone_number__icontains=term)
    )
