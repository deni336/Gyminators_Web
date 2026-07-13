import json
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from jackrabbit_reporting.models import JackrabbitClass
from jackrabbit_reporting.security import usable_webhook_token
from jackrabbit_reporting.services.class_feed import ClassFeedError, sync_classes
from jackrabbit_reporting.services.ingestion import (
    EventConflictError,
    EventValidationError,
    ingest_event as store_event,
)
from jackrabbit_reporting.services.metrics import (
    class_reporting_summary,
    dashboard_data,
    resolve_period,
)


def _require_reporting_permission(user):
    if not user.has_perm("jackrabbit_reporting.view_reporting_dashboard"):
        raise PermissionDenied


def _valid_webhook_token(request):
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return False
    candidate = authorization[7:].strip()
    if not candidate:
        return False
    configured = tuple(
        token.strip()
        for token in (
            settings.JACKRABBIT_WEBHOOK_TOKEN,
            settings.JACKRABBIT_WEBHOOK_PREVIOUS_TOKEN,
        )
        if usable_webhook_token(token)
    )
    return any(secrets.compare_digest(candidate, token) for token in configured)


def _json_error(message, status):
    response = JsonResponse({"status": "error", "message": message}, status=status)
    response["Cache-Control"] = "no-store"
    return response


@csrf_exempt
@require_POST
def ingest_event(request):
    if (
        not settings.JACKRABBIT_REPORTING_ENABLED
        or not usable_webhook_token(settings.JACKRABBIT_WEBHOOK_TOKEN)
    ):
        return _json_error("Jackrabbit event ingestion is not configured.", 503)
    if not _valid_webhook_token(request):
        response = _json_error("Authentication required.", 401)
        response["WWW-Authenticate"] = "Bearer"
        return response
    if request.content_type != "application/json":
        return _json_error("Content-Type must be application/json.", 415)
    if len(request.body) > settings.JACKRABBIT_WEBHOOK_MAX_BODY_BYTES:
        return _json_error("Request body is too large.", 413)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _json_error("Request body must be valid JSON.", 400)
    try:
        _event, created = store_event(payload)
    except EventConflictError as exc:
        return _json_error(str(exc), 409)
    except EventValidationError as exc:
        return _json_error(str(exc), 400)
    response = JsonResponse({"status": "created" if created else "duplicate"}, status=201 if created else 200)
    response["Cache-Control"] = "no-store"
    return response


@never_cache
@login_required
def reporting_dashboard(request):
    _require_reporting_permission(request.user)
    context = dashboard_data(resolve_period(request.GET.get("period")))
    context["can_sync"] = bool(
        settings.JACKRABBIT_REPORTING_ENABLED
        and request.user.has_perm("jackrabbit_reporting.manage_jackrabbit_sync")
    )
    return render(request, "jackrabbit_reporting/dashboard.html", context)


@never_cache
@login_required
def class_list(request):
    _require_reporting_permission(request.user)
    all_classes = JackrabbitClass.objects.filter(
        organization_id=str(settings.JACKRABBIT_ORG_ID).strip(),
        is_current=True,
    )
    classes = all_classes
    query = request.GET.get("q", "").strip()[:100]
    location = request.GET.get("location", "").strip()[:80]
    session = request.GET.get("session", "").strip()[:160]
    category = request.GET.get("category", "").strip()[:160]
    day = request.GET.get("day", "").strip().lower()
    availability = request.GET.get("availability", "").strip().lower()

    if query:
        classes = classes.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(category1__icontains=query)
            | Q(category2__icontains=query)
            | Q(category3__icontains=query)
        )
    if location:
        classes = classes.filter(location_code=location)
    if session:
        classes = classes.filter(session=session)
    if category:
        classes = classes.filter(category1=category)
    valid_days = {key for key, _label in JackrabbitClass.DAY_LABELS}
    if day in valid_days:
        classes = classes.filter(**{f"meeting_days__{day}": True})
    else:
        day = ""
    if availability in {"open", "waitlist"}:
        wanted_state = "open" if availability == "open" else "warning"
        matching_ids = [
            class_record.pk
            for class_record in classes.only(
                "id",
                "waitlist",
                "is_per_day",
                "calculated_openings",
                "openings_by_day",
                "meeting_days",
            )
            if class_record.availability_state == wanted_state
        ]
        classes = classes.filter(pk__in=matching_ids)
    else:
        availability = ""

    classes = classes.order_by("category1", "name", "start_time")
    page = Paginator(classes, 50).get_page(request.GET.get("page"))
    return render(
        request,
        "jackrabbit_reporting/class_list.html",
        {
            "page": page,
            "query": query,
            "selected_location": location,
            "selected_session": session,
            "selected_category": category,
            "selected_day": day,
            "selected_availability": availability,
            "class_summary": class_reporting_summary(),
            "locations": all_classes.exclude(location_code="").values_list("location_code", "location_name").order_by("location_code").distinct(),
            "sessions": all_classes.exclude(session="").values_list("session", flat=True).order_by("session").distinct(),
            "categories": all_classes.exclude(category1="").values_list("category1", flat=True).order_by("category1").distinct(),
            "day_choices": JackrabbitClass.DAY_LABELS,
        },
    )


@require_POST
@login_required
def sync_class_feed(request):
    if not request.user.has_perm("jackrabbit_reporting.manage_jackrabbit_sync"):
        raise PermissionDenied
    if not settings.JACKRABBIT_REPORTING_ENABLED:
        messages.error(request, "Jackrabbit reporting is disabled in server configuration.")
        return redirect("jackrabbit_reporting:dashboard")
    try:
        run = sync_classes()
    except ClassFeedError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            f"Class feed refreshed: {run.fetched_count} classes, {run.created_count} new, "
            f"{run.updated_count} updated, and {run.deactivated_count} retired from the current list.",
        )
    return redirect("jackrabbit_reporting:dashboard")
