"""Authentication views and the post-login dashboard router."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Role

# What each role sees on its dashboard, as (label, description, url_name).
# A url_name of None means that screen is not built yet; the labels come from
# the specification's permissions matrix.
DASHBOARD_MODULES = {
    Role.ADMINISTRATOR: [
        ("Users & roles", "Create staff accounts and assign roles", None),
        ("Point of sale", "Take payment and issue receipts", "till"),
        ("Price lists", "Consultation, test, drug and procedure pricing", None),
        ("Reports", "Revenue and profit across every department", None),
    ],
    Role.RECEPTIONIST: [
        ("Registration", "Find or register a patient and start a visit", "registration_home"),
        ("Appointments", "Book, confirm and track upcoming visits", None),
    ],
    Role.TRIAGE_NURSE: [
        ("Triage queue", "Patients waiting for vitals", "triage_queue"),
    ],
    Role.DOCTOR: [
        ("Consultation queue", "Patients ready to be seen", None),
        ("Results", "Lab results returned for review", None),
    ],
    Role.LAB_TECHNICIAN: [
        ("Lab worklist", "Paid test orders awaiting processing", None),
        ("Test catalogue", "Available tests and sample types", None),
    ],
    Role.PHARMACIST: [
        ("Dispensing queue", "Paid prescriptions awaiting dispensing", None),
        ("Stock", "Stock in, write-offs, low-stock and expiry alerts", None),
    ],
    Role.PROCEDURE_NURSE: [
        ("Procedure queue", "Paid procedure orders awaiting action", None),
    ],
    Role.CASHIER: [
        ("Point of sale", "Take payment and issue receipts", "till"),
    ],
    Role.FINANCE_MANAGER: [
        ("Bills", "Every open bill and what is outstanding", "till"),
        ("Revenue", "Collections by date, department and cashier", None),
        ("Profit per day", "Revenue against recorded costs", None),
    ],
}


@login_required
def dashboard(request):
    """Land a user on the view matching their role.

    A user holding several roles lands on the highest-priority one and can see
    the rest listed, rather than being locked into a single home screen.
    """
    primary = request.user.primary_role
    modules = DASHBOARD_MODULES.get(primary, []) if primary else []

    other_roles = sorted(
        name for name in request.user.role_names
        if not primary or name != primary.value
    )

    return render(
        request,
        "accounts/dashboard.html",
        {
            "primary_role": primary,
            "primary_role_label": primary.label if primary else None,
            "modules": modules,
            "other_roles": other_roles,
        },
    )
