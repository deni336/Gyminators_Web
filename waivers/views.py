import logging
import uuid

from django.core import signing
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters

from .constants import AGREEMENTS, get_agreement
from .forms import NewWaiverForm, ReturningSearchForm, ReturningWaiverForm
from .models import GymnastProfile, StoredWaiverPDF, Waiver
from .pdf import flatten_snapshot
from .security import (
    no_sensitive_cache,
    public_waiver_required,
    waiver_view_permission_required,
)
from .services import (
    SEARCH_RESULT_LIMIT,
    consume_search_attempt,
    consume_submission_attempt,
    create_new_waiver,
    create_returning_waiver,
    issue_profile_token,
    issue_submission_token,
    read_profile_token,
)


logger = logging.getLogger(__name__)
CONFIRMATION_SESSION_KEY = "waiver_confirmation_ids"
CONFIRMATION_SESSION_LIMIT = 5


def _agreement_or_404(enrollment_type):
    try:
        return get_agreement(enrollment_type)
    except ValueError as exc:
        raise Http404("Unknown enrollment type.") from exc


def _require_fresh_signature(form):
    """Never reflect a posted signature data URL after a validation failure."""
    data = form.data.copy()
    data["signature_data"] = ""
    form.data = data
    if "signature_data" not in form.errors:
        form.add_error("signature_data", "Please sign again before submitting.")


def _remember_confirmation(request, waiver_id):
    """Bind recent confirmation pages to the browser session that submitted them."""
    confirmation_id = str(waiver_id)
    recent = request.session.get(CONFIRMATION_SESSION_KEY, [])
    recent = [value for value in recent if value != confirmation_id]
    request.session[CONFIRMATION_SESSION_KEY] = [confirmation_id, *recent][
        :CONFIRMATION_SESSION_LIMIT
    ]


def _submission_rate_limited(request):
    response = render(
        request,
        "waivers/rate_limited.html",
        {"message": "Too many signing attempts. Please wait 10 minutes before trying again."},
        status=429,
    )
    response["Retry-After"] = "600"
    return response


@no_sensitive_cache
@public_waiver_required
def start(request):
    return render(
        request,
        "waivers/start.html",
        {"agreements": AGREEMENTS.values()},
    )


@no_sensitive_cache
@public_waiver_required
def gymnast_status(request, enrollment_type):
    agreement = _agreement_or_404(enrollment_type)
    return render(request, "waivers/gymnast_status.html", {"agreement": agreement})


@no_sensitive_cache
@public_waiver_required
@sensitive_post_parameters()
@csrf_protect
def new_waiver(request, enrollment_type):
    agreement = _agreement_or_404(enrollment_type)
    status = 200
    if request.method == "POST":
        if not consume_submission_attempt(request):
            return _submission_rate_limited(request)
        form = NewWaiverForm(request.POST, enrollment_type=enrollment_type)
        if form.is_valid():
            try:
                waiver, _created = create_new_waiver(
                    cleaned_data=form.cleaned_data,
                    enrollment_type=enrollment_type,
                )
            except signing.BadSignature:
                form.add_error(None, "This signing form expired. Reload the page and try again.")
                status = 400
            else:
                _remember_confirmation(request, waiver.pk)
                return redirect("waivers:success", confirmation_id=waiver.pk)
    else:
        form = NewWaiverForm(
            enrollment_type=enrollment_type,
            initial={
                "submission_token": issue_submission_token(
                    enrollment_type,
                    Waiver.NEW,
                )
            },
        )
    if request.method == "POST":
        _require_fresh_signature(form)
    return render(
        request,
        "waivers/waiver_form.html",
        {
            "agreement": agreement,
            "form": form,
            "participant_status": Waiver.NEW,
            "page_title": "New gymnast waiver",
        },
        status=status,
    )


@no_sensitive_cache
@public_waiver_required
@sensitive_post_parameters()
@csrf_protect
def returning_search(request, enrollment_type):
    agreement = _agreement_or_404(enrollment_type)
    results = None
    message = ""
    status = 200
    if request.method == "POST":
        form = ReturningSearchForm(request.POST)
        if not consume_search_attempt(request):
            status = 429
            message = "Too many lookup attempts. Please wait 10 minutes before trying again."
        elif form.is_valid():
            matches = GymnastProfile.objects.returning_matches(
                last_name=form.cleaned_data["gymnast_last_name"],
                date_of_birth=form.cleaned_data["gymnast_dob"],
                phone_last4=form.cleaned_data["guardian_phone_last4"],
                limit=SEARCH_RESULT_LIMIT,
            )
            results = [
                {
                    "label": f"{profile.first_name} {profile.last_name[:1]}.",
                    "birth_year": profile.date_of_birth.year,
                    "url": reverse(
                        "waivers:returning",
                        kwargs={
                            "enrollment_type": enrollment_type,
                            "token": issue_profile_token(profile, enrollment_type),
                        },
                    ),
                }
                for profile in matches
            ]
            if not results:
                message = "No matching gymnast was found. Check all three entries or contact the office."
    else:
        form = ReturningSearchForm()

    response = render(
        request,
        "waivers/returning_search.html",
        {
            "agreement": agreement,
            "form": form,
            "results": results,
            "message": message,
        },
        status=status,
    )
    if status == 429:
        response["Retry-After"] = "600"
    return response


@no_sensitive_cache
@public_waiver_required
@sensitive_post_parameters()
@csrf_protect
def returning_waiver(request, enrollment_type, token):
    agreement = _agreement_or_404(enrollment_type)
    if request.method == "POST" and not consume_submission_attempt(request):
        return _submission_rate_limited(request)
    try:
        profile_id = read_profile_token(token, enrollment_type)
    except signing.BadSignature as exc:
        raise Http404("This returning-gymnast link is invalid or expired.") from exc
    profile = get_object_or_404(
        GymnastProfile.objects.select_related("guardian", "authorized_pickup"),
        pk=profile_id,
    )
    status = 200
    if request.method == "POST":
        form = ReturningWaiverForm(request.POST, enrollment_type=enrollment_type)
        if form.is_valid():
            try:
                waiver, _created = create_returning_waiver(
                    profile_id=profile.pk,
                    cleaned_data=form.cleaned_data,
                    enrollment_type=enrollment_type,
                )
            except signing.BadSignature:
                form.add_error(None, "This signing form expired. Start the lookup again.")
                status = 400
            else:
                _remember_confirmation(request, waiver.pk)
                return redirect("waivers:success", confirmation_id=waiver.pk)
    else:
        form = ReturningWaiverForm(
            enrollment_type=enrollment_type,
            initial={
                "submission_token": issue_submission_token(
                    enrollment_type,
                    Waiver.RETURNING,
                    profile.pk,
                )
            },
        )
    if request.method == "POST":
        _require_fresh_signature(form)
    return render(
        request,
        "waivers/waiver_form.html",
        {
            "agreement": agreement,
            "form": form,
            "participant_status": Waiver.RETURNING,
            "page_title": "Returning gymnast waiver",
            "gymnast_label": f"{profile.first_name} {profile.last_name}",
            "gymnast_dob": profile.date_of_birth,
        },
        status=status,
    )


@no_sensitive_cache
@public_waiver_required
def success(request, confirmation_id):
    # Deliberately do not query the record or disclose any submitted information.
    if str(confirmation_id) not in request.session.get(CONFIRMATION_SESSION_KEY, []):
        raise Http404("This confirmation is not available in this browser session.")
    return render(
        request,
        "waivers/success.html",
        {"confirmation_id": confirmation_id},
    )


@no_sensitive_cache
@waiver_view_permission_required
@sensitive_post_parameters("q")
@csrf_protect
def staff_list(request):
    waivers = Waiver.objects.select_related("gymnast")
    query = request.POST.get("q", "").strip()[:100] if request.method == "POST" else ""
    if query:
        filters = Q(gymnast__first_name__icontains=query) | Q(gymnast__last_name__icontains=query)
        try:
            filters |= Q(pk=uuid.UUID(query))
        except ValueError:
            pass
        waivers = waivers.filter(filters)
    return render(
        request,
        "waivers/staff_list.html",
        {"waivers": waivers[:100], "query": query},
    )


@no_sensitive_cache
@waiver_view_permission_required
def staff_detail(request, waiver_id):
    waiver = get_object_or_404(
        Waiver.objects.select_related("gymnast", "stored_pdf"),
        pk=waiver_id,
    )
    try:
        pdf_artifact = waiver.stored_pdf
    except StoredWaiverPDF.DoesNotExist:
        pdf_artifact = None
    logger.info(
        "waiver detail accessed",
        extra={
            "action": "waiver_detail_accessed",
            "waiver_id": str(waiver.pk),
            "staff_user_id": request.user.pk,
        },
    )
    return render(
        request,
        "waivers/staff_detail.html",
        {
            "waiver": waiver,
            "pdf_artifact": pdf_artifact,
            "snapshot_rows": flatten_snapshot(waiver.details),
        },
    )


@no_sensitive_cache
@waiver_view_permission_required
def staff_pdf(request, waiver_id):
    artifact = get_object_or_404(
        StoredWaiverPDF.objects.select_related("waiver"),
        waiver_id=waiver_id,
    )
    waiver = artifact.waiver
    try:
        content = artifact.validated_content()
    except ValidationError:
        logger.error(
            "stored waiver PDF integrity validation failed",
            extra={
                "action": "waiver_pdf_integrity_failed",
                "waiver_id": str(waiver.pk),
            },
        )
        response = HttpResponse(
            "The stored waiver PDF could not be verified.",
            status=409,
            content_type="text/plain; charset=utf-8",
        )
        response["X-Content-Type-Options"] = "nosniff"
        return response
    logger.info(
        "waiver PDF accessed",
        extra={
            "action": "waiver_pdf_accessed",
            "waiver_id": str(waiver.pk),
            "staff_user_id": request.user.pk,
        },
    )
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="waiver-{waiver.pk}.pdf"'
    response["X-Content-Type-Options"] = "nosniff"
    return response
