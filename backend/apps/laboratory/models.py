"""The laboratory: what each test needs, and what came back.

Two records. LabTest is the lab's half of a priced service — which specimen it
takes and what a normal result looks like, neither of which belongs on a price
list. LabResult is one test's journey from specimen to released result, hung off
the order the doctor placed.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Specimen(models.TextChoices):
    """What the technician has to collect before anything can be run."""

    BLOOD = "blood", "Blood"
    URINE = "urine", "Urine"
    STOOL = "stool", "Stool"
    SWAB = "swab", "Swab"
    SPUTUM = "sputum", "Sputum"
    OTHER = "other", "Other"


class LabTest(models.Model):
    """The lab's own detail for a service on the price list.

    Kept beside the Service rather than on it: the price list is a billing
    record maintained by the Administrator, and a specimen type is neither a
    price nor the Administrator's to know.
    """

    service = models.OneToOneField(
        "billing.Service", on_delete=models.CASCADE, related_name="lab_test"
    )
    specimen = models.CharField(max_length=20, choices=Specimen.choices)
    reference_range = models.CharField(
        max_length=120,
        blank=True,
        help_text="What normal looks like, shown beside the result as it is typed.",
    )
    preparation = models.CharField(
        max_length=200,
        blank=True,
        help_text="What the patient must do first, e.g. fast for 8 hours.",
    )

    class Meta:
        ordering = ["service__name"]

    def __str__(self):
        return f"{self.service.name} ({self.get_specimen_display()})"


class LabResult(models.Model):
    """One ordered test, from specimen to released result.

    The three stamps are the audit trail the specification asks for: who
    collected, who ran it, who released it. They are also the state — a result
    with no released_at is not yet a result the doctor can act on, and there is
    no separate status field to contradict them.
    """

    order = models.OneToOneField(
        "orders.Order", on_delete=models.PROTECT, related_name="lab_result"
    )

    specimen = models.CharField(max_length=20, choices=Specimen.choices)
    collected_at = models.DateTimeField(null=True, blank=True)
    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="specimens_collected",
        null=True,
        blank=True,
    )

    findings = models.TextField(blank=True, help_text="The result, as it is reported.")
    is_abnormal = models.BooleanField(
        default=False,
        help_text="Flagged by the technician; shows against the result in the doctor's queue.",
    )
    recorded_at = models.DateTimeField(null=True, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="lab_results_recorded",
        null=True,
        blank=True,
    )

    released_at = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="lab_results_released",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-order__ordered_at"]

    def __str__(self):
        return f"{self.order.service.name} for {self.order.visit.patient.mrn}"

    @property
    def is_collected(self):
        return self.collected_at is not None

    @property
    def is_recorded(self):
        return self.recorded_at is not None

    @property
    def is_released(self):
        return self.released_at is not None

    @property
    def stage(self):
        """Where this test has got to, in the words the worklist shows."""
        if self.is_released:
            return "released"
        if self.is_recorded:
            return "awaiting release"
        if self.is_collected:
            return "specimen collected"
        return "awaiting specimen"

    @property
    def turnaround_minutes(self):
        """Ordered to released, which is the number the clinic is judged on."""
        if not self.is_released:
            return None
        return int((self.released_at - self.order.ordered_at).total_seconds() // 60)

    @property
    def waiting_minutes(self):
        """How long this has been on the bench, for a worklist that has to be
        worked oldest first."""
        return int((timezone.now() - self.order.ordered_at).total_seconds() // 60)
