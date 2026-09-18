"""Authentication views and the post-login dashboard router."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Role

# What each role sees on its dashboard. The modules are placeholders until the
# corresponding phase is built; the labels come from the specification's matrix.
DASHBOARD_MODULES = {
    Role.ADMINISTRATOR: [
        ("Users & roles", "Create staff accounts and assign roles"),
        ("Price lists", "Consultation, test, drug and procedure pricing"),
        ("Reports", "Revenue and profit across every department"),
    ],
    Role.RECEPTIONIST: [
        ("Registration", "Find or register a patient and start a visit"),
        ("Appointments", "Book, confirm and track upcoming visits"),
    ],
    Role.TRIAGE_NURSE: [
        ("Triage queue", "Patients waiting for vitals"),
    ],
    Role.DOCTOR: [
        ("Consultation queue", "Patients ready to be seen"),
        ("Results", "Lab results returned for review"),
    ],
    Role.LAB_TECHNICIAN: [
        ("Lab worklist", "Paid test orders awaiting processing"),
        ("Test catalogue", "Available tests and sample types"),
    ],
    Role.PHARMACIST: [
        ("Dispensing queue", "Paid prescriptions awaiting dispensing"),
        ("Stock", "Stock in, write-offs, low-stock and expiry alerts"),
    ],
    Role.PROCEDURE_NURSE: [
        ("Procedure queue", "Paid procedure orders awaiting action"),
    ],
    Role.CASHIER: [
        ("Point of sale", "Take payment and issue receipts"),
        ("Today's invoices", "Outstanding balances and daily total"),
    ],
    Role.FINANCE_MANAGER: [
        ("Revenue", "Collections by date, department and cashier"),
        ("Profit per day", "Revenue against recorded costs"),
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
