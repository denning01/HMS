"""Registration: find an existing patient or create one, then start a visit."""

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import Role
from apps.accounts.permissions import role_required

from .forms import PatientForm
from .models import Patient, Visit, VisitStatus

REGISTRATION_ROLES = (Role.RECEPTIONIST, Role.ADMINISTRATOR)

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


@role_required(*REGISTRATION_ROLES)
def registration_home(request):
    """Search-before-create: the clerk must look first so returns aren't duplicated."""
    return render(
        request,
        "patients/registration_home.html",
        {"open_visits": Visit.objects.filter(
            status__in=[VisitStatus.AWAITING_TRIAGE, VisitStatus.AWAITING_CONSULTATION]
        ).select_related("patient")[:10]},
    )


@role_required(*REGISTRATION_ROLES)
def patient_search(request):
    """HTMX partial: live results as the clerk types."""
    term = request.GET.get("q", "")
    return render(
        request,
        "patients/_search_results.html",
        {"patients": search_patients(term), "term": term.strip()},
    )


@role_required(*REGISTRATION_ROLES)
def patient_create(request):
    if request.method == "POST":
        form = PatientForm(request.POST)
        if form.is_valid():
            patient = form.save(commit=False)
            patient.created_by = request.user
            patient.save()
            messages.success(
                request, f"Registered {patient.full_name} as {patient.mrn}."
            )
            return redirect("patient_detail", pk=patient.pk)
    else:
        # Prefill the name typed into the search box, so it isn't keyed twice.
        form = PatientForm(initial={"first_name": request.GET.get("q", "").strip()})

    return render(request, "patients/patient_form.html", {"form": form})


@role_required(*REGISTRATION_ROLES, Role.TRIAGE_NURSE, Role.DOCTOR, Role.CASHIER)
def patient_detail(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    visits = patient.visits.select_related("created_by")

    return render(
        request,
        "patients/patient_detail.html",
        {
            "patient": patient,
            "visits": visits,
            "open_visit": visits.filter(
                status__in=[
                    VisitStatus.AWAITING_TRIAGE,
                    VisitStatus.AWAITING_CONSULTATION,
                    VisitStatus.IN_CONSULTATION,
                ]
            ).first(),
            "can_start_visit": request.user.is_superuser
            or any(request.user.has_role(r) for r in REGISTRATION_ROLES),
        },
    )


@require_POST
@role_required(*REGISTRATION_ROLES)
def start_visit(request, pk):
    """Open a visit and send the patient to triage.

    Refuses a second open visit for the same patient: two open visits would split
    one attendance's charges across two bills.
    """
    patient = get_object_or_404(Patient, pk=pk)

    existing = patient.visits.exclude(
        status__in=[VisitStatus.COMPLETED, VisitStatus.CANCELLED]
    ).first()
    if existing:
        messages.warning(
            request,
            f"{patient.full_name} already has an open visit — continue that one.",
        )
        return redirect("patient_detail", pk=patient.pk)

    billing_mode = request.POST.get("billing_mode")
    visit = Visit(patient=patient, created_by=request.user)
    if billing_mode:
        visit.billing_mode = billing_mode
    visit.save()

    messages.success(request, f"Visit started for {patient.full_name}. Sent to triage.")
    return redirect("patient_detail", pk=patient.pk)
