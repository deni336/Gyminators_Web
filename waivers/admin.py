from django.contrib import admin

from .models import (
    AuthorizedPickupProfile,
    EmergencyContactProfile,
    GuardianProfile,
    GymnastProfile,
    Waiver,
)


class SuperuserOnlyAdmin(admin.ModelAdmin):
    """Keep raw waiver/profile admin separate from friendly role-based records UI."""

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(GymnastProfile)
class GymnastProfileAdmin(SuperuserOnlyAdmin):
    list_display = ("first_name", "last_name", "date_of_birth", "updated_at")
    search_fields = ("first_name", "last_name")
    readonly_fields = ("id", "created_at", "updated_at")
    date_hierarchy = "updated_at"


@admin.register(GuardianProfile)
class GuardianProfileAdmin(SuperuserOnlyAdmin):
    list_display = ("gymnast", "first_name", "last_name", "updated_at")
    search_fields = ("gymnast__first_name", "gymnast__last_name", "first_name", "last_name")
    readonly_fields = ("id", "phone_digits", "created_at", "updated_at")
    autocomplete_fields = ("gymnast",)


@admin.register(EmergencyContactProfile)
class EmergencyContactProfileAdmin(SuperuserOnlyAdmin):
    list_display = ("gymnast", "first_name", "last_name", "relationship", "updated_at")
    search_fields = ("gymnast__first_name", "gymnast__last_name", "first_name", "last_name")
    readonly_fields = ("id", "phone_digits", "created_at", "updated_at")
    autocomplete_fields = ("gymnast",)


@admin.register(AuthorizedPickupProfile)
class AuthorizedPickupProfileAdmin(SuperuserOnlyAdmin):
    list_display = ("gymnast", "first_name", "last_name", "updated_at")
    search_fields = ("gymnast__first_name", "gymnast__last_name", "first_name", "last_name")
    readonly_fields = ("id", "phone_digits", "created_at", "updated_at")
    autocomplete_fields = ("gymnast",)


@admin.register(Waiver)
class WaiverAdmin(SuperuserOnlyAdmin):
    list_display = (
        "id",
        "gymnast",
        "enrollment_type",
        "participant_status",
        "signed_at",
    )
    list_filter = ("enrollment_type", "participant_status", "signed_at")
    search_fields = ("=id", "gymnast__first_name", "gymnast__last_name")
    date_hierarchy = "signed_at"
    actions = None

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
