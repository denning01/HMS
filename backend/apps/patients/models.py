"""Patient and Visit — the two records every other module hangs off.

A Patient is created once and reused for life. A Visit is created each time the
patient attends; vitals, consultation notes, orders, results and invoice lines all
attach to one Visit, which is what lets Billing pull a single bill together and
lets a doctor see this visit's results without re-asking the patient.
"""

from datetime import date

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class Sex(models.TextChoices):
    FEMALE = "F", "Female"
    MALE = "M", "Male"


class Patient(models.Model):
    """A person known to the clinic, across all their visits."""

    # Permanent, system-generated medical record number, assigned on first save.
    mrn = models.CharField("MRN", max_length=20, unique=True, editable=False, blank=True)

    first_name = models.CharField(max_length=60)
    middle_name = models.CharField(max_length=60, blank=True)
    last_name = models.CharField(max_length=60)

    date_of_birth = models.DateField()
    sex = models.CharField(max_length=1, choices=Sex.choices)

    phone_number = models.CharField(max_length=20, blank=True)
    residence = models.CharField(max_length=120, blank=True, help_text="Area or address")
    national_id = models.CharField(
        max_length=20,
        blank=True,
        help_text="Adults only; left blank for minors.",
    )

    next_of_kin_name = models.CharField(max_length=120, blank=True)
    next_of_kin_relationship = models.CharField(
        max_length=40,
        blank=True,
        help_text="e.g. spouse, parent, sibling",
    )
    next_of_kin_phone = models.CharField(max_length=20, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="patients_registered",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["last_name", "first_name"]),
            models.Index(fields=["phone_number"]),
        ]

    def __str__(self):
        return f"{self.mrn} — {self.full_name}"

    def save(self, *args, **kwargs):
        """Assign the MRN on first save, derived from the primary key.

        Deriving it from the PK means the number is unique without a second
        counter to keep in step, and it never changes once assigned.
        """
        if self.mrn:
            return super().save(*args, **kwargs)

        with transaction.atomic():
            super().save(*args, **kwargs)
            Patient.objects.filter(pk=self.pk).update(mrn=f"MRN{self.pk:06d}")
            self.mrn = f"MRN{self.pk:06d}"

    @property
    def full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(part for part in parts if part)

    @property
    def age(self):
        """Age in completed years."""
        today = date.today()
        had_birthday = (today.month, today.day) >= (
            self.date_of_birth.month,
            self.date_of_birth.day,
        )
        return today.year - self.date_of_birth.year - (0 if had_birthday else 1)

    @property
    def is_paediatric(self):
        """Under 18 — surfaced at Registration so the doctor sees it up front."""
        return self.age < 18


class VisitStatus(models.TextChoices):
    """Where a visit currently sits in the patient journey."""

    AWAITING_TRIAGE = "awaiting_triage", "Awaiting triage"
    AWAITING_CONSULTATION = "awaiting_consultation", "Awaiting consultation"
    IN_CONSULTATION = "in_consultation", "In consultation"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class BillingMode(models.TextChoices):
    """How this visit's charges are settled.

    Pay-per-service is the default: each department is gated on its own line item
    being paid. Consolidated accumulates every charge into one bill settled at the
    end, for staff, corporate accounts, and a future insurance workflow.
    """

    PAY_PER_SERVICE = "pay_per_service", "Pay per service"
    CONSOLIDATED = "consolidated", "Consolidated"


class Visit(models.Model):
    """One attendance. Everything that happens that day attaches here."""

    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="visits")

    status = models.CharField(
        max_length=30,
        choices=VisitStatus.choices,
        default=VisitStatus.AWAITING_TRIAGE,
    )
    billing_mode = models.CharField(
        max_length=20,
        choices=BillingMode.choices,
        default=BillingMode.PAY_PER_SERVICE,
    )

    is_urgent = models.BooleanField(
        default=False,
        help_text="Set at triage when vitals are out of range; prioritises the doctor's queue.",
    )

    started_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="visits_started",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["status", "-started_at"]),
        ]

    def __str__(self):
        return f"{self.patient.mrn} — {self.started_at:%Y-%m-%d %H:%M}"

    @property
    def is_open(self):
        return self.status not in {VisitStatus.COMPLETED, VisitStatus.CANCELLED}

    @property
    def is_first_visit(self):
        """True when this is the patient's only visit — the spec's new/returning flag."""
        return not self.patient.visits.exclude(pk=self.pk).exists()

    def close(self, *, status=VisitStatus.COMPLETED):
        self.status = status
        self.closed_at = timezone.now()
        self.save(update_fields=["status", "closed_at"])
