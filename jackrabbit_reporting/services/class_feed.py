import html
import json
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time

from jackrabbit_reporting.models import ClassSyncRun, JackrabbitClass


CLASS_FEED_URL = "https://app.jackrabbitclass.com/jr3.0/Openings/OpeningsJson"
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_CLASS_RECORDS = 5000


class ClassFeedError(RuntimeError):
    pass


def _organization_id(value):
    value = str(value or "").strip()
    if not value or len(value) > 20 or not value.isdigit():
        raise ClassFeedError("A valid numeric Jackrabbit organization ID is required.")
    return value


@contextmanager
def _organization_sync_lock(organization_id):
    """Prevent overlapping production syncs without adding another service."""
    if connection.vendor != "postgresql":
        yield
        return
    lock_name = f"gyminators-jackrabbit-classes:{organization_id}"
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(hashtext(%s))", [lock_name])
        acquired = cursor.fetchone()[0]
    if not acquired:
        raise ClassFeedError("A Jackrabbit class synchronization is already running.")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(hashtext(%s))", [lock_name])


def _limited_string(value, limit):
    return str(value or "").strip()[:limit]


def _integer(value, field="value"):
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ClassFeedError(f"The class feed contained an invalid {field}.")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ClassFeedError(f"The class feed contained an invalid {field}.") from exc


def _decimal(value, field="value"):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ClassFeedError(f"The class feed contained an invalid {field}.") from exc


def _required_dict(value, field):
    if not isinstance(value, dict):
        raise ClassFeedError(f"The class feed contained an invalid {field} object.")
    return value


def _required_string(value, field, limit):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ClassFeedError(f"The class feed contained an invalid {field}.")
    value = str(value or "").strip()
    if not value:
        raise ClassFeedError(f"The class feed contained a class without {field}.")
    if len(value) > limit:
        raise ClassFeedError(f"The class feed contained {field} longer than expected.")
    return value


def _date(value, field):
    value = str(value or "").strip()
    if not value:
        return None
    parsed = parse_date(value)
    if parsed is None:
        raise ClassFeedError(f"The class feed contained an invalid {field}.")
    return parsed


def _time(value, field):
    value = str(value or "").strip()
    if not value:
        return None
    parsed = parse_time(value)
    if parsed is None:
        raise ClassFeedError(f"The class feed contained an invalid {field}.")
    return parsed


def _boolean(value, field, default=None):
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ClassFeedError(f"The class feed contained an invalid {field} flag.")
    return value


def _registration_url(value):
    candidate = html.unescape(str(value or "").strip())
    if not candidate:
        return ""
    parsed = urlsplit(candidate)
    hostname = (parsed.hostname or "").lower()
    if (
        len(candidate) > 1000
        or parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or not (hostname == "jackrabbitclass.com" or hostname.endswith(".jackrabbitclass.com"))
    ):
        return ""
    return candidate


def normalize_class_row(row):
    if not isinstance(row, dict):
        raise ClassFeedError("The class feed contained a non-object row.")
    external_id = _required_string(row.get("id"), "a class ID", 100)
    name = _required_string(row.get("name"), "a class name", 240)
    openings = _required_dict(row.get("openings"), "openings")
    tuition = _required_dict(row.get("tuition"), "tuition")
    raw_meeting_days = _required_dict(row.get("meeting_days"), "meeting-days")
    meeting_days = {
        key: _boolean(raw_meeting_days.get(key), f"meeting day {key}", default=False)
        for key, _label in JackrabbitClass.DAY_LABELS
    }
    raw_openings_by_day = openings.get("days", {})
    if raw_openings_by_day is None:
        raw_openings_by_day = {}
    raw_openings_by_day = _required_dict(raw_openings_by_day, "per-day openings")
    openings_by_day = {}
    for key, _label in JackrabbitClass.DAY_LABELS:
        if raw_openings_by_day.get(key) not in (None, ""):
            openings_by_day[key] = _integer(
                raw_openings_by_day[key],
                f"opening count for {key}",
            )

    raw_tuition_by_day = tuition.get("days", {})
    if raw_tuition_by_day is None:
        raw_tuition_by_day = {}
    raw_tuition_by_day = _required_dict(raw_tuition_by_day, "per-day tuition")
    tuition_by_day = {}
    for day_number in range(2, 8):
        key = f"day_{day_number}"
        if raw_tuition_by_day.get(key) not in (None, ""):
            amount = _decimal(raw_tuition_by_day[key], f"tuition for {key}")
            tuition_by_day[key] = str(amount)

    registration_url = _registration_url(row.get("online_reg_link"))
    instructors = row.get("instructors", [])
    if instructors is None:
        instructors = []
    if not isinstance(instructors, list):
        raise ClassFeedError("The class feed contained an invalid instructor list.")
    if any(not isinstance(instructor, (str, int)) or isinstance(instructor, bool) for instructor in instructors):
        raise ClassFeedError("The class feed contained an invalid instructor value.")
    instructors = [_limited_string(name, 160) for name in instructors if str(name or "").strip()]

    return {
        "external_id": external_id,
        "name": name,
        "description": _limited_string(row.get("description"), 10000),
        "category1": _limited_string(row.get("category1"), 160),
        "category2": _limited_string(row.get("category2"), 160),
        "category3": _limited_string(row.get("category3"), 160),
        "gender": _limited_string(row.get("gender"), 40),
        "instructors": instructors,
        "location_code": _limited_string(row.get("location_code") or row.get("location"), 80),
        "location_name": _limited_string(row.get("location_name"), 160),
        "location_address1": _limited_string(row.get("location_addr1"), 200),
        "location_address2": _limited_string(row.get("location_addr2"), 200),
        "location_city": _limited_string(row.get("location_city"), 120),
        "location_state": _limited_string(row.get("location_state"), 80),
        "location_postal_code": _limited_string(row.get("location_postalcode"), 30),
        "location_phone": _limited_string(row.get("location_phone"), 40),
        "room": _limited_string(row.get("room"), 120),
        "session": _limited_string(row.get("session"), 160),
        "start_date": _date(row.get("start_date"), "start date"),
        "end_date": _date(row.get("end_date"), "end date"),
        "registration_start_date": _date(row.get("reg_start_date"), "registration start date"),
        "start_time": _time(row.get("start_time"), "start time"),
        "end_time": _time(row.get("end_time"), "end time"),
        "meeting_days": meeting_days,
        "minimum_age": _limited_string(row.get("min_age"), 40),
        "maximum_age": _limited_string(row.get("max_age"), 40),
        "is_per_day": _boolean(row.get("master_class"), "per-day enrollment", default=False),
        "waitlist": _boolean(row.get("waitlist"), "waitlist", default=None),
        "calculated_openings": _integer(openings.get("calculated_openings"), "calculated openings"),
        "openings_by_day": openings_by_day,
        "tuition": _decimal(tuition.get("fee"), "tuition fee"),
        "tuition_by_day": tuition_by_day,
        "billing_cycle": _limited_string(row.get("BillingCycle") or row.get("billing_cycle"), 120),
        "online_registration_url": registration_url,
    }


def fetch_class_rows(organization_id=None, opener=None):
    organization_id = _organization_id(organization_id or settings.JACKRABBIT_ORG_ID)
    payload = json.dumps({"OrgId": organization_id, "ShowClosed": 1}).encode("utf-8")
    request = Request(
        CLASS_FEED_URL,
        data=payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "GyminatorsWebsite/1.0 (+https://www.gyminators.com/)",
        },
        method="POST",
    )
    opener = opener or urlopen
    try:
        with opener(request, timeout=settings.JACKRABBIT_CLASS_SYNC_TIMEOUT_SECONDS) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ClassFeedError("Jackrabbit's class feed could not be reached.") from exc
    if len(body) > MAX_RESPONSE_BYTES:
        raise ClassFeedError("Jackrabbit's class feed response was too large.")
    try:
        result = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ClassFeedError("Jackrabbit's class feed returned invalid JSON.") from exc
    if not isinstance(result, dict) or result.get("success") is not True:
        raise ClassFeedError("Jackrabbit's class feed reported an unsuccessful request.")
    rows = result.get("rows")
    if not isinstance(rows, list):
        raise ClassFeedError("Jackrabbit's class feed did not return a class list.")
    if not rows:
        raise ClassFeedError(
            "Jackrabbit's class feed returned no classes; the last successful copy was preserved."
        )
    if len(rows) > MAX_CLASS_RECORDS:
        raise ClassFeedError("Jackrabbit's class feed returned more records than expected.")
    return rows


def sync_classes(organization_id=None, opener=None):
    organization_id = _organization_id(organization_id or settings.JACKRABBIT_ORG_ID)
    with _organization_sync_lock(organization_id):
        return _sync_classes(organization_id, opener=opener)


def _sync_classes(organization_id, opener=None):
    run = ClassSyncRun.objects.create(organization_id=organization_id)
    try:
        rows = fetch_class_rows(organization_id, opener=opener)
        normalized_rows = [normalize_class_row(row) for row in rows]
        external_ids = [values["external_id"] for values in normalized_rows]
        if len(external_ids) != len(set(external_ids)):
            raise ClassFeedError("Jackrabbit's class feed contained duplicate class IDs.")
        now = timezone.now()
        created_count = 0
        updated_count = 0
        seen_ids = external_ids

        with transaction.atomic():
            for values in normalized_rows:
                external_id = values.pop("external_id")
                existing = JackrabbitClass.objects.filter(
                    organization_id=organization_id,
                    external_id=external_id,
                ).first()
                if existing is None:
                    JackrabbitClass.objects.create(
                        organization_id=organization_id,
                        external_id=external_id,
                        last_seen_at=now,
                        is_current=True,
                        missed_syncs=0,
                        **values,
                    )
                    created_count += 1
                    continue

                changed_fields = []
                for field, value in values.items():
                    if getattr(existing, field) != value:
                        setattr(existing, field, value)
                        changed_fields.append(field)
                if not existing.is_current:
                    existing.is_current = True
                    changed_fields.append("is_current")
                if existing.missed_syncs:
                    existing.missed_syncs = 0
                    changed_fields.append("missed_syncs")
                existing.last_seen_at = now
                changed_fields.append("last_seen_at")
                if changed_fields:
                    existing.save(update_fields=tuple(dict.fromkeys(changed_fields + ["updated_at"])))
                if len(changed_fields) > 1 or changed_fields[0] != "last_seen_at":
                    updated_count += 1

            unseen = JackrabbitClass.objects.filter(
                organization_id=organization_id,
                is_current=True,
            ).exclude(external_id__in=seen_ids)
            unseen.update(missed_syncs=F("missed_syncs") + 1, updated_at=now)
            deactivated_count = unseen.filter(missed_syncs__gte=2).update(
                is_current=False,
                updated_at=now,
            )

            run.status = ClassSyncRun.SUCCESS
            run.finished_at = now
            run.fetched_count = len(normalized_rows)
            run.created_count = created_count
            run.updated_count = updated_count
            run.deactivated_count = deactivated_count
            run.save(
                update_fields=(
                    "status",
                    "finished_at",
                    "fetched_count",
                    "created_count",
                    "updated_count",
                    "deactivated_count",
                )
            )
        return run
    except Exception as exc:
        run.status = ClassSyncRun.FAILED
        run.finished_at = timezone.now()
        run.error_message = str(exc)[:1000]
        run.save(update_fields=("status", "finished_at", "error_message"))
        if isinstance(exc, ClassFeedError):
            raise
        raise ClassFeedError("Jackrabbit class data could not be synchronized.") from exc
