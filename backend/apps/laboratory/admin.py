from django.contrib import admin

from .models import LabResult, LabTest


@admin.register(LabTest)
class LabTestAdmin(admin.ModelAdmin):
    list_display = ("service", "specimen", "reference_range", "preparation")
    list_filter = ("specimen",)
    search_fields = ("service__name", "service__code")


@admin.register(LabResult)
class LabResultAdmin(admin.ModelAdmin):
    list_display = ("order", "specimen", "stage", "is_abnormal", "released_at")
    list_filter = ("specimen", "is_abnormal", "released_at")
    search_fields = ("order__visit__patient__mrn", "order__service__name")
    readonly_fields = ("collected_at", "recorded_at", "released_at")

    @admin.display(description="Stage")
    def stage(self, obj):
        return obj.stage
