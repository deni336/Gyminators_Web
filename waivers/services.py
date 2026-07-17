"""Transactional profile/snapshot operations for the public waiver flow."""

import hashlib
import hmac
import ipaddress
import logging
import time
import uuid
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.db import IntegrityError, transaction
from django.utils import timezone

from .constants import CAMP, get_agreement
from .models import (
    AuthorizedPickupProfile,
    EmergencyContactProfile,
    GuardianProfile,
    GymnastProfile,
    ReturningSearchThrottle,
    StoredWaiverPDF,
    Waiver,
    WaiverSubmissionThrottle,
)
from .pdf import render_waiver_pdf


logger = logging.getLogger(__name__)

PROFILE_TOKEN_SALT = "waivers.returning-profile.v1"
SUBMISSION_TOKEN_SALT = "waivers.submission.v1"
SUBMISSION_TOKEN_MAX_AGE = 2 * 60 * 60
# The returning-profile URL remains in the browser while the guardian reads and
# completes the form. Keep it valid for the same window as the signed submission
# token so a legitimate POST cannot expire earlier than the form itself.
PROFILE_TOKEN_MAX_AGE = SUBMISSION_TOKEN_MAX_AGE
SEARCH_SESSION_KEY = "waiver_returning_search_attempts"
SEARCH_MAX_ATTEMPTS = 5
SEARCH_WINDOW_SECONDS = 10 * 60
SEARCH_IP_MAX_ATTEMPTS = 20
SEARCH_RESULT_LIMIT = 5
# Shared households may legitimately retry several forms. Thirty signing POSTs
# per public IP in ten minutes is high enough for that case while bounding CPU
# and storage abuse from fresh sessions and one-time tokens.
SUBMISSION_IP_MAX_ATTEMPTS = 30
SUBMISSION_IP_WINDOW_SECONDS = 10 * 60

ENROLLMENT_DETAIL_FIELDS = (
    "activity_name",
    "home_address",
    "city",
    "state",
    "zip_code",
    "gender",
    "home_phone",
    "guardian_occupation",
    "guardian_work_phone",
    "guardian_cell_phone",
    "second_guardian_name",
    "second_guardian_occupation",
    "second_guardian_work_phone",
    "second_guardian_cell_phone",
    "primary_insurance",
    "policy_number",
    "citizen_usa",
    "medical_info",
    "referral_source",
)


def issue_profile_token(profile, enrollment_type):
    return signing.dumps(
        {"profile": str(profile.pk), "enrollment": enrollment_type},
        salt=PROFILE_TOKEN_SALT,
        compress=True,
    )


def read_profile_token(token, enrollment_type, *, max_age=PROFILE_TOKEN_MAX_AGE):
    payload = signing.loads(token, salt=PROFILE_TOKEN_SALT, max_age=max_age)
    if payload.get("enrollment") != enrollment_type:
        raise signing.BadSignature("Enrollment type does not match.")
    try:
        return uuid.UUID(payload["profile"])
    except (KeyError, TypeError, ValueError) as exc:
        raise signing.BadSignature("Invalid profile token.") from exc


def issue_submission_token(enrollment_type, participant_status, profile_id=None):
    return signing.dumps(
        {
            "nonce": uuid.uuid4().hex,
            "enrollment": enrollment_type,
            "status": participant_status,
            "profile": str(profile_id) if profile_id else "",
        },
        salt=SUBMISSION_TOKEN_SALT,
        compress=True,
    )


def submission_key(
    token,
    *,
    enrollment_type,
    participant_status,
    profile_id=None,
    max_age=SUBMISSION_TOKEN_MAX_AGE,
):
    payload = signing.loads(token, salt=SUBMISSION_TOKEN_SALT, max_age=max_age)
    expected_profile = str(profile_id) if profile_id else ""
    if (
        payload.get("enrollment") != enrollment_type
        or payload.get("status") != participant_status
        or payload.get("profile", "") != expected_profile
        or not payload.get("nonce")
    ):
        raise signing.BadSignature("Submission token does not match this form.")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def search_is_throttled(session, *, now=None):
    now = time.time() if now is None else now
    cutoff = now - SEARCH_WINDOW_SECONDS
    attempts = [
        float(value)
        for value in session.get(SEARCH_SESSION_KEY, [])
        if isinstance(value, (int, float)) and float(value) >= cutoff
    ]
    session[SEARCH_SESSION_KEY] = attempts
    return len(attempts) >= SEARCH_MAX_ATTEMPTS


def record_search_attempt(session, *, now=None):
    now = time.time() if now is None else now
    cutoff = now - SEARCH_WINDOW_SECONDS
    attempts = [
        float(value)
        for value in session.get(SEARCH_SESSION_KEY, [])
        if isinstance(value, (int, float)) and float(value) >= cutoff
    ]
    attempts.append(float(now))
    session[SEARCH_SESSION_KEY] = attempts
    session.modified = True


def normalized_client_ip(request):
    """Use the last valid Caddy-forwarded hop, falling back to REMOTE_ADDR."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    candidates = [item.strip() for item in forwarded.split(",") if item.strip()]
    for candidate in reversed(candidates):
        try:
            return ipaddress.ip_address(candidate).compressed
        except ValueError:
            continue
    remote = request.META.get("REMOTE_ADDR", "").strip()
    try:
        if remote:
            return ipaddress.ip_address(remote).compressed
    except ValueError:
        pass
    return "unavailable"


def client_ip_key(request, *, scope):
    normalized = normalized_client_ip(request).encode("ascii")
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        f"waiver-{scope}-ip-v1\x00".encode("ascii") + normalized,
        hashlib.sha256,
    ).hexdigest()


def _consume_central_bucket(*, model, key, maximum, window_seconds, now):
    cutoff = now - timedelta(seconds=window_seconds)
    stale = now - timedelta(days=1)
    model.objects.filter(updated_at__lt=stale).delete()
    with transaction.atomic():
        bucket, _created = model.objects.select_for_update().get_or_create(
            client_key=key,
            defaults={"window_started_at": now, "attempts": 0},
        )
        if bucket.window_started_at < cutoff:
            bucket.window_started_at = now
            bucket.attempts = 0
        if bucket.attempts >= maximum:
            return False
        bucket.attempts += 1
        bucket.save(update_fields=("window_started_at", "attempts", "updated_at"))
    return True


def consume_search_attempt(request, *, now=None):
    """Atomically consume both the per-session and central per-IP allowance."""
    database_now = timezone.now() if now is None else now
    session_now = database_now.timestamp()
    if search_is_throttled(request.session, now=session_now):
        return False

    now = database_now
    key = client_ip_key(request, scope="returning-search")
    if not _consume_central_bucket(
        model=ReturningSearchThrottle,
        key=key,
        maximum=SEARCH_IP_MAX_ATTEMPTS,
        window_seconds=SEARCH_WINDOW_SECONDS,
        now=now,
    ):
        return False

    record_search_attempt(request.session, now=session_now)
    return True


def consume_submission_attempt(request, *, now=None):
    """Bound signing POST work before any signature decoding or form validation."""
    now = timezone.now() if now is None else now
    return _consume_central_bucket(
        model=WaiverSubmissionThrottle,
        key=client_ip_key(request, scope="submission"),
        maximum=SUBMISSION_IP_MAX_ATTEMPTS,
        window_seconds=SUBMISSION_IP_WINDOW_SECONDS,
        now=now,
    )


def age_on_date(date_of_birth, on_date=None):
    on_date = timezone.localdate() if on_date is None else on_date
    return on_date.year - date_of_birth.year - (
        (on_date.month, on_date.day) < (date_of_birth.month, date_of_birth.day)
    )


def _enrollment_details(cleaned_data):
    return {name: cleaned_data.get(name, "") for name in ENROLLMENT_DETAIL_FIELDS if name in cleaned_data}


def _initials(cleaned_data, agreement):
    return {
        str(number): cleaned_data[f"initial_{number}"]
        for number in range(1, agreement.clause_count + 1)
    }


def _guardian_details(cleaned_data):
    return {
        "first_name": cleaned_data["guardian_first_name"],
        "last_name": cleaned_data["guardian_last_name"],
        "phone": cleaned_data["guardian_phone"],
        "email": cleaned_data["guardian_email"].lower(),
        "occupation": cleaned_data.get("guardian_occupation", ""),
        "work_phone": cleaned_data.get("guardian_work_phone", ""),
        "cell_phone": cleaned_data.get("guardian_cell_phone", ""),
        "second_guardian_name": cleaned_data.get("second_guardian_name", ""),
        "second_guardian_occupation": cleaned_data.get("second_guardian_occupation", ""),
        "second_guardian_work_phone": cleaned_data.get("second_guardian_work_phone", ""),
        "second_guardian_cell_phone": cleaned_data.get("second_guardian_cell_phone", ""),
    }


def _pickup_details(cleaned_data):
    return {
        "first_name": cleaned_data["pickup_first_name"],
        "last_name": cleaned_data["pickup_last_name"],
        "phone": cleaned_data["pickup_phone"],
    }


def _signing_details(cleaned_data, *, participant_status):
    return {
        "typed_signer_name": cleaned_data["typed_signer_name"],
        "signer_capacity": cleaned_data["signer_capacity"],
        "agreement_accepted": bool(cleaned_data["agreement_accepted"]),
        "pickup_verified": bool(cleaned_data.get("pickup_verified", False)),
        "participant_status": participant_status,
    }


def _find_idempotent_waiver(key):
    return Waiver.objects.filter(submission_key=key).first()


def ensure_stored_waiver_pdf(waiver):
    """Create and validate the one immutable artifact for a signed waiver."""
    existing = StoredWaiverPDF.objects.filter(waiver_id=waiver.pk).first()
    if existing:
        existing.validated_content()
        return existing, False

    content = render_waiver_pdf(waiver)
    try:
        # The savepoint keeps a concurrent one-to-one insert from breaking an
        # outer signing or backfill transaction.
        with transaction.atomic():
            artifact = StoredWaiverPDF(waiver=waiver, pdf_bytes=content)
            artifact.save(force_insert=True)
    except IntegrityError:
        artifact = StoredWaiverPDF.objects.get(waiver_id=waiver.pk)
        return artifact, False
    return artifact, True


def _existing_waiver_with_artifact(waiver):
    with transaction.atomic():
        ensure_stored_waiver_pdf(waiver)
    return waiver, False


def create_new_waiver(*, cleaned_data, enrollment_type):
    agreement = get_agreement(enrollment_type)
    key = submission_key(
        cleaned_data["submission_token"],
        enrollment_type=enrollment_type,
        participant_status=Waiver.NEW,
    )
    existing = _find_idempotent_waiver(key)
    if existing:
        return _existing_waiver_with_artifact(existing)

    try:
        with transaction.atomic():
            existing = _find_idempotent_waiver(key)
            if existing:
                ensure_stored_waiver_pdf(existing)
                return existing, False

            gymnast = GymnastProfile.objects.create(
                first_name=cleaned_data["gymnast_first_name"],
                last_name=cleaned_data["gymnast_last_name"],
                date_of_birth=cleaned_data["gymnast_dob"],
                age=cleaned_data["gymnast_age"],
            )
            guardian_data = _guardian_details(cleaned_data)
            guardian = GuardianProfile.objects.create(gymnast=gymnast, **guardian_data)
            emergency_data = {
                "first_name": cleaned_data["emergency_first_name"],
                "last_name": cleaned_data["emergency_last_name"],
                "relationship": cleaned_data["emergency_relationship"],
                "phone": cleaned_data["emergency_phone"],
            }
            emergency = EmergencyContactProfile.objects.create(gymnast=gymnast, **emergency_data)
            pickup_data = _pickup_details(cleaned_data)
            pickup = AuthorizedPickupProfile.objects.create(gymnast=gymnast, **pickup_data)
            details = {
                "gymnast": {
                    "first_name": gymnast.first_name,
                    "last_name": gymnast.last_name,
                    "date_of_birth": gymnast.date_of_birth.isoformat(),
                    "age": gymnast.age,
                },
                "guardian": guardian_data,
                "emergency_contact": emergency_data,
                "authorized_pickup": pickup_data,
                "enrollment": _enrollment_details(cleaned_data),
                "signing": _signing_details(cleaned_data, participant_status=Waiver.NEW),
            }
            waiver = Waiver(
                gymnast=gymnast,
                guardian=guardian,
                emergency_contact=emergency,
                authorized_pickup=pickup,
                participant_status=Waiver.NEW,
                enrollment_type=enrollment_type,
                activity_name=cleaned_data.get("activity_name", ""),
                typed_signer_name=cleaned_data["typed_signer_name"],
                signer_capacity=cleaned_data["signer_capacity"],
                pickup_verified=False,
                agreement_accepted=True,
                agreement_version=agreement.version,
                legal_text_snapshot=agreement.text,
                initials=_initials(cleaned_data, agreement),
                details=details,
                signature_png=cleaned_data["signature_png"],
                submission_key=key,
            )
            waiver.save()
            ensure_stored_waiver_pdf(waiver)
    except IntegrityError:
        existing = _find_idempotent_waiver(key)
        if existing:
            return _existing_waiver_with_artifact(existing)
        raise

    logger.info(
        "waiver created",
        extra={
            "action": "waiver_created",
            "waiver_id": str(waiver.pk),
            "enrollment_type": enrollment_type,
            "participant_status": Waiver.NEW,
        },
    )
    return waiver, True


def create_returning_waiver(*, profile_id, cleaned_data, enrollment_type):
    agreement = get_agreement(enrollment_type)
    key = submission_key(
        cleaned_data["submission_token"],
        enrollment_type=enrollment_type,
        participant_status=Waiver.RETURNING,
        profile_id=profile_id,
    )
    existing = _find_idempotent_waiver(key)
    if existing:
        return _existing_waiver_with_artifact(existing)

    try:
        with transaction.atomic():
            existing = _find_idempotent_waiver(key)
            if existing:
                ensure_stored_waiver_pdf(existing)
                return existing, False

            gymnast = GymnastProfile.objects.select_for_update().get(pk=profile_id)
            current_age = age_on_date(gymnast.date_of_birth)
            if gymnast.age != current_age:
                gymnast.age = current_age
                gymnast.save(update_fields=("age", "updated_at"))
            guardian_data = _guardian_details(cleaned_data)
            pickup_data = _pickup_details(cleaned_data)
            emergency_data = {
                "first_name": cleaned_data["emergency_first_name"],
                "last_name": cleaned_data["emergency_last_name"],
                "relationship": cleaned_data["emergency_relationship"],
                "phone": cleaned_data["emergency_phone"],
            }
            details = {
                "gymnast": {
                    "first_name": gymnast.first_name,
                    "last_name": gymnast.last_name,
                    "date_of_birth": gymnast.date_of_birth.isoformat(),
                    "age": gymnast.age,
                },
                "guardian": guardian_data,
                "emergency_contact": emergency_data,
                "authorized_pickup": pickup_data,
                "enrollment": _enrollment_details(cleaned_data),
                "signing": _signing_details(cleaned_data, participant_status=Waiver.RETURNING),
            }
            waiver = Waiver(
                gymnast=gymnast,
                # Returning lookup is association, not guardian authentication.
                # Signed contact values live only in the immutable snapshot.
                guardian=None,
                emergency_contact=None,
                authorized_pickup=None,
                participant_status=Waiver.RETURNING,
                enrollment_type=enrollment_type,
                activity_name=cleaned_data.get("activity_name", ""),
                typed_signer_name=cleaned_data["typed_signer_name"],
                signer_capacity=cleaned_data["signer_capacity"],
                pickup_verified=True,
                agreement_accepted=True,
                agreement_version=agreement.version,
                legal_text_snapshot=agreement.text,
                initials=_initials(cleaned_data, agreement),
                details=details,
                signature_png=cleaned_data["signature_png"],
                submission_key=key,
            )
            waiver.save()
            ensure_stored_waiver_pdf(waiver)
    except IntegrityError:
        existing = _find_idempotent_waiver(key)
        if existing:
            return _existing_waiver_with_artifact(existing)
        raise

    logger.info(
        "waiver created",
        extra={
            "action": "waiver_created",
            "waiver_id": str(waiver.pk),
            "enrollment_type": enrollment_type,
            "participant_status": Waiver.RETURNING,
        },
    )
    return waiver, True
