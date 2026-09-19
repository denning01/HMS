"""Create one demo account per role, for walking the workflow locally.

Development aid only — it refuses to run unless DEBUG is on, so it cannot create
known-password accounts on a production database.
"""

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Role, User

DEMO_PASSWORD = "demo-password-123"

DEMO_STAFF = [
    ("admin.demo", "Asha", "Njoroge", Role.ADMINISTRATOR),
    ("reception.demo", "Ruth", "Wanjiku", Role.RECEPTIONIST),
    ("triage.demo", "Tom", "Mwangi", Role.TRIAGE_NURSE),
    ("doctor.demo", "Dan", "Kiprop", Role.DOCTOR),
    ("lab.demo", "Lena", "Achieng", Role.LAB_TECHNICIAN),
    ("pharmacy.demo", "Peter", "Muturi", Role.PHARMACIST),
    ("procedure.demo", "Pauline", "Cherono", Role.PROCEDURE_NURSE),
    ("cashier.demo", "Caleb", "Omondi", Role.CASHIER),
    ("finance.demo", "Faith", "Mutiso", Role.FINANCE_MANAGER),
]


class Command(BaseCommand):
    help = "Create a demo staff account for each role (development only)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Refusing to run with DEBUG off — this creates accounts with a known password."
            )

        for username, first_name, last_name, role in DEMO_STAFF:
            group = Group.objects.filter(name=role.value).first()
            if group is None:
                raise CommandError(
                    f"Role group '{role.value}' is missing. Run `manage.py seed_roles` first."
                )

            user, created = User.objects.get_or_create(
                username=username,
                defaults={"first_name": first_name, "last_name": last_name},
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()

            user.groups.add(group)
            self.stdout.write(
                f"{'created' if created else 'exists '}  {username:<18} {role.label}"
            )

        self.stdout.write(
            self.style.SUCCESS(f"\nAll demo accounts use the password: {DEMO_PASSWORD}")
        )
