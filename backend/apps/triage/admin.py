from django.contrib import admin

from .models import Vitals


@admin.register(Vitals)
class VitalsAdmin(admin.ModelAdmin):
    list_display = ("visit", "blood_pressure", "pulse_rate", "temperature", "spo2", "bmi", "recorded_by")
    list_filter = ("recorded_at",)
    search_fields = ("visit__patient__mrn", "visit__patient__first_name", "visit__patient__last_name")
    readonly_fields = ("recorded_at", "bmi", "bmi_category")

    @admin.display(description="BMI")
    def bmi(self, obj):
        return obj.bmi
