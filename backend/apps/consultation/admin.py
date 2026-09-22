from django.contrib import admin

from .models import Consultation


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ("visit", "diagnosis", "doctor", "started_at", "updated_at")
    list_filter = ("started_at",)
    search_fields = (
        "visit__patient__mrn",
        "visit__patient__first_name",
        "visit__patient__last_name",
        "diagnosis",
        "icd10_code",
    )
    readonly_fields = ("started_at", "updated_at")
