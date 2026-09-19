from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Staff accounts. Roles are managed through the Groups field."""

    list_display = ("username", "get_full_name", "roles_display", "is_active", "is_staff")
    list_filter = ("is_active", "is_staff", "is_superuser", "groups")
    search_fields = ("username", "first_name", "last_name", "email", "staff_id")

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Clinic details", {"fields": ("phone_number", "staff_id")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Clinic details", {"fields": ("first_name", "last_name", "email", "phone_number", "staff_id")}),
    )

    @admin.display(description="Roles")
    def roles_display(self, obj):
        return ", ".join(sorted(obj.role_names)) or "—"
