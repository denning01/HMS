"""Seed a starting price list.

Idempotent on code: it creates services that are missing and leaves the price of
anything already there alone, so running it on a later deploy never overwrites
prices the clinic has since set for itself.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.billing.models import Department, Service

# (code, name, department, price in KES). Indicative starting prices for a
# single-site outpatient clinic; the clinic sets its own in the admin afterwards.
SERVICES = [
    ("CONS-GEN", "General consultation", Department.CONSULTATION, "500.00"),
    ("CONS-REV", "Review consultation", Department.CONSULTATION, "300.00"),
    ("LAB-MPS", "Malaria parasite smear", Department.LABORATORY, "300.00"),
    ("LAB-HB", "Haemoglobin", Department.LABORATORY, "250.00"),
    ("LAB-UA", "Urinalysis", Department.LABORATORY, "350.00"),
    ("LAB-RBS", "Random blood sugar", Department.LABORATORY, "200.00"),
    ("LAB-WIDAL", "Widal test", Department.LABORATORY, "600.00"),
    ("LAB-FBC", "Full haemogram (FBC)", Department.LABORATORY, "800.00"),
    ("LAB-UPT", "Pregnancy test (UPT)", Department.LABORATORY, "300.00"),
    ("LAB-STOOL", "Stool analysis", Department.LABORATORY, "350.00"),
    ("LAB-HIV", "HIV test", Department.LABORATORY, "400.00"),
    ("PHA-PARA", "Paracetamol 500mg (per tablet)", Department.PHARMACY, "10.00"),
    ("PHA-AMOX", "Amoxicillin 500mg (per capsule)", Department.PHARMACY, "25.00"),
    ("PHA-ORS", "Oral rehydration salts (sachet)", Department.PHARMACY, "50.00"),
    ("PRO-INJ", "Injection administration", Department.PROCEDURE, "200.00"),
    ("PRO-DRESS", "Wound dressing", Department.PROCEDURE, "400.00"),
    ("PRO-SUT", "Suturing (simple)", Department.PROCEDURE, "1500.00"),
]


class Command(BaseCommand):
    help = "Create the starting price list (idempotent; never overwrites prices)."

    def handle(self, *args, **options):
        created = 0
        for code, name, department, price in SERVICES:
            _, was_created = Service.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "department": department,
                    "unit_price": Decimal(price),
                },
            )
            created += was_created

        total = Service.objects.count()
        self.stdout.write(
            self.style.SUCCESS(f"{total} services present ({created} created this run).")
        )
