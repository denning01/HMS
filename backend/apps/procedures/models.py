"""The procedure and injection room: what was done, by whom, and what it used up.

One record per ordered procedure. The consumables it used are not a list on this
record — they are the stock movements that came off the shelf for it, which is
the same ledger the pharmacy keeps. Counting them anywhere else would be a
second set of books.
"""

from django.conf import settings
from django.db import models


class ProcedureRecord(models.Model):
    """One procedure, carried out."""

    order = models.OneToOneField(
        "orders.Order", on_delete=models.PROTECT, related_name="procedure_record"
    )

    notes = models.TextField(
        blank=True, help_text="What was done and how the patient tolerated it."
    )

    performed_at = models.DateTimeField(null=True, blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="procedures_performed",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-order__ordered_at"]

    def __str__(self):
        return f"{self.order.service.name} for {self.order.visit.patient.mrn}"

    @property
    def is_performed(self):
        return self.performed_at is not None

    @property
    def consumable_cost(self):
        """What the stock used up cost, at the price those units were bought for.

        Read from the movements rather than stored, so it cannot disagree with
        the shelf it came off.
        """
        return sum((movement.cost_total for movement in self.stock_movements.all()), 0)
