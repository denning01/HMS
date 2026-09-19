from django.contrib import admin

from .models import Patient, Visit


class VisitInline(admin.TabularInline):
    model = Visit
    extra = 0
    fields = ("started_at", "status", "billing_mode", "is_urgent", "created_by")
    readonly_fields = ("started_at",)
    show_change_link = True


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("mrn", "full_name", "sex", "age", "phone_number", "residence")
    list_filter = ("sex", "created_at")
    search_fields = ("mrn", "first_name", "middle_name", "last_name", "phone_number", "national_id")
    readonly_fields = ("mrn", "created_at", "updated_at", "age")
    inlines = [VisitInline]

    fieldsets = (
        ("Identity", {"fields": ("mrn", ("first_name", "middle_name", "last_name"), ("date_of_birth", "age"), "sex", "national_id")}),
        ("Contact", {"fields": ("phone_number", "residence")}),
        ("Next of kin", {"fields": ("next_of_kin_name", "next_of_kin_relationship", "next_of_kin_phone")}),
        ("Record", {"fields": ("created_by", "created_at", "updated_at")}),
    )

    @admin.display(description="Name", ordering="last_name")
    def full_name(self, obj):
        return obj.full_name

    @admin.display(description="Age")
    def age(self, obj):
        return obj.age if obj.pk else "—"


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ("patient", "started_at", "status", "billing_mode", "is_urgent", "created_by")
    list_filter = ("status", "billing_mode", "is_urgent", "started_at")
    search_fields = ("patient__mrn", "patient__first_name", "patient__last_name")
    readonly_fields = ("started_at",)
    autocomplete_fields = ("patient",)
