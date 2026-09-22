"""What the doctor asks another department to do.

An order is one row here and one charge on the visit's bill, created together.
Laboratory, Pharmacy and the Procedure room all work from this record, so the
question every one of them has to ask first — has billing cleared this? — has a
single answer rather than three.

The department that carries the order out attaches its own record to it (a
result, a dispensing, a procedure performed) rather than restating what an order
already holds: who asked, for what, at what price, and when.
"""

from django.conf import settings
from django.db import models

from apps.billing.models import Department


class OrderStatus(models.TextChoices):
    """How far the receiving department has got with it.

    Deliberately coarse. What "in progress" means differs department by
    department — a sample collected, a prescription part-dispensed — and each one
    keeps that detail on its own record.
    """

    ORDERED = "ordered", "Ordered"
    IN_PROGRESS = "in_progress", "In progress"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


OPEN_ORDER_STATUSES = [OrderStatus.ORDERED, OrderStatus.IN_PROGRESS]


class Order(models.Model):
    """One request from the consulting room to a department."""

    visit = models.ForeignKey(
        "patients.Visit", on_delete=models.PROTECT, related_name="orders"
    )
    service = models.ForeignKey(
        "billing.Service", on_delete=models.PROTECT, related_name="orders"
    )
    quantity = models.PositiveIntegerField(default=1)

    # The charge this order raised. One-to-one, because the department acts on
    # the order and the cashier settles the line, and the two must be the same
    # thing seen from either side.
    invoice_line = models.OneToOneField(
        "billing.InvoiceLine", on_delete=models.PROTECT, related_name="order"
    )

    clinical_details = models.TextField(
        blank=True,
        help_text="Why it was ordered — what the department needs to know before acting.",
    )

    status = models.CharField(
        max_length=20, choices=OrderStatus.choices, default=OrderStatus.ORDERED
    )

    ordered_at = models.DateTimeField(auto_now_add=True)
    ordered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders_placed",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["ordered_at"]
        indexes = [models.Index(fields=["status", "ordered_at"])]

    def __str__(self):
        return f"{self.service.name} for {self.visit.patient.mrn}"

    @property
    def patient(self):
        return self.visit.patient

    @property
    def department(self):
        return self.service.department

    @property
    def department_display(self):
        return Department(self.service.department).label

    @property
    def is_cleared(self):
        """True when billing allows the department to act.

        The rule itself lives on the charge: pay-per-service waits for the line
        to be paid, consolidated billing never holds work up.
        """
        return self.invoice_line.is_cleared

    @property
    def is_open(self):
        return self.status in set(OPEN_ORDER_STATUSES)
