"""Billing: the price list, the bill, its charges and the money received.

Four records, in the order money moves through them:

- Service   the price list. The only place a price is set.
- Invoice   one bill per visit, so every department's charges meet in one place.
- Line      one charge, with the price copied from the Service as it was raised.
- Payment   money received, and the receipt it produced.

Two rules run through all of it. Prices are snapshotted onto the line, because a
price list that changes next month must not rewrite what a patient was charged
last month. Totals are derived from the lines and never stored, because a stored
total is one more thing that can disagree with the charges beneath it.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction

from apps.patients.models import BillingMode


class Department(models.TextChoices):
    """The departments that raise charges, matching the workflow in the spec."""

    CONSULTATION = "consultation", "Consultation"
    LABORATORY = "laboratory", "Laboratory"
    PHARMACY = "pharmacy", "Pharmacy"
    PROCEDURE = "procedure", "Procedure / Injection room"
    OTHER = "other", "Other"


class Service(models.Model):
    """One priced item: a consultation, a test, a drug, a procedure."""

    code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Short stable code used on bills and reports, e.g. LAB-MPS.",
    )
    name = models.CharField(max_length=120)
    department = models.CharField(
        max_length=20,
        choices=Department.choices,
        help_text="Which department performs it — this is what gates the queues.",
    )
    unit_price = models.DecimalField(
        "Unit price (KES)",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Retired services stay here so old bills still read correctly.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["department", "name"]
        indexes = [models.Index(fields=["department", "is_active"])]

    def __str__(self):
        return f"{self.code} — {self.name}"


class LineStatus(models.TextChoices):
    UNPAID = "unpaid", "Unpaid"
    PAID = "paid", "Paid"
    CANCELLED = "cancelled", "Cancelled"


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"
    MPESA = "mpesa", "M-Pesa"
    CARD = "card", "Card"
    BANK = "bank", "Bank transfer"


class Invoice(models.Model):
    """One bill per visit.

    There is exactly one, created the first time anything is charged, so every
    department's charges land in the same place and the cashier settles one bill
    rather than chasing a patient around the building.
    """

    visit = models.OneToOneField(
        "patients.Visit", on_delete=models.PROTECT, related_name="invoice"
    )
    number = models.CharField(max_length=20, unique=True, editable=False, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.number} — {self.visit.patient.mrn}"

    def save(self, *args, **kwargs):
        """Assign the invoice number on first save, derived from the primary key."""
        if self.number:
            return super().save(*args, **kwargs)

        with transaction.atomic():
            super().save(*args, **kwargs)
            self.number = f"INV{self.pk:06d}"
            Invoice.objects.filter(pk=self.pk).update(number=self.number)

    # Totals are derived from the lines, never stored: a stored total is one more
    # thing that can disagree with the charges it is supposed to summarise.

    @property
    def billable_lines(self):
        return self.lines.exclude(status=LineStatus.CANCELLED)

    @property
    def total(self):
        return sum((line.line_total for line in self.billable_lines), Decimal("0.00"))

    @property
    def paid_total(self):
        return sum(
            (line.line_total for line in self.billable_lines if line.status == LineStatus.PAID),
            Decimal("0.00"),
        )

    @property
    def balance(self):
        return self.total - self.paid_total

    @property
    def is_settled(self):
        return self.balance == Decimal("0.00")

    @property
    def status_label(self):
        if not self.billable_lines:
            return "No charges"
        if self.is_settled:
            return "Paid"
        if self.paid_total:
            return "Part paid"
        return "Unpaid"


class InvoiceLine(models.Model):
    """One charge on a bill.

    The description and unit price are copied from the Service when the charge is
    raised, not read through the foreign key. A price list that changes next month
    must not silently rewrite what a patient was charged last month, and a renamed
    service must not make an old receipt unreadable.
    """

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="lines")

    description = models.CharField(max_length=120)
    unit_price = models.DecimalField("Unit price (KES)", max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    status = models.CharField(
        max_length=20, choices=LineStatus.choices, default=LineStatus.UNPAID
    )
    payment = models.ForeignKey(
        "billing.Payment",
        on_delete=models.PROTECT,
        related_name="lines",
        null=True,
        blank=True,
        help_text="The payment that settled this line.",
    )

    ordered_at = models.DateTimeField(auto_now_add=True)
    ordered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="charges_raised",
        null=True,
        blank=True,
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["ordered_at"]
        indexes = [models.Index(fields=["invoice", "status"])]

    def __str__(self):
        return f"{self.description} x{self.quantity}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def department(self):
        return self.service.department

    @property
    def is_cleared(self):
        """True when the department may act on this charge.

        Pay-per-service gates each line on its own payment. Consolidated billing
        (staff, corporate accounts) accumulates and settles at the end, so work is
        never held up waiting for a payment that comes later by arrangement.
        """
        if self.status == LineStatus.CANCELLED:
            return False
        if self.invoice.visit.billing_mode == BillingMode.CONSOLIDATED:
            return True
        return self.status == LineStatus.PAID


def cleared_lines_q(prefix=""):
    """`InvoiceLine.is_cleared` as a queryset filter, kept beside it so the two
    cannot drift apart.

    The departmental worklists ask "what may I act on?" of hundreds of rows at a
    time, which has to be one query rather than a property evaluated per row.
    `prefix` is the path to the line from whatever is being filtered — the
    orders worklist passes "invoice_line".
    """
    p = f"{prefix}__" if prefix else ""
    return ~models.Q(**{f"{p}status": LineStatus.CANCELLED}) & (
        models.Q(**{f"{p}invoice__visit__billing_mode": BillingMode.CONSOLIDATED})
        | models.Q(**{f"{p}status": LineStatus.PAID})
    )


class Payment(models.Model):
    """Money received against a bill, and the receipt it produced."""

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    receipt_number = models.CharField(
        max_length=20, unique=True, editable=False, blank=True
    )

    amount = models.DecimalField(
        "Amount (KES)",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    reference = models.CharField(
        max_length=50,
        blank=True,
        help_text="M-Pesa code or card/bank reference, where there is one.",
    )

    received_at = models.DateTimeField(auto_now_add=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payments_received",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-received_at"]
        indexes = [models.Index(fields=["-received_at"])]

    def __str__(self):
        return f"{self.receipt_number} — KES {self.amount}"

    def save(self, *args, **kwargs):
        if self.receipt_number:
            return super().save(*args, **kwargs)

        with transaction.atomic():
            super().save(*args, **kwargs)
            self.receipt_number = f"RCT{self.pk:06d}"
            Payment.objects.filter(pk=self.pk).update(receipt_number=self.receipt_number)
