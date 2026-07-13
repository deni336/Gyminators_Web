import re
import uuid
from decimal import Decimal, InvalidOperation

from django.db import models
from django.utils import timezone


class JackrabbitEvent(models.Model):
    FAMILY_CREATED = "family_created"
    CONTACT_CREATED = "contact_created"
    STUDENT_CREATED = "student_created"
    LEAD_CREATED = "lead_created"
    STUDENT_ENROLLED = "student_enrolled"
    STUDENT_DROPPED = "student_dropped"
    WAITLIST_ADDED = "waitlist_added"
    WAITLIST_REMOVED = "waitlist_removed"
    STUDENT_INACTIVE = "student_inactive"

    EVENT_TYPES = (
        (FAMILY_CREATED, "Family created"),
        (CONTACT_CREATED, "Contact created"),
        (STUDENT_CREATED, "Student created"),
        (LEAD_CREATED, "Lead created"),
        (STUDENT_ENROLLED, "Student enrolled"),
        (STUDENT_DROPPED, "Student dropped"),
        (WAITLIST_ADDED, "Student added to waitlist"),
        (WAITLIST_REMOVED, "Student removed from waitlist"),
        (STUDENT_INACTIVE, "Student inactive"),
    )
    EVENT_TYPE_VALUES = {value for value, _label in EVENT_TYPES}

    TRIGGER = "trigger"
    BACKFILL = "backfill"
    SOURCES = ((TRIGGER, "Zapier trigger"), (BACKFILL, "Zapier search backfill"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization_id = models.CharField(max_length=20, db_index=True)
    event_type = models.CharField(max_length=32, choices=EVENT_TYPES, db_index=True)
    source = models.CharField(max_length=16, choices=SOURCES, default=TRIGGER)
    dedupe_hash = models.CharField(max_length=64, unique=True, editable=False)
    occurred_at = models.DateTimeField(db_index=True)
    received_at = models.DateTimeField(auto_now_add=True)

    family_id = models.CharField(max_length=100, blank=True, db_index=True)
    contact_id = models.CharField(max_length=100, blank=True, db_index=True)
    student_id = models.CharField(max_length=100, blank=True, db_index=True)
    class_id = models.CharField(max_length=100, blank=True, db_index=True)
    enrollment_id = models.CharField(max_length=100, blank=True, db_index=True)
    location = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ("-occurred_at", "-received_at")
        indexes = (
            models.Index(fields=("event_type", "occurred_at"), name="jr_event_type_date"),
            models.Index(fields=("organization_id", "occurred_at"), name="jr_event_org_date"),
        )
        permissions = (("view_reporting_dashboard", "Can view the Jackrabbit reporting dashboard"),)

    def __str__(self):
        return f"{self.get_event_type_display()} at {self.occurred_at:%Y-%m-%d %H:%M}"


class JackrabbitClass(models.Model):
    DAY_LABELS = (
        ("mon", "Mon"),
        ("tue", "Tue"),
        ("wed", "Wed"),
        ("thu", "Thu"),
        ("fri", "Fri"),
        ("sat", "Sat"),
        ("sun", "Sun"),
    )

    organization_id = models.CharField(max_length=20, db_index=True)
    external_id = models.CharField(max_length=100)
    name = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    category1 = models.CharField(max_length=160, blank=True)
    category2 = models.CharField(max_length=160, blank=True)
    category3 = models.CharField(max_length=160, blank=True)
    gender = models.CharField(max_length=40, blank=True)
    instructors = models.JSONField(default=list, blank=True)

    location_code = models.CharField(max_length=80, blank=True)
    location_name = models.CharField(max_length=160, blank=True)
    location_address1 = models.CharField(max_length=200, blank=True)
    location_address2 = models.CharField(max_length=200, blank=True)
    location_city = models.CharField(max_length=120, blank=True)
    location_state = models.CharField(max_length=80, blank=True)
    location_postal_code = models.CharField(max_length=30, blank=True)
    location_phone = models.CharField(max_length=40, blank=True)

    room = models.CharField(max_length=120, blank=True)
    session = models.CharField(max_length=160, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    registration_start_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    meeting_days = models.JSONField(default=dict, blank=True)

    minimum_age = models.CharField(max_length=40, blank=True)
    maximum_age = models.CharField(max_length=40, blank=True)
    is_per_day = models.BooleanField(default=False)
    waitlist = models.BooleanField(null=True, blank=True)
    calculated_openings = models.IntegerField(null=True, blank=True)
    openings_by_day = models.JSONField(default=dict, blank=True)
    tuition = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tuition_by_day = models.JSONField(default=dict, blank=True)
    billing_cycle = models.CharField(max_length=120, blank=True)
    online_registration_url = models.URLField(max_length=1000, blank=True)

    is_current = models.BooleanField(default=True, db_index=True)
    missed_syncs = models.PositiveSmallIntegerField(default=0)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("category1", "name", "start_time")
        constraints = (
            models.UniqueConstraint(
                fields=("organization_id", "external_id"),
                name="unique_jackrabbit_class",
            ),
        )
        indexes = (
            models.Index(fields=("organization_id", "is_current"), name="jr_class_org_current"),
            models.Index(fields=("session", "location_code"), name="jr_class_session_loc"),
        )

    @property
    def meeting_days_display(self):
        return ", ".join(label for key, label in self.DAY_LABELS if self.meeting_days.get(key)) or "Not listed"

    @property
    def time_display(self):
        if not self.start_time:
            return "Time not listed"
        start = self.start_time.strftime("%I:%M %p").lstrip("0")
        if not self.end_time:
            return start
        end = self.end_time.strftime("%I:%M %p").lstrip("0")
        return f"{start}–{end}"

    @property
    def age_display(self):
        minimum = self._format_age(self.minimum_age)
        maximum = self._format_age(self.maximum_age)
        if minimum and maximum:
            return minimum if minimum == maximum else f"{minimum}–{maximum}"
        return minimum or maximum or "See class details"

    @staticmethod
    def _format_age(value):
        value = str(value or "").strip()
        if not value:
            return ""
        match = re.fullmatch(r"P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?", value)
        if not match:
            return value
        years, months, days = (int(part or 0) for part in match.groups())
        parts = []
        if years:
            parts.append(f"{years} yr")
        if months:
            parts.append(f"{months} mo")
        if days:
            parts.append(f"{days} day" + ("s" if days != 1 else ""))
        return " ".join(parts) or "0 mo"

    @property
    def date_display(self):
        if not self.start_date and not self.end_date:
            return "Dates not listed"
        start = self._format_date(self.start_date)
        end = self._format_date(self.end_date)
        if start and end:
            return start if self.start_date == self.end_date else f"{start}–{end}"
        return start or f"Through {end}"

    @staticmethod
    def _format_date(value):
        return f"{value.strftime('%b')} {value.day}, {value.year}" if value else ""

    @property
    def tuition_display(self):
        if self.is_per_day:
            # Jackrabbit uses tuition.fee for one selected day and day_N for
            # the total charge when N days are selected; these are totals, not
            # per-day rates.
            amounts = [self.tuition] if self.tuition is not None else []
            for value in self.tuition_by_day.values():
                try:
                    amounts.append(Decimal(str(value)))
                except (InvalidOperation, TypeError, ValueError):
                    continue
            positive_amounts = [amount for amount in amounts if amount > 0]
            if positive_amounts:
                amounts = positive_amounts
            if amounts:
                low, high = min(amounts), max(amounts)
                if low == high:
                    return f"${low:.2f} total"
                return f"${low:.2f}–${high:.2f} total"
            return "Varies by days selected"
        return f"${self.tuition:.2f}" if self.tuition is not None else "Not listed"

    @property
    def availability_label(self):
        if self.waitlist is True:
            return "Waitlist"
        if self.is_per_day:
            values = self.per_day_opening_values
            if values:
                low, high = min(values), max(values)
                if high <= 0:
                    return "Full"
                return f"{low}–{high} open by day" if low != high else f"{low} open by day"
            return "Check availability by day"
        if self.calculated_openings is None:
            return "Check availability"
        if self.calculated_openings <= 0:
            return "Full"
        return f"{self.calculated_openings} open"

    @property
    def per_day_opening_values(self):
        all_values = [
            value for value in self.openings_by_day.values() if isinstance(value, int)
        ]
        scheduled_values = [
                value
                for day, value in self.openings_by_day.items()
                if isinstance(value, int) and self.meeting_days.get(day, True)
            ]
        return scheduled_values or all_values

    @property
    def availability_state(self):
        if self.waitlist is True:
            return "warning"
        if self.is_per_day:
            values = self.per_day_opening_values
            if not values:
                return "neutral"
            return "warning" if max(values) <= 0 else "open"
        if self.calculated_openings is None:
            return "neutral"
        return "warning" if self.calculated_openings <= 0 else "open"

    @property
    def is_waitlist_listing(self):
        return self.waitlist is True

    @property
    def is_unavailable_listing(self):
        return self.availability_state == "warning"

    def __str__(self):
        return self.name


class ClassSyncRun(models.Model):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    STATUSES = ((RUNNING, "Running"), (SUCCESS, "Success"), (FAILED, "Failed"))

    organization_id = models.CharField(max_length=20, db_index=True)
    status = models.CharField(max_length=16, choices=STATUSES, default=RUNNING, db_index=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    fetched_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    deactivated_count = models.PositiveIntegerField(default=0)
    error_message = models.CharField(max_length=1000, blank=True)

    class Meta:
        ordering = ("-started_at",)
        permissions = (("manage_jackrabbit_sync", "Can run and diagnose Jackrabbit class synchronization"),)

    def __str__(self):
        return f"Class feed {self.get_status_display()} at {self.started_at:%Y-%m-%d %H:%M}"
