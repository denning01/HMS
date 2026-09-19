"""The price list.

Every charge in the system is priced from a Service. The catalogue is the only
place a price is set, and the Administrator maintains it; nobody types an amount
into a bill by hand.

Prices here change over time. A charge already raised must not change with them,
so an invoice line copies the price it was raised at rather than pointing back to
this table — see apps.billing.models.InvoiceLine.
"""

from django.core.validators import MinValueValidator
from django.db import models


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
