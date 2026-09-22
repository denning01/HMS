"""Give each laboratory service the lab's own detail: specimen and normal range.

Idempotent, and it never overwrites: a clinic that has corrected a reference
range in the admin keeps its correction the next time this is deployed.
"""

from django.core.management.base import BaseCommand

from apps.billing.models import Department, Service
from apps.laboratory.models import LabTest, Specimen

# (service code, specimen, reference range, preparation)
LAB_TESTS = [
    ("LAB-MPS", Specimen.BLOOD, "No parasites seen", ""),
    ("LAB-HB", Specimen.BLOOD, "M 13–17, F 12–15 g/dL", ""),
    ("LAB-UA", Specimen.URINE, "No cells, no casts", "Midstream sample"),
    ("LAB-RBS", Specimen.BLOOD, "3.9–7.8 mmol/L", ""),
    ("LAB-WIDAL", Specimen.BLOOD, "Non-reactive", ""),
    ("LAB-FBC", Specimen.BLOOD, "WBC 4–11 ×10⁹/L, Hb 12–17 g/dL", ""),
    ("LAB-UPT", Specimen.URINE, "Negative", "First morning sample preferred"),
    ("LAB-STOOL", Specimen.STOOL, "No ova or cysts seen", ""),
    ("LAB-HIV", Specimen.BLOOD, "Non-reactive", "Counselling before and after"),
]


class Command(BaseCommand):
    help = "Attach specimen types and reference ranges to the lab price list."

    def handle(self, *args, **options):
        created = 0
        for code, specimen, reference_range, preparation in LAB_TESTS:
            service = Service.objects.filter(
                code=code, department=Department.LABORATORY
            ).first()
            if service is None:
                self.stdout.write(
                    self.style.WARNING(f"{code} is not in the price list — skipped.")
                )
                continue

            _, was_created = LabTest.objects.get_or_create(
                service=service,
                defaults={
                    "specimen": specimen,
                    "reference_range": reference_range,
                    "preparation": preparation,
                },
            )
            created += was_created

        total = LabTest.objects.count()
        self.stdout.write(
            self.style.SUCCESS(f"{total} lab tests described ({created} created this run).")
        )
