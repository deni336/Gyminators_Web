from django.contrib import admin

from .models import ClassSyncRun, JackrabbitClass, JackrabbitEvent


class ReadOnlyImportAdmin(admin.ModelAdmin):
    actions = None

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm(f"{self.model._meta.app_label}.view_{self.model._meta.model_name}")

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        return None


@admin.register(JackrabbitEvent)
class JackrabbitEventAdmin(ReadOnlyImportAdmin):
    list_display = ("event_type", "occurred_at", "source", "location", "received_at")
    list_filter = ("event_type", "source", "location")
    date_hierarchy = "occurred_at"
    search_fields = ("family_id", "contact_id", "student_id", "class_id", "enrollment_id")


@admin.register(JackrabbitClass)
class JackrabbitClassAdmin(ReadOnlyImportAdmin):
    list_display = (
        "name",
        "category1",
        "meeting_days_display",
        "time_display",
        "calculated_openings",
        "tuition",
        "is_current",
        "missed_syncs",
    )
    list_filter = ("is_current", "category1", "session", "location_code", "waitlist")
    search_fields = ("name", "description", "external_id")


@admin.register(ClassSyncRun)
class ClassSyncRunAdmin(ReadOnlyImportAdmin):
    list_display = ("started_at", "status", "fetched_count", "created_count", "updated_count", "deactivated_count")
    list_filter = ("status",)
    date_hierarchy = "started_at"
