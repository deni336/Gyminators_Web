import logging
import os
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from jackrabbit_reporting.services.metrics import class_reporting_summary
from jackrabbit_reporting.services.schedule import class_calendar_context

from .forms import EventForm, HomepageFeatureForm, ProgramForm, SiteConfigurationForm, SocialLinkForm
from .models import Event, HomepageFeature, Program, SiteConfiguration, SocialLink

logger = logging.getLogger(__name__)


def home(request):
    now = timezone.now()
    events = (
        Event.objects.filter(published=True)
        .filter(Q(publish_at__isnull=True) | Q(publish_at__lte=now))
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    )
    programs = Program.objects.filter(published=True)
    return render(
        request,
        "website/home.html",
        {
            "site": SiteConfiguration.get_solo(),
            "featured_programs": programs.filter(featured=True),
            "specialty_programs": programs.filter(featured=False),
            "events": events,
            "proof_points": HomepageFeature.objects.filter(section="proof", published=True),
            "benefits": HomepageFeature.objects.filter(section="benefit", published=True),
            "social_links": SocialLink.objects.filter(published=True),
        },
    )


def class_schedule(request):
    context = class_calendar_context(request.GET, settings.JACKRABBIT_ORG_ID)
    summary = class_reporting_summary()
    requires_verification = bool(
        (summary["available"] and (summary["stale"] or summary["latest_sync_failed"]))
        or summary["pending_confirmation"]
        or (summary["count"] and not summary["sync_enabled"])
    )
    context.update(
        {
            "calendar_last_updated": summary["last_success"],
            "calendar_is_stale": requires_verification,
            "calendar_snapshot_available": summary["available"],
            "calendar_total_count": summary["count"],
            "schedule_timezone": settings.TIME_ZONE,
            "social_links": SocialLink.objects.filter(published=True),
        }
    )
    return render(request, "website/class_schedule.html", context)


def favicon(request):
    site = SiteConfiguration.get_solo()
    return redirect(site.favicon.url if site.favicon else static("images/logo.png"))


def health(request):
    try:
        connection.ensure_connection()
    except Exception:
        logger.exception("Database health check failed")
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


CMS_TYPES = {
    "programs": {
        "model": Program,
        "form": ProgramForm,
        "title": "Programs",
        "singular": "program",
        "description": "Edit program details and upload, replace, or remove each program picture.",
        "image_field": "image",
        "fallback_image_field": "fallback_image",
        "columns": (("Program", "name"), ("Age range", "age_range"), ("Featured", "featured"), ("Published", "published"), ("Order", "display_order")),
    },
    "events": {
        "model": Event,
        "form": EventForm,
        "title": "Events",
        "singular": "event",
        "description": "Publish events with an optional picture, schedule, price note, and destination.",
        "image_field": "image",
        "columns": (("Event", "title"), ("Starts", "starts_at"), ("Published", "published"), ("Expires", "expires_at"), ("Order", "display_order")),
    },
    "features": {
        "model": HomepageFeature,
        "form": HomepageFeatureForm,
        "title": "Homepage highlights",
        "singular": "highlight",
        "description": "Manage the short proof points and benefits shown around the homepage.",
        "columns": (("Highlight", "title"), ("Section", "get_section_display"), ("Published", "published"), ("Order", "display_order")),
    },
    "social-links": {
        "model": SocialLink,
        "form": SocialLinkForm,
        "title": "Social links",
        "singular": "social link",
        "description": "Keep the public social profile links in the footer accurate.",
        "columns": (("Label", "label"), ("URL", "url"), ("Published", "published"), ("Order", "display_order")),
    },
}


def _model_permission(user, action, model):
    return user.has_perm(f"{model._meta.app_label}.{action}_{model._meta.model_name}")


def _can_manage_content(user):
    return user.is_superuser or user.has_perm("website.change_siteconfiguration") or any(
        _model_permission(user, "change", config["model"]) for config in CMS_TYPES.values()
    )


def _can_view_reporting(user):
    return user.has_perm("jackrabbit_reporting.view_reporting_dashboard")


def _can_view_waivers(user):
    return user.has_perm("waivers.view_waiver")


def _can_access_dashboard(user):
    return _can_manage_content(user) or _can_view_reporting(user) or _can_view_waivers(user)


def _cms_config(kind):
    config = CMS_TYPES.get(kind)
    if not config:
        raise Http404
    return config


def _require_permission(user, action, model):
    if not _model_permission(user, action, model):
        raise PermissionDenied


def _display_value(obj, attribute):
    value = getattr(obj, attribute)
    value = value() if callable(value) else value
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, datetime):
        localized = timezone.localtime(value)
        if os.name == "nt":
            return localized.strftime("%b %d, %Y %I:%M %p").replace(" 0", " ")
        return localized.strftime("%b %-d, %Y %-I:%M %p")
    return value if value not in (None, "") else "—"


@login_required
def content_hub(request):
    if not _can_manage_content(request.user):
        raise PermissionDenied
    cards = []
    for kind, config in CMS_TYPES.items():
        if _model_permission(request.user, "view", config["model"]) or _model_permission(request.user, "change", config["model"]):
            cards.append(
                {
                    "kind": kind,
                    "title": config["title"],
                    "description": config["description"],
                    "count": config["model"].objects.count(),
                }
            )
    return render(request, "website/cms/content_hub.html", {"cards": cards})


@login_required
def site_configuration_edit(request):
    if not request.user.has_perm("website.change_siteconfiguration"):
        raise PermissionDenied
    instance = SiteConfiguration.get_solo()
    form = SiteConfigurationForm(request.POST or None, request.FILES or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.updated_by = request.user
        saved.save()
        messages.success(request, "Website details and homepage content were saved.")
        return redirect("home" if "save_view" in request.POST else "site_configuration_edit")
    groups = (
        ("Business details", ("gym_name", "announcement", "phone", "email", "street_address", "city_state_zip", "hours_note", "opened_year", "age_range")),
        ("Jackrabbit links", ("registration_url", "portal_url", "class_schedule_url", "jackrabbit_owner_url", "staff_portal_url")),
        ("Other links", ("map_url", "accessibility_url")),
        ("Search and branding", ("meta_title", "meta_description", "logo", "favicon", "logo_alt")),
        ("Hero", ("header_button_text", "hero_eyebrow", "hero_heading", "hero_accent", "hero_body", "hero_image", "hero_image_alt", "hero_primary_button", "hero_secondary_button")),
        ("Introduction", ("intro_eyebrow", "intro_heading", "intro_accent", "intro_lead", "intro_body")),
        ("Jackrabbit registration and payments", ("show_payments", "payment_eyebrow", "payment_heading", "payment_body", "payment_benefit_one", "payment_benefit_two", "payment_benefit_three", "payment_portal_note", "payment_new_heading", "payment_new_body", "payment_new_button", "payment_existing_heading", "payment_existing_body", "payment_existing_button")),
        ("Online waiver", ("show_online_waiver", "privacy_url")),
        ("Programs", ("show_programs", "programs_eyebrow", "programs_heading", "programs_body")),
        ("Why Gyminators", ("show_why", "why_eyebrow", "why_heading", "why_body", "why_image", "why_image_alt")),
        ("Events", ("show_events", "events_eyebrow", "events_heading", "events_body")),
        ("Trial and footer", ("show_trial", "trial_eyebrow", "trial_heading", "trial_body", "trial_button_text", "footer_body", "footer_credentials", "terms_url", "cancellation_url")),
    )
    field_groups = [(title, [form[name] for name in fields]) for title, fields in groups]
    return render(request, "website/cms/site_form.html", {"form": form, "field_groups": field_groups})


@login_required
def content_list(request, kind):
    config = _cms_config(kind)
    if not (_model_permission(request.user, "view", config["model"]) or _model_permission(request.user, "change", config["model"])):
        raise PermissionDenied
    rows = []
    for obj in config["model"].objects.all():
        picture = None
        image_field = config.get("image_field")
        if image_field:
            upload = getattr(obj, image_field)
            if upload:
                picture = {"url": upload.url, "label": "Uploaded"}
            else:
                fallback_field = config.get("fallback_image_field")
                fallback = getattr(obj, fallback_field, "") if fallback_field else ""
                picture = {"url": static(fallback) if fallback else "", "label": "Bundled fallback" if fallback else "No picture"}
        rows.append(
            {
                "object": obj,
                "picture": picture,
                "values": [_display_value(obj, attribute) for _, attribute in config["columns"]],
            }
        )
    return render(
        request,
        "website/cms/content_list.html",
        {
            "kind": kind,
            "config": config,
            "rows": rows,
            "can_add": _model_permission(request.user, "add", config["model"]),
            "can_change": _model_permission(request.user, "change", config["model"]),
            "can_delete": _model_permission(request.user, "delete", config["model"]),
        },
    )


@login_required
def content_edit(request, kind, pk=None):
    config = _cms_config(kind)
    action = "add" if pk is None else "change"
    _require_permission(request.user, action, config["model"])
    instance = get_object_or_404(config["model"], pk=pk) if pk is not None else None
    form = config["form"](request.POST or None, request.FILES or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            saved = form.save()
            if hasattr(saved, "updated_by_id"):
                saved.updated_by = request.user
                saved.save(update_fields=("updated_by", "updated_at"))
        messages.success(request, f"{config['singular'].title()} saved.")
        if "save_view" in request.POST:
            return redirect("home")
        return redirect("content_list", kind=kind)
    return render(request, "website/cms/content_form.html", {"form": form, "kind": kind, "config": config, "object": instance})


@login_required
def content_delete(request, kind, pk):
    config = _cms_config(kind)
    _require_permission(request.user, "delete", config["model"])
    instance = get_object_or_404(config["model"], pk=pk)
    if request.method == "POST":
        try:
            instance.delete()
            messages.success(request, f"{config['singular'].title()} deleted.")
        except ProtectedError:
            messages.error(request, "This item is still referenced and cannot be deleted. Unpublish it instead.")
        return redirect("content_list", kind=kind)
    return render(request, "website/cms/content_confirm_delete.html", {"kind": kind, "config": config, "object": instance})


def legacy_payment_redirect(request, token=None):
    messages.info(request, "Gyminators payments are now handled securely through the Jackrabbit Parent Portal.")
    return redirect(SiteConfiguration.get_solo().portal_url)


def legacy_checkout_redirect(request):
    messages.info(request, "Gyminators enrollment and payments are now managed in Jackrabbit.")
    return redirect("home")


@csrf_exempt
def stripe_webhook_retired(request):
    return HttpResponse("Stripe processing has been retired; Gyminators now uses Jackrabbit.", status=410, content_type="text/plain")


@login_required
def dashboard(request):
    if not _can_access_dashboard(request.user):
        raise PermissionDenied
    return render(
        request,
        "website/dashboard.html",
        {
            "can_manage_content": _can_manage_content(request.user),
            "can_view_reporting": _can_view_reporting(request.user),
            "can_view_waivers": _can_view_waivers(request.user),
        },
    )
