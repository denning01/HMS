from django.contrib import admin

from .models import Invoice, InvoiceLine, Payment, Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    """The Administrator's price list."""

    list_display = ("code", "name", "department", "unit_price", "is_active")
    list_filter = ("department", "is_active")
    list_editable = ("unit_price", "is_active")
    search_fields = ("code", "name")
    ordering = ("department", "name")


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0
    fields = ("description", "unit_price", "quantity", "status", "ordered_by", "paid_at")
    # Charges are raised by the departments, not typed in here; the admin is for
    # looking at a bill, not for rewriting one.
    readonly_fields = fields
    can_delete = False


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "patient", "status_label", "total", "paid_total", "balance")
    search_fields = ("number", "visit__patient__mrn", "visit__patient__last_name")
    readonly_fields = ("number", "visit", "created_at")
    inlines = [InvoiceLineInline]

    @admin.display(description="Patient")
    def patient(self, obj):
        return obj.visit.patient


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "invoice", "amount", "method", "received_by", "received_at")
    list_filter = ("method", "received_at")
    search_fields = ("receipt_number", "reference", "invoice__number")
    readonly_fields = ("receipt_number", "invoice", "amount", "method", "reference", "received_by", "received_at")

    def has_delete_permission(self, request, obj=None):
        # A receipt is a financial record. Corrections are refunds, not deletions.
        return False
