from datetime import datetime, time, timedelta

from django.conf import settings
from django.db.models import Max, Min
from django.utils import timezone

from jackrabbit_reporting.models import ClassSyncRun, JackrabbitClass, JackrabbitEvent
from jackrabbit_reporting.security import usable_webhook_token
from jackrabbit_reporting.services.schedule import (
    schedule_classes,
    schedule_scope_display,
    schedule_window,
)


PERIOD_CHOICES = {7: "7 days", 30: "30 days", 90: "90 days", 365: "12 months"}


def _reporting_events():
    return JackrabbitEvent.objects.filter(
        organization_id=str(settings.JACKRABBIT_ORG_ID).strip()
    )


def resolve_period(value):
    try:
        requested = int(value)
    except (TypeError, ValueError):
        requested = 30
    return requested if requested in PERIOD_CHOICES else 30


def _coverage_for(event_types):
    event_types = tuple(event_types)
    rows = {
        row["event_type"]: row
        for row in _reporting_events()
        .filter(event_type__in=event_types)
        .values("event_type")
        .annotate(
            earliest_event=Min("occurred_at"),
            first_received=Min("received_at"),
        )
    }
    if not set(event_types).issubset(rows):
        return None
    earliest_event = max(
        rows[event_type]["earliest_event"] for event_type in event_types
    )
    first_received = max(
        rows[event_type]["first_received"] for event_type in event_types
    )
    return {
        # A combined metric cannot predate the newest of its required feeds.
        "earliest_event": earliest_event,
        "first_received": first_received,
        # A historical occurrence delivered today is not proof that the
        # intervening period was completely backfilled.
        "coverage_start": max(earliest_event, first_received),
    }


def _metric_result(label, note, coverage, current, previous, start, previous_start):
    if coverage is None:
        return {
            "label": label,
            "available": False,
            "value": None,
            "previous": None,
            "comparison_available": False,
            "period_partial": False,
            "earliest_event": None,
            "coverage_start": None,
            "note": note,
        }
    comparison_available = coverage["coverage_start"] <= previous_start
    return {
        "label": label,
        "available": True,
        "value": current,
        "previous": previous if comparison_available else None,
        "comparison_available": comparison_available,
        "period_partial": coverage["coverage_start"] > start,
        "earliest_event": coverage["earliest_event"],
        "coverage_start": coverage["coverage_start"],
        "note": note,
    }


def _metric(label, event_types, current_qs, previous_qs, start, previous_start, note):
    event_types = tuple(event_types)
    coverage = _coverage_for(event_types)
    current = current_qs.filter(event_type__in=event_types).count() if coverage else None
    previous = previous_qs.filter(event_type__in=event_types).count() if coverage else None
    return _metric_result(
        label,
        note,
        coverage,
        current,
        previous,
        start,
        previous_start,
    )


def _net_metric(
    label,
    positive_type,
    negative_type,
    current_qs,
    previous_qs,
    start,
    previous_start,
    note,
):
    coverage = _coverage_for((positive_type, negative_type))
    current = None
    previous = None
    if coverage:
        current = current_qs.filter(event_type=positive_type).count() - current_qs.filter(
            event_type=negative_type
        ).count()
        previous = previous_qs.filter(event_type=positive_type).count() - previous_qs.filter(
            event_type=negative_type
        ).count()
    return _metric_result(label, note, coverage, current, previous, start, previous_start)


def _churn_signal_metric(current_qs, previous_qs, start, previous_start):
    event_types = (JackrabbitEvent.STUDENT_DROPPED, JackrabbitEvent.STUDENT_INACTIVE)
    coverage = _coverage_for(event_types)
    note = "Distinct students with a drop or inactive signal; this is not confirmed customer churn."
    current = None
    previous = None
    if coverage:
        current = (
            current_qs.filter(event_type__in=event_types)
            .exclude(student_id="")
            .values("student_id")
            .distinct()
            .count()
        )
        previous = (
            previous_qs.filter(event_type__in=event_types)
            .exclude(student_id="")
            .values("student_id")
            .distinct()
            .count()
        )
    return _metric_result(
        "Students with churn signals",
        note,
        coverage,
        current,
        previous,
        start,
        previous_start,
    )


def _bucket_key(moment, period_days):
    local_date = timezone.localtime(moment).date()
    if period_days <= 7:
        return local_date
    if period_days <= 90:
        return local_date - timedelta(days=local_date.weekday())
    return local_date.replace(day=1)


def _bucket_label(bucket, period_days):
    if period_days <= 7:
        return bucket.strftime("%a %m/%d")
    if period_days <= 90:
        return "Week of " + bucket.strftime("%m/%d")
    return bucket.strftime("%b %Y")


def _next_bucket(bucket, period_days):
    if period_days <= 7:
        return bucket + timedelta(days=1)
    if period_days <= 90:
        return bucket + timedelta(days=7)
    if bucket.month == 12:
        return bucket.replace(year=bucket.year + 1, month=1)
    return bucket.replace(month=bucket.month + 1)


def _trend(events, period_days, series, start, end):
    connected_series = []
    for key, label in series:
        coverage = _coverage_for((key,))
        if coverage:
            connected_series.append((key, label, coverage["coverage_start"]))
    if not connected_series:
        return []

    first_bucket = _bucket_key(start, period_days)
    last_bucket = _bucket_key(end, period_days)
    buckets = {}
    bucket = first_bucket
    while bucket <= last_bucket:
        buckets[bucket] = {key: 0 for key, _label, _coverage in connected_series}
        bucket = _next_bucket(bucket, period_days)

    for event_type, occurred_at in events:
        bucket = _bucket_key(occurred_at, period_days)
        if bucket not in buckets:
            continue
        for key, _label, _coverage in connected_series:
            if event_type == key and key in buckets[bucket]:
                buckets[bucket][key] += 1
                break

    rows = []
    maximum = max(
        (value for counts in buckets.values() for value in counts.values()),
        default=0,
    )
    for bucket in sorted(buckets):
        values = []
        bucket_end = _next_bucket(bucket, period_days)
        current_timezone = timezone.get_current_timezone()
        bucket_start_at = timezone.make_aware(
            datetime.combine(bucket, time.min), current_timezone
        )
        bucket_end_at = timezone.make_aware(
            datetime.combine(bucket_end, time.min), current_timezone
        )
        window_start_at = timezone.localtime(start, current_timezone)
        window_end_at = timezone.localtime(end, current_timezone)
        partial_window_bucket = (
            bucket_start_at < window_start_at or bucket_end_at > window_end_at
        )
        for key, label, coverage_start in connected_series:
            value = buckets[bucket][key]
            coverage_at = timezone.localtime(coverage_start, current_timezone)
            coverage_verified = coverage_at < bucket_end_at
            unverified = value > 0 and not coverage_verified
            available = coverage_verified or unverified
            values.append(
                {
                    "label": label,
                    "available": available,
                    "unverified": unverified,
                    "partial": available
                    and (
                        unverified
                        or coverage_at >= bucket_start_at
                        or partial_window_bucket
                    ),
                    "value": value if available else None,
                    "percent": round((value / maximum) * 100) if available and maximum else 0,
                }
            )
        rows.append({"label": _bucket_label(bucket, period_days), "values": values})
    return rows


def class_reporting_summary(now=None):
    now = now or timezone.now()
    today = timezone.localdate(now)
    window_start, window_end = schedule_window(today)
    organization_id = str(settings.JACKRABBIT_ORG_ID).strip()
    organization_runs = ClassSyncRun.objects.filter(organization_id=organization_id)
    successful_sync = organization_runs.filter(status=ClassSyncRun.SUCCESS).first()
    latest_sync = organization_runs.first()
    stale = True
    if successful_sync and successful_sync.finished_at:
        stale_after = timedelta(minutes=settings.JACKRABBIT_CLASS_STALE_AFTER_MINUTES)
        stale = successful_sync.finished_at < now - stale_after
    latest_sync_failed = bool(
        latest_sync
        and latest_sync.status == ClassSyncRun.FAILED
        and (not successful_sync or latest_sync.started_at > successful_sync.started_at)
    )
    current_classes = JackrabbitClass.objects.filter(
        organization_id=organization_id,
        is_current=True,
    )
    classes = schedule_classes(current_classes, today)
    class_objects = list(
        classes.only(
            "id",
            "waitlist",
            "is_per_day",
            "calculated_openings",
            "openings_by_day",
            "meeting_days",
            "tuition",
            "tuition_by_day",
        )
    )
    availability_states = [class_record.availability_state for class_record in class_objects]
    return {
        "available": successful_sync is not None,
        "count": len(class_objects),
        "with_openings": availability_states.count("open"),
        "waitlist": availability_states.count("warning"),
        "with_tuition": sum(
            class_record.tuition is not None or bool(class_record.tuition_by_day)
            for class_record in class_objects
        ),
        "schedule_year_start": window_start.year,
        "schedule_year_end": window_end.year,
        "pending_confirmation": current_classes.filter(missed_syncs__gt=0).count(),
        "last_success": successful_sync.finished_at if successful_sync else None,
        "last_run": latest_sync,
        "stale": stale,
        "latest_sync_failed": latest_sync_failed,
        "sync_enabled": settings.JACKRABBIT_REPORTING_ENABLED,
    }


def dashboard_data(period_days=30):
    period_days = resolve_period(period_days)
    now = timezone.now()
    start = now - timedelta(days=period_days)
    previous_start = start - timedelta(days=period_days)
    reporting_events = _reporting_events()
    current_qs = reporting_events.filter(
        occurred_at__gte=start,
        occurred_at__lte=now,
    )
    previous_qs = reporting_events.filter(
        occurred_at__gte=previous_start,
        occurred_at__lt=start,
    )

    customer_metrics = [
        _metric("New families", (JackrabbitEvent.FAMILY_CREATED,), current_qs, previous_qs, start, previous_start, "New customer accounts, not all active families."),
        _metric("New contacts", (JackrabbitEvent.CONTACT_CREATED,), current_qs, previous_qs, start, previous_start, "Adult/contact records created in Jackrabbit."),
        _metric("New students", (JackrabbitEvent.STUDENT_CREATED,), current_qs, previous_qs, start, previous_start, "Participant records created in Jackrabbit."),
        _metric("New leads", (JackrabbitEvent.LEAD_CREATED,), current_qs, previous_qs, start, previous_start, "Families moved into the Jackrabbit Lead File."),
    ]
    enrollment_metrics = [
        _metric("Enrollments", (JackrabbitEvent.STUDENT_ENROLLED,), current_qs, previous_qs, start, previous_start, "Class enrollment events in the selected period."),
        _metric("Drops", (JackrabbitEvent.STUDENT_DROPPED,), current_qs, previous_qs, start, previous_start, "Class drops; one student can have more than one."),
        _net_metric("Net enrollment activity", JackrabbitEvent.STUDENT_ENROLLED, JackrabbitEvent.STUDENT_DROPPED, current_qs, previous_qs, start, previous_start, "Enrollments minus drops; not total active enrollment."),
    ]
    waitlist_metrics = [
        _metric("Waitlist additions", (JackrabbitEvent.WAITLIST_ADDED,), current_qs, previous_qs, start, previous_start, "Additions during the selected period."),
        _metric("Waitlist removals", (JackrabbitEvent.WAITLIST_REMOVED,), current_qs, previous_qs, start, previous_start, "Removals during the selected period."),
        _net_metric("Net waitlist activity", JackrabbitEvent.WAITLIST_ADDED, JackrabbitEvent.WAITLIST_REMOVED, current_qs, previous_qs, start, previous_start, "Additions minus removals; not the current waitlist size."),
        _metric("Students marked inactive", (JackrabbitEvent.STUDENT_INACTIVE,), current_qs, previous_qs, start, previous_start, "A retention signal, not a confirmed reason for leaving."),
        _churn_signal_metric(current_qs, previous_qs, start, previous_start),
    ]

    trend_types = {
        JackrabbitEvent.FAMILY_CREATED,
        JackrabbitEvent.CONTACT_CREATED,
        JackrabbitEvent.STUDENT_CREATED,
        JackrabbitEvent.STUDENT_ENROLLED,
        JackrabbitEvent.STUDENT_DROPPED,
    }
    trend_events = list(
        current_qs.filter(event_type__in=trend_types).values_list("event_type", "occurred_at")
    )

    coverage = []
    for value, label in JackrabbitEvent.EVENT_TYPES:
        summary = reporting_events.filter(event_type=value).aggregate(
            first_event=Min("occurred_at"),
            first_received=Min("received_at"),
            last_event=Max("occurred_at"),
            last_received=Max("received_at"),
        )
        coverage.append(
            {
                "event_type": value,
                "label": label,
                "connected": summary["first_received"] is not None,
                **summary,
            }
        )

    organization_id = str(settings.JACKRABBIT_ORG_ID).strip()
    classes = schedule_classes(
        JackrabbitClass.objects.filter(
            organization_id=organization_id,
            is_current=True,
        ),
        timezone.localdate(now),
    )
    class_summary = class_reporting_summary(now)
    class_preview = list(classes.order_by("start_time", "name", "pk")[:8])
    for class_record in class_preview:
        class_record.schedule_scope_display = schedule_scope_display(
            class_record,
            timezone.localdate(now),
        )

    overall = reporting_events.aggregate(
        first_event=Min("occurred_at"),
        first_received=Min("received_at"),
        last_received=Max("received_at"),
    )
    return {
        "period_days": period_days,
        "period_label": PERIOD_CHOICES[period_days],
        "period_choices": PERIOD_CHOICES,
        "period_start": start,
        "period_end": now,
        "metric_groups": (
            {"title": "Customer growth", "metrics": customer_metrics},
            {"title": "Enrollment movement", "metrics": enrollment_metrics},
            {"title": "Waitlist and retention", "metrics": waitlist_metrics},
        ),
        "customer_trend": _trend(
            trend_events,
            period_days,
            (
                (JackrabbitEvent.FAMILY_CREATED, "Families"),
                (JackrabbitEvent.CONTACT_CREATED, "Contacts"),
                (JackrabbitEvent.STUDENT_CREATED, "Students"),
            ),
            start,
            now,
        ),
        "enrollment_trend": _trend(
            trend_events,
            period_days,
            (
                (JackrabbitEvent.STUDENT_ENROLLED, "Enrolled"),
                (JackrabbitEvent.STUDENT_DROPPED, "Dropped"),
            ),
            start,
            now,
        ),
        "coverage": coverage,
        "earliest_event": overall["first_event"],
        "first_delivery_received": overall["first_received"],
        "last_event_received": overall["last_received"],
        "webhook_enabled": bool(
            settings.JACKRABBIT_REPORTING_ENABLED
            and usable_webhook_token(settings.JACKRABBIT_WEBHOOK_TOKEN)
        ),
        "reporting_enabled": settings.JACKRABBIT_REPORTING_ENABLED,
        "class_summary": class_summary,
        "class_preview": class_preview,
    }
