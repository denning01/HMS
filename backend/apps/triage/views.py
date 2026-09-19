"""Triage: the queue of registered patients and the vitals form."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import Role
from apps.accounts.permissions import role_required
from apps.patients.models import Visit, VisitStatus

from .forms import VitalsForm

TRIAGE_ROLES = (Role.TRIAGE_NURSE, Role.ADMINISTRATOR)


@role_required(*TRIAGE_ROLES)
def triage_queue(request):
    """Visits waiting for vitals, oldest first so nobody is left behind."""
    waiting = (
        Visit.objects.filter(status=VisitStatus.AWAITING_TRIAGE)
        .select_related("patient")
        .order_by("started_at")
    )
    return render(request, "triage/queue.html", {"visits": waiting})


@role_required(*TRIAGE_ROLES)
def record_vitals(request, visit_id):
    """Record vitals against an open visit and move it on to consultation."""
    visit = get_object_or_404(
        Visit.objects.select_related("patient"), pk=visit_id
    )

    if not visit.is_open:
        messages.warning(request, "That visit is already closed.")
        return redirect("triage_queue")

    if hasattr(visit, "vitals"):
        messages.info(
            request,
            f"Vitals were already recorded for {visit.patient.full_name}.",
        )
        return redirect("triage_queue")

    if request.method == "POST":
        form = VitalsForm(request.POST)
        if form.is_valid():
            vitals = form.save(commit=False)
            vitals.visit = visit
            vitals.recorded_by = request.user
            vitals.save()

            # Out-of-range readings prioritise this visit in the doctor's queue.
            visit.is_urgent = vitals.is_urgent
            visit.status = VisitStatus.AWAITING_CONSULTATION
            visit.save(update_fields=["is_urgent", "status"])

            if vitals.is_urgent:
                messages.warning(
                    request,
                    "Flagged urgent — "
                    + ", ".join(vitals.urgency_reasons())
                    + ". Sent to consultation.",
                )
            else:
                messages.success(
                    request,
                    f"Vitals recorded for {visit.patient.full_name}. Sent to consultation.",
                )
            return redirect("triage_queue")
    else:
        form = VitalsForm()

    return render(request, "triage/vitals_form.html", {"form": form, "visit": visit})
