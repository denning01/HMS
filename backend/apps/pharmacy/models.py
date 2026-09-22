"""The pharmacy: what is held, what it cost, and what left the shelf.

Four records:

- StockItem     a thing the clinic holds stock of — a drug it dispenses, or a
                consumable the procedure room uses up.
- StockBatch    one delivery of it: its number, its expiry, and what it cost.
- StockMovement every unit in and every unit out, with a reason and a person.
- Prescription  the doctor's directions for one drug on one visit.

Cost sits on the batch, not on the item, because it is what was actually paid
for those units. Profit is revenue minus what the units dispensed cost, and that
answer only exists if each dispensing knows which batch it came out of.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class Form(models.TextChoices):
    TABLET = "tablet", "Tablet"
    CAPSULE = "capsule", "Capsule"
    SYRUP = "syrup", "Syrup"
    INJECTION = "injection", "Injection"
    CREAM = "cream", "Cream or ointment"
    DROPS = "drops", "Drops"
    SACHET = "sachet", "Sachet"
    CONSUMABLE = "consumable", "Consumable"


class StockItem(models.Model):
    """Something the clinic keeps on a shelf and counts.

    `service` is what it is sold as, and is optional: gauze and syringes are
    consumed inside a procedure that is priced as a whole, so they are counted
    without ever being a line on a bill.
    """

    service = models.OneToOneField(
        "billing.Service",
        on_delete=models.PROTECT,
        related_name="stock_item",
        null=True,
        blank=True,
        help_text="The priced service this is dispensed as. Blank for consumables.",
    )

    name = models.CharField(max_length=120)
    generic_name = models.CharField(max_length=120, blank=True)
    form = models.CharField(max_length=20, choices=Form.choices)
    strength = models.CharField(max_length=40, blank=True, help_text="e.g. 500 mg")
    unit = models.CharField(
        max_length=20,
        default="unit",
        help_text="What one counted unit is — tablet, ml, sachet, piece.",
    )

    reorder_level = models.PositiveIntegerField(
        default=0, help_text="Falls to this or below and it shows as low stock."
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} {self.strength}".strip()

    @property
    def quantity_in_stock(self):
        """Counted from the batches, so it cannot disagree with what is on the
        shelf. Lists annotate this in one query instead of reading it per row."""
        return self.batches.aggregate(total=Sum("quantity_remaining"))["total"] or 0

    @property
    def is_low(self):
        return self.quantity_in_stock <= self.reorder_level


class StockBatch(models.Model):
    """One delivery, with its own cost and its own expiry date."""

    item = models.ForeignKey(StockItem, on_delete=models.PROTECT, related_name="batches")

    batch_number = models.CharField(max_length=40, blank=True)
    quantity_received = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    # The running balance. Every change to it is written as a StockMovement in
    # the same transaction, so the ledger and the balance are one operation and
    # a test can prove they still agree.
    quantity_remaining = models.PositiveIntegerField()

    unit_cost = models.DecimalField(
        "Unit cost (KES)",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="What the clinic paid per unit — this is what makes profit reportable.",
    )
    expires_on = models.DateField()
    supplier = models.CharField(max_length=120, blank=True)

    received_at = models.DateTimeField(auto_now_add=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="stock_received",
        null=True,
        blank=True,
    )

    class Meta:
        # Earliest expiry first: it is the order stock should leave in, so it is
        # the order the shelf is read in.
        ordering = ["expires_on", "received_at"]
        indexes = [models.Index(fields=["item", "expires_on"])]

    def __str__(self):
        return f"{self.item} — {self.batch_number or 'no batch number'} exp {self.expires_on}"

    @property
    def is_expired(self):
        return self.expires_on < timezone.localdate()

    @property
    def days_to_expiry(self):
        return (self.expires_on - timezone.localdate()).days


class MovementReason(models.TextChoices):
    RECEIVED = "received", "Received"
    DISPENSED = "dispensed", "Dispensed"
    CONSUMED = "consumed", "Used in a procedure"
    WASTAGE = "wastage", "Wastage or breakage"
    EXPIRED = "expired", "Written off, expired"
    CORRECTION = "correction", "Stock count correction"


class StockMovement(models.Model):
    """Every unit in and every unit out, with a reason and a person.

    Signed: positive is stock in, negative is stock out. Reconciling the shelf
    against what was dispensed and billed means reading this and nothing else.
    """

    item = models.ForeignKey(StockItem, on_delete=models.PROTECT, related_name="movements")
    batch = models.ForeignKey(
        StockBatch, on_delete=models.PROTECT, related_name="movements"
    )

    quantity = models.IntegerField(help_text="Positive in, negative out.")
    reason = models.CharField(max_length=20, choices=MovementReason.choices)
    note = models.CharField(max_length=200, blank=True)

    # What caused it, where there was a cause on the system rather than a person
    # deciding at the shelf.
    prescription = models.ForeignKey(
        "pharmacy.Prescription",
        on_delete=models.PROTECT,
        related_name="movements",
        null=True,
        blank=True,
    )

    # Copied from the batch as the units move, so a later correction to a batch
    # cost cannot rewrite the cost of stock already gone.
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)

    recorded_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="stock_movements",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [models.Index(fields=["item", "-recorded_at"])]

    def __str__(self):
        return f"{self.quantity:+d} {self.item} ({self.get_reason_display()})"

    @property
    def cost_total(self):
        return abs(self.quantity) * self.unit_cost


class Prescription(models.Model):
    """The doctor's directions for one drug, and its dispensing."""

    order = models.OneToOneField(
        "orders.Order", on_delete=models.PROTECT, related_name="prescription"
    )

    dosage = models.CharField(max_length=60, blank=True, help_text="e.g. 1 tablet")
    frequency = models.CharField(max_length=60, blank=True, help_text="e.g. three times a day")
    duration = models.CharField(max_length=60, blank=True, help_text="e.g. 5 days")
    instructions = models.CharField(max_length=200, blank=True, help_text="e.g. after food")

    dispensed_at = models.DateTimeField(null=True, blank=True)
    dispensed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="prescriptions_dispensed",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-order__ordered_at"]

    def __str__(self):
        return f"{self.order.service.name} for {self.order.visit.patient.mrn}"

    @property
    def is_dispensed(self):
        return self.dispensed_at is not None

    @property
    def directions(self):
        """The label on the packet, in one line."""
        parts = [self.dosage, self.frequency, self.duration]
        line = ", ".join(part for part in parts if part)
        if self.instructions:
            line = f"{line} — {self.instructions}" if line else self.instructions
        return line
