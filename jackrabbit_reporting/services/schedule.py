import calendar
from datetime import date, datetime, time, timedelta

from django.db.models import F, Q
from django.utils import timezone

from jackrabbit_reporting.models import JackrabbitClass


LONG_DAY_LABELS = (
    ("mon", "Monday"),
    ("tue", "Tuesday"),
    ("wed", "Wednesday"),
    ("thu", "Thursday"),
    ("fri", "Friday"),
    ("sat", "Saturday"),
    ("sun", "Sunday"),
)
DAY_KEYS_BY_WEEKDAY = tuple(key for key, _label in LONG_DAY_LABELS)
DEFAULT_MAX_CALENDAR_CLASSES = 250
DEFAULT_MAX_CALENDAR_OCCURRENCES = 5000


def schedule_window(today=None):
    """Return the inclusive two-calendar-year schedule horizon."""
    today = today or timezone.localdate()
    return date(today.year, 1, 1), date(today.year + 1, 12, 31)


def schedule_classes(queryset=None, today=None):
    """Limit cached feed rows to valid schedules starting in the display horizon."""
    window_start, window_end = schedule_window(today)
    queryset = queryset if queryset is not None else JackrabbitClass.objects.all()
    return queryset.filter(
        start_date__gte=window_start,
        start_date__lte=window_end,
    ).filter(Q(end_date__isnull=True) | Q(end_date__gte=F("start_date")))


def classes_active_in_month(queryset, month_start):
    month_end = date(
        month_start.year,
        month_start.month,
        calendar.monthrange(month_start.year, month_start.month)[1],
    )
    return queryset.filter(start_date__lte=month_end).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=month_start)
    )


def selected_schedule_month(raw_value, today=None):
    today = today or timezone.localdate()
    default = date(today.year, today.month, 1)
    try:
        selected = datetime.strptime(str(raw_value or ""), "%Y-%m").date().replace(day=1)
    except (TypeError, ValueError):
        return default
    window_start, window_end = schedule_window(today)
    if selected < window_start or selected > window_end.replace(day=1):
        return default
    return selected


def schedule_month_groups(today=None):
    today = today or timezone.localdate()
    groups = []
    for year in (today.year, today.year + 1):
        groups.append(
            {
                "year": year,
                "months": tuple(
                    {
                        "value": f"{year}-{month:02d}",
                        "label": calendar.month_name[month],
                    }
                    for month in range(1, 13)
                ),
            }
        )
    return tuple(groups)


def adjacent_schedule_month(month_start, offset, today=None):
    absolute_month = month_start.year * 12 + month_start.month - 1 + offset
    adjacent = date(absolute_month // 12, absolute_month % 12 + 1, 1)
    window_start, window_end = schedule_window(today)
    if window_start <= adjacent <= window_end.replace(day=1):
        return adjacent
    return None


def _format_date(value):
    return f"{value.strftime('%b')} {value.day}, {value.year}"


def schedule_scope_display(class_record, today=None):
    window_start, window_end = schedule_window(today)
    visible_start = max(class_record.start_date, window_start)
    if class_record.end_date is None:
        return f"From {_format_date(visible_start)} · ongoing"
    visible_end = min(class_record.end_date, window_end)
    if visible_start == visible_end:
        return _format_date(visible_start)
    suffix = " · continues beyond this calendar" if class_record.end_date > window_end else ""
    return f"{_format_date(visible_start)}–{_format_date(visible_end)}{suffix}"


def day_availability(class_record, day_key):
    if class_record.waitlist is True:
        return class_record.availability_label, "warning"
    if class_record.is_per_day:
        value = class_record.openings_by_day.get(day_key)
        if isinstance(value, int):
            if value <= 0:
                return "Full", "warning"
            return f"{value} open", "open"
        return "Check day availability", "neutral"
    return class_record.availability_label, class_record.availability_state


def _class_sort_key(class_record):
    return (
        class_record.start_time is None,
        class_record.start_time or time.max,
        class_record.name.casefold(),
        class_record.pk,
    )


def build_month_calendar(
    class_records,
    month_start,
    selected_day="",
    availability_state="",
    max_occurrences=None,
    today=None,
):
    """Project recurring class rules into one bounded calendar month."""
    today = today or timezone.localdate()
    window_start, window_end = schedule_window(today)
    calendar_weeks = calendar.Calendar(firstweekday=calendar.MONDAY).monthdatescalendar(
        month_start.year,
        month_start.month,
    )
    cells = []
    cells_by_date = {}
    for week in calendar_weeks:
        for calendar_date in week:
            in_month = calendar_date.month == month_start.month
            cell = {
                "date": calendar_date,
                "in_month": in_month,
                "is_today": in_month and calendar_date == today,
                "occurrences": [],
            }
            cells.append(cell)
            if in_month:
                cells_by_date[calendar_date] = cell

    sorted_classes = sorted(class_records, key=_class_sort_key)
    unscheduled = []
    occurrence_count = 0
    matching_class_ids = set()
    truncated = False
    for class_record in sorted_classes:
        day_keys = [
            key
            for key, _label in LONG_DAY_LABELS
            if class_record.meeting_days.get(key)
            and (not selected_day or selected_day == key)
        ]
        if not day_keys:
            if not selected_day:
                class_state = class_record.availability_state
                if availability_state and class_state != availability_state:
                    continue
                unscheduled.append(
                    {
                        "class_record": class_record,
                        "scope_display": schedule_scope_display(class_record, today),
                    }
                )
                matching_class_ids.add(class_record.pk)
            continue

        month_end = max(cells_by_date)
        active_start = max(class_record.start_date, month_start, window_start)
        active_end = min(class_record.end_date or month_end, month_end, window_end)
        if active_start > active_end:
            continue
        active_day_keys = set(day_keys)
        current_date = active_start
        while current_date <= active_end:
            day_key = DAY_KEYS_BY_WEEKDAY[current_date.weekday()]
            if day_key in active_day_keys:
                availability_label, occurrence_state = day_availability(
                    class_record,
                    day_key,
                )
                if (
                    availability_state
                    and occurrence_state != availability_state
                ):
                    current_date += timedelta(days=1)
                    continue
                if max_occurrences is not None and occurrence_count >= max_occurrences:
                    truncated = True
                    current_date += timedelta(days=1)
                    continue
                cells_by_date[current_date]["occurrences"].append(
                    {
                        "class_record": class_record,
                        "day_key": day_key,
                        "availability_label": availability_label,
                        "availability_state": occurrence_state,
                        "scope_display": schedule_scope_display(class_record, today),
                    }
                )
                occurrence_count += 1
                matching_class_ids.add(class_record.pk)
            current_date += timedelta(days=1)

    return {
        "cells": tuple(cells),
        "unscheduled": tuple(unscheduled),
        "occurrence_count": occurrence_count,
        "class_count": len(matching_class_ids),
        "truncated": truncated,
    }


def class_calendar_context(
    query_params,
    organization_id,
    today=None,
    max_classes=DEFAULT_MAX_CALENDAR_CLASSES,
    max_occurrences=DEFAULT_MAX_CALENDAR_OCCURRENCES,
):
    """Build the shared public/staff class-calendar context from safe GET filters."""
    today = today or timezone.localdate()
    window_start, window_end = schedule_window(today)
    all_classes = schedule_classes(
        JackrabbitClass.objects.filter(
            organization_id=str(organization_id).strip(),
            is_current=True,
        ),
        today,
    )
    selected_month = selected_schedule_month(query_params.get("month"), today)
    classes = classes_active_in_month(all_classes, selected_month)
    query = query_params.get("q", "").strip()[:100]
    location = query_params.get("location", "").strip()[:80]
    session = query_params.get("session", "").strip()[:160]
    category = query_params.get("category", "").strip()[:160]
    day = query_params.get("day", "").strip().lower()
    availability = query_params.get("availability", "").strip().lower()

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
        wanted_availability_state = "open" if availability == "open" else "warning"
    else:
        availability = ""
        wanted_availability_state = ""

    candidate_class_count = classes.count()
    class_records = list(classes.order_by("start_time", "name", "pk")[: max_classes + 1])
    classes_truncated = len(class_records) > max_classes
    if classes_truncated:
        class_records = class_records[:max_classes]
    month_calendar = build_month_calendar(
        class_records,
        selected_month,
        selected_day=day,
        availability_state=wanted_availability_state,
        max_occurrences=max_occurrences,
        today=today,
    )

    def month_url(month):
        if month is None:
            return ""
        copied_params = query_params.copy()
        copied_params["month"] = month.strftime("%Y-%m")
        copied_params.pop("page", None)
        return f"?{copied_params.urlencode()}"

    return {
        "calendar_cells": month_calendar["cells"],
        "calendar_unscheduled": month_calendar["unscheduled"],
        "calendar_occurrence_count": month_calendar["occurrence_count"],
        "class_count": month_calendar["class_count"],
        "candidate_class_count": candidate_class_count,
        "calendar_truncated": classes_truncated or month_calendar["truncated"],
        "calendar_class_limit": max_classes,
        "calendar_occurrence_limit": max_occurrences,
        "selected_month": selected_month,
        "selected_month_value": selected_month.strftime("%Y-%m"),
        "month_groups": schedule_month_groups(today),
        "previous_month_url": month_url(adjacent_schedule_month(selected_month, -1, today)),
        "next_month_url": month_url(adjacent_schedule_month(selected_month, 1, today)),
        "schedule_year_start": window_start.year,
        "schedule_year_end": window_end.year,
        "query": query,
        "selected_location": location,
        "selected_session": session,
        "selected_category": category,
        "selected_day": day,
        "selected_availability": availability,
        "locations": all_classes.exclude(location_code="")
        .values_list("location_code", "location_name")
        .order_by("location_code")
        .distinct(),
        "sessions": all_classes.exclude(session="")
        .values_list("session", flat=True)
        .order_by("session")
        .distinct(),
        "categories": all_classes.exclude(category1="")
        .values_list("category1", flat=True)
        .order_by("category1")
        .distinct(),
        "day_choices": JackrabbitClass.DAY_LABELS,
    }
