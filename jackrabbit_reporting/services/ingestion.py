import hashlib

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware

from jackrabbit_reporting.models import JackrabbitEvent


SCHEMA_VERSION = 1
ALLOWED_FIELDS = {
    "schema_version",
    "event_type",
    "idempotency_key",
    "occurred_at",
    "source",
    "family_id",
    "contact_id",
    "student_id",
    "class_id",
    "enrollment_id",
    "location",
}
FIELD_LIMITS = {
    "family_id": 100,
    "contact_id": 100,
    "student_id": 100,
    "class_id": 100,
    "enrollment_id": 100,
    "location": 160,
}


class EventValidationError(ValueError):
    pass


class EventConflictError(ValueError):
    pass


def _string_value(payload, field):
    value = payload.get(field, "")
    if value is None:
        return ""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise EventValidationError(f"{field} must be a string or integer.")
    value = str(value).strip()
    if len(value) > FIELD_LIMITS[field]:
        raise EventValidationError(f"{field} is too long.")
    return value


def validate_event_payload(payload):
    if not isinstance(payload, dict):
        raise EventValidationError("The request body must be a JSON object.")

    unsupported = sorted(set(payload) - ALLOWED_FIELDS)
    if unsupported:
        raise EventValidationError("Unsupported fields: " + ", ".join(unsupported) + ".")

    if payload.get("schema_version") != SCHEMA_VERSION:
        raise EventValidationError(f"schema_version must be {SCHEMA_VERSION}.")

    event_type = payload.get("event_type")
    if event_type not in JackrabbitEvent.EVENT_TYPE_VALUES:
        raise EventValidationError("Unsupported event_type.")

    idempotency_key = payload.get("idempotency_key")
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise EventValidationError("idempotency_key is required.")
    idempotency_key = idempotency_key.strip()
    if len(idempotency_key) > 500:
        raise EventValidationError("idempotency_key is too long.")

    occurred_at_value = payload.get("occurred_at")
    if not isinstance(occurred_at_value, str):
        raise EventValidationError("occurred_at must be an ISO-8601 timestamp with a timezone.")
    occurred_at = parse_datetime(occurred_at_value.strip())
    if occurred_at is None or not is_aware(occurred_at):
        raise EventValidationError("occurred_at must be an ISO-8601 timestamp with a timezone.")

    source = payload.get("source", JackrabbitEvent.TRIGGER)
    if source not in {value for value, _label in JackrabbitEvent.SOURCES}:
        raise EventValidationError("source must be trigger or backfill.")

    values = {field: _string_value(payload, field) for field in FIELD_LIMITS}
    required_by_event = {
        JackrabbitEvent.FAMILY_CREATED: ("family_id",),
        JackrabbitEvent.LEAD_CREATED: ("family_id",),
        JackrabbitEvent.CONTACT_CREATED: ("contact_id",),
        JackrabbitEvent.STUDENT_CREATED: ("student_id",),
        JackrabbitEvent.STUDENT_INACTIVE: ("student_id",),
        JackrabbitEvent.STUDENT_ENROLLED: ("student_id", "class_id"),
        JackrabbitEvent.STUDENT_DROPPED: ("student_id", "class_id"),
        JackrabbitEvent.WAITLIST_ADDED: ("student_id", "class_id"),
        JackrabbitEvent.WAITLIST_REMOVED: ("student_id", "class_id"),
    }
    missing = [field for field in required_by_event[event_type] if not values[field]]
    if missing:
        raise EventValidationError("Missing required fields: " + ", ".join(missing) + ".")

    organization_id = str(settings.JACKRABBIT_ORG_ID).strip()
    digest_source = f"{organization_id}:{event_type}:{idempotency_key}".encode("utf-8")
    return {
        "organization_id": organization_id,
        "event_type": event_type,
        "source": source,
        "dedupe_hash": hashlib.sha256(digest_source).hexdigest(),
        "occurred_at": occurred_at,
        **values,
    }


def _matches_existing_event(event, values):
    fields = (
        "organization_id",
        "event_type",
        "occurred_at",
        "family_id",
        "contact_id",
        "student_id",
        "class_id",
        "enrollment_id",
        "location",
    )
    return all(getattr(event, field) == values[field] for field in fields)


@transaction.atomic
def ingest_event(payload):
    values = validate_event_payload(payload)
    dedupe_hash = values.pop("dedupe_hash")
    event = JackrabbitEvent.objects.select_for_update().filter(dedupe_hash=dedupe_hash).first()
    if event is None:
        try:
            # The savepoint keeps the outer transaction usable if a concurrent
            # delivery wins the unique-key race.
            with transaction.atomic():
                event = JackrabbitEvent.objects.create(
                    **values,
                    dedupe_hash=dedupe_hash,
                )
        except IntegrityError:
            event = JackrabbitEvent.objects.select_for_update().get(dedupe_hash=dedupe_hash)
        else:
            return event, True

    if not _matches_existing_event(event, values):
        raise EventConflictError(
            "The idempotency key was already used for different event data."
        )
    return event, False
