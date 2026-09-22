"""Put the pharmacy price list on a shelf, and add the consumables nobody bills.

Idempotent on the item name: it creates what is missing and leaves reorder
levels the clinic has set alone. It stocks nothing — quantities arrive as
batches, through the pharmacist receiving a delivery, because that is where cost
and expiry come from.
"""

from django.core.management.base import BaseCommand

from apps.billing.models import Department, Service
from apps.pharmacy.models import Form, StockItem

# (service code, name, form, strength, unit, reorder level). The clinic stocks
# generics, so the shelf name is the generic name and the strength is its own
# field — "Paracetamol" plus "500 mg" rather than one string carrying both.
DRUGS = [
    ("PHA-PARA", "Paracetamol", Form.TABLET, "500 mg", "tablet", 200),
    ("PHA-AMOX", "Amoxicillin", Form.CAPSULE, "500 mg", "capsule", 100),
    ("PHA-ORS", "Oral rehydration salts", Form.SACHET, "", "sachet", 50),
    ("PHA-IBU", "Ibuprofen", Form.TABLET, "400 mg", "tablet", 100),
    ("PHA-METRO", "Metronidazole", Form.TABLET, "400 mg", "tablet", 100),
    ("PHA-CTX", "Ceftriaxone", Form.INJECTION, "1 g", "vial", 20),
]

# Used up inside a procedure that is priced as a whole, so they are counted
# without ever being a line on a bill.
CONSUMABLES = [
    ("Gauze swabs", "", "piece", 100),
    ("Syringe 5ml", "", "piece", 100),
    ("Examination gloves", "", "pair", 200),
    ("Cotton wool", "", "roll", 20),
    ("IV giving set", "", "piece", 20),
    ("Suture pack 3/0", "", "pack", 10),
]


class Command(BaseCommand):
    help = "Create the stock list for the pharmacy price list and the consumables."

    def handle(self, *args, **options):
        created = 0

        for code, name, form, strength, unit, reorder in DRUGS:
            service = Service.objects.filter(code=code, department=Department.PHARMACY).first()
            if service is None:
                self.stdout.write(self.style.WARNING(f"{code} is not in the price list — skipped."))
                continue

            _, was_created = StockItem.objects.get_or_create(
                service=service,
                defaults={
                    "name": name,
                    "form": form,
                    "strength": strength,
                    "unit": unit,
                    "reorder_level": reorder,
                },
            )
            created += was_created

        for name, strength, unit, reorder in CONSUMABLES:
            _, was_created = StockItem.objects.get_or_create(
                name=name,
                service=None,
                defaults={
                    "form": Form.CONSUMABLE,
                    "strength": strength,
                    "unit": unit,
                    "reorder_level": reorder,
                },
            )
            created += was_created

        total = StockItem.objects.count()
        self.stdout.write(
            self.style.SUCCESS(f"{total} stock items present ({created} created this run).")
        )
