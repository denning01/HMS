from django.contrib import admin

from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("patient", "scheduled_for", "department", "clinician", "status")
    list_filter = ("status", "department", "scheduled_for")
    search_fields = (
        "patient__mrn",
        "patient__first_name",
        "patient__last_name",
        "reason",
    )
    readonly_fields = ("created_at", "updated_at")
