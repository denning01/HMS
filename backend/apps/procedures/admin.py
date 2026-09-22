from django.contrib import admin

from .models import ProcedureRecord


@admin.register(ProcedureRecord)
class ProcedureRecordAdmin(admin.ModelAdmin):
    list_display = ("order", "performed_at", "performed_by")
    list_filter = ("performed_at",)
    search_fields = ("order__visit__patient__mrn", "order__service__name")
    readonly_fields = ("performed_at",)
