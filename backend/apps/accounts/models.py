"""User accounts and the role system.

Roles are Django Groups, not a field on the user: the specification requires one
person to be able to hold several roles at once (a small clinic's receptionist may
also handle appointments and the till). Permissions hang off those Groups, so the
permissions matrix in the specification is expressed as group membership.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    """The nine roles from the specification. The value is the Group name."""

    ADMINISTRATOR = "Administrator", "System Administrator"
    RECEPTIONIST = "Receptionist", "Receptionist / Registration Clerk"
    TRIAGE_NURSE = "Triage Nurse", "Triage Nurse"
    DOCTOR = "Doctor", "Doctor / Clinician"
    LAB_TECHNICIAN = "Lab Technician", "Lab Technician"
    PHARMACIST = "Pharmacist", "Pharmacist"
    PROCEDURE_NURSE = "Procedure Nurse", "Procedure / Injection Room Nurse"
    CASHIER = "Cashier", "Cashier / Billing Officer"
    FINANCE_MANAGER = "Finance Manager", "Finance Manager"


# When a user holds several roles, the first match here decides which dashboard
# they land on after login. Ordered by breadth of responsibility.
DASHBOARD_PRIORITY = [
    Role.ADMINISTRATOR,
    Role.DOCTOR,
    Role.FINANCE_MANAGER,
    Role.CASHIER,
    Role.PHARMACIST,
    Role.LAB_TECHNICIAN,
    Role.PROCEDURE_NURSE,
    Role.TRIAGE_NURSE,
    Role.RECEPTIONIST,
]


class User(AbstractUser):
    """Staff account.

    Every clinical and financial record is stamped with the acting user, so this
    model is referenced widely from the modules built later.
    """

    phone_number = models.CharField(max_length=20, blank=True)
    staff_id = models.CharField(
        max_length=30,
        blank=True,
        help_text="Internal staff/payroll number, if the clinic uses one.",
    )

    class Meta:
        ordering = ["first_name", "last_name", "username"]

    def __str__(self):
        full_name = self.get_full_name()
        return full_name or self.username

    @property
    def role_names(self):
        """Every role this user holds, as a set of Group names."""
        return set(self.groups.values_list("name", flat=True))

    def has_role(self, role):
        """True if the user holds the given role (superusers hold all of them)."""
        if self.is_superuser:
            return True
        return str(role) in self.role_names

    @property
    def primary_role(self):
        """The role that decides which dashboard this user lands on, or None."""
        held = self.role_names
        if self.is_superuser:
            return Role.ADMINISTRATOR
        for role in DASHBOARD_PRIORITY:
            if role.value in held:
                return role
        return None
