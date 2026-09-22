from django.contrib import admin

from .models import Prescription, StockBatch, StockItem, StockMovement


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ("name", "strength", "form", "unit", "quantity_in_stock", "reorder_level", "is_active")
    list_filter = ("form", "is_active")
    search_fields = ("name", "generic_name", "service__code")

    @admin.display(description="In stock")
    def quantity_in_stock(self, obj):
        return obj.quantity_in_stock


@admin.register(StockBatch)
class StockBatchAdmin(admin.ModelAdmin):
    list_display = ("item", "batch_number", "quantity_remaining", "unit_cost", "expires_on", "supplier")
    list_filter = ("expires_on",)
    search_fields = ("item__name", "batch_number", "supplier")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("item", "quantity", "reason", "unit_cost", "recorded_at", "recorded_by")
    list_filter = ("reason", "recorded_at")
    search_fields = ("item__name", "note")
    readonly_fields = ("recorded_at",)


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ("order", "directions", "dispensed_at", "dispensed_by")
    search_fields = ("order__visit__patient__mrn", "order__service__name")
    readonly_fields = ("dispensed_at",)
