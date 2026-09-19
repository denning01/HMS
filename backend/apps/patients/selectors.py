"""Reads of the patient register that more than one caller needs."""

from django.db.models import Q

from .models import Patient

SEARCH_RESULT_LIMIT = 20


def search_patients(term):
    """Match on the things a clerk actually has to hand: name, phone, MRN, ID."""
    term = term.strip()
    if not term:
        return Patient.objects.none()

    return Patient.objects.filter(
        Q(first_name__icontains=term)
        | Q(middle_name__icontains=term)
        | Q(last_name__icontains=term)
        | Q(phone_number__icontains=term)
        | Q(mrn__icontains=term)
        | Q(national_id__icontains=term)
    )[:SEARCH_RESULT_LIMIT]
