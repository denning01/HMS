from django.contrib import admin

from .models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("service", "visit", "quantity", "status", "ordered_at", "ordered_by")
    list_filter = ("status", "service__department", "ordered_at")
    search_fields = ("visit__patient__mrn", "service__name", "service__code")
    readonly_fields = ("ordered_at",)
