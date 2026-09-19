from django.contrib import admin

from .models import Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    """The Administrator's price list."""

    list_display = ("code", "name", "department", "unit_price", "is_active")
    list_filter = ("department", "is_active")
    list_editable = ("unit_price", "is_active")
    search_fields = ("code", "name")
    ordering = ("department", "name")
