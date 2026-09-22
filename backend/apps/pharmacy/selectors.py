"""Reads of the shelf: what is there, what is short, what is about to expire."""

from datetime import timedelta

from django.db.models import Q, Sum
from django.utils import timezone

from .models import StockBatch, StockItem

# Far enough ahead that a clinic can still use or return the stock.
EXPIRY_WARNING_DAYS = 90


def stock_levels():
    """Every item with its count, in one query rather than one per row."""
    return (
        StockItem.objects.filter(is_active=True)
        .select_related("service")
        .annotate(
            quantity=Sum("batches__quantity_remaining", default=0),
            in_date_quantity=Sum(
                "batches__quantity_remaining",
                filter=Q(batches__expires_on__gte=timezone.localdate()),
                default=0,
            ),
        )
        .order_by("name")
    )


def low_stock():
    """At or below the reorder level — what the pharmacist has to order today."""
    return [item for item in stock_levels() if item.quantity <= item.reorder_level]


def expiring_batches(within_days=EXPIRY_WARNING_DAYS):
    """Stock that will be money thrown away unless it is used or returned."""
    today = timezone.localdate()
    horizon = today + timedelta(days=within_days)
    return (
        StockBatch.objects.filter(quantity_remaining__gt=0, expires_on__lte=horizon)
        .select_related("item")
        .order_by("expires_on")
    )
