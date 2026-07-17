from django.contrib import admin

from .models import Event, HomepageFeature, Program, SiteConfiguration, SocialLink


class UpdatedByAdminMixin:
    def save_model(self, request, obj, form, change):
        if hasattr(obj, "updated_by_id"):
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(UpdatedByAdminMixin, admin.ModelAdmin):
    readonly_fields = ("phone_link", "updated_at", "updated_by")
    fieldsets = (
        ("Business details", {"fields": ("gym_name", "announcement", "phone", "phone_link", "email", "street_address", "city_state_zip", "hours_note", "opened_year", "age_range")}),
        ("Jackrabbit links", {"fields": ("registration_url", "portal_url", "class_schedule_url", "jackrabbit_owner_url", "staff_portal_url")}),
        ("Other links", {"fields": ("map_url", "accessibility_url")}),
        ("Search and branding", {"fields": ("meta_title", "meta_description", "logo", "favicon", "logo_alt")}),
        ("Hero", {"fields": ("header_button_text", "hero_eyebrow", "hero_heading", "hero_accent", "hero_body", "hero_image", "hero_image_alt", "hero_primary_button", "hero_secondary_button")}),
        ("Introduction", {"fields": ("intro_eyebrow", "intro_heading", "intro_accent", "intro_lead", "intro_body")}),
        ("Jackrabbit registration and payments", {"fields": ("show_payments", "payment_eyebrow", "payment_heading", "payment_body", "payment_benefit_one", "payment_benefit_two", "payment_benefit_three", "payment_portal_note", "payment_new_heading", "payment_new_body", "payment_new_button", "payment_existing_heading", "payment_existing_body", "payment_existing_button")}),
        ("Online waiver", {"fields": ("show_online_waiver", "privacy_url")}),
        ("Programs", {"fields": ("show_programs", "programs_eyebrow", "programs_heading", "programs_body")}),
        ("Why Gyminators", {"fields": ("show_why", "why_eyebrow", "why_heading", "why_body", "why_image", "why_image_alt")}),
        ("Events", {"fields": ("show_events", "events_eyebrow", "events_heading", "events_body")}),
        ("Trial and footer", {"fields": ("show_trial", "trial_eyebrow", "trial_heading", "trial_body", "trial_button_text", "footer_body", "footer_credentials", "terms_url", "cancellation_url")}),
        ("Audit", {"fields": ("updated_at", "updated_by")}),
    )

    def has_add_permission(self, request):
        return not SiteConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Program)
class ProgramAdmin(UpdatedByAdminMixin, admin.ModelAdmin):
    list_display = ("name", "age_range", "featured", "published", "display_order")
    list_editable = ("featured", "published", "display_order")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "description")


@admin.register(Event)
class EventAdmin(UpdatedByAdminMixin, admin.ModelAdmin):
    list_display = ("title", "starts_at", "published", "expires_at", "display_order")
    list_editable = ("published", "display_order")
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title", "description")


@admin.register(HomepageFeature)
class HomepageFeatureAdmin(UpdatedByAdminMixin, admin.ModelAdmin):
    list_display = ("title", "section", "published", "display_order")
    list_editable = ("published", "display_order")
    list_filter = ("section", "published")


@admin.register(SocialLink)
class SocialLinkAdmin(UpdatedByAdminMixin, admin.ModelAdmin):
    list_display = ("label", "url", "published", "display_order")
    list_editable = ("published", "display_order")
