import hashlib
import json
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from jackrabbit_reporting.models import ClassSyncRun, JackrabbitClass, JackrabbitEvent
from jackrabbit_reporting.services.class_feed import ClassFeedError, sync_classes
from jackrabbit_reporting.services.metrics import class_reporting_summary, dashboard_data


REPORTING_SETTINGS = {
    "JACKRABBIT_REPORTING_ENABLED": True,
    "JACKRABBIT_ORG_ID": "154877",
    "JACKRABBIT_WEBHOOK_TOKEN": "current-token-with-more-than-32-characters",
    "JACKRABBIT_WEBHOOK_PREVIOUS_TOKEN": "previous-token-with-more-than-32-characters",
    "JACKRABBIT_WEBHOOK_MAX_BODY_BYTES": 32768,
    "JACKRABBIT_CLASS_SYNC_TIMEOUT_SECONDS": 5,
    "JACKRABBIT_CLASS_STALE_AFTER_MINUTES": 60,
}


class FakeResponse:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, size=-1):
        return self.body[:size]


def class_row(class_id=18541238, name="Preschool Gymnastics", openings=3, tuition=85.00):
    return {
        "id": class_id,
        "category1": "PreSchool",
        "category2": "Beginner",
        "category3": "6Sat",
        "description": "A public class description.",
        "end_date": "",
        "end_time": "12:20",
        "gender": "All",
        "instructors": ["Coach One"],
        "location": "GG",
        "location_code": "GG",
        "location_name": "Main Gym",
        "master_class": False,
        "max_age": "P5Y0M",
        "meeting_days": {"mon": False, "tue": False, "wed": False, "thu": False, "fri": False, "sat": True, "sun": False},
        "min_age": "P3Y6M",
        "name": name,
        "online_reg_link": f"https://app.jackrabbitclass.com/reg.asp?id=154877&amp;WL=0&amp;preLoadClassID={class_id}",
        "openings": {"calculated_openings": openings, "days": {"mon": 0, "tue": 0, "wed": 0, "thu": 0, "fri": 0, "sat": openings, "sun": 0}},
        "reg_start_date": "2014-04-01",
        "room": "Blue Gym",
        "session": "50 Minutes",
        "start_date": "2014-06-01",
        "start_time": "11:30",
        "waitlist": openings <= 0,
        "location_addr1": "4603 Shirley Ave",
        "location_addr2": "",
        "location_city": "Jacksonville",
        "location_state": "FL",
        "location_postalcode": "32210",
        "location_phone": "(904) 388-5533",
        "BillingCycle": "Monthly",
        "tuition": {"fee": tuition, "days": {f"day_{number}": 0 for number in range(2, 8)}},
    }


@override_settings(**REPORTING_SETTINGS)
class EventIngestionTests(TestCase):
    endpoint = reverse("jackrabbit_reporting:ingest_event")

    def payload(self, **overrides):
        payload = {
            "schema_version": 1,
            "event_type": "student_enrolled",
            "idempotency_key": "enroll-123-456-2026-07-13",
            "occurred_at": "2026-07-13T10:30:00-04:00",
            "source": "trigger",
            "student_id": "123",
            "class_id": "456",
            "enrollment_id": "789",
            "location": "GG",
        }
        payload.update(overrides)
        return payload

    def post(self, payload, token=REPORTING_SETTINGS["JACKRABBIT_WEBHOOK_TOKEN"], content_type="application/json"):
        return self.client.post(
            self.endpoint,
            data=json.dumps(payload),
            content_type=content_type,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    @override_settings(JACKRABBIT_WEBHOOK_TOKEN="")
    def test_disabled_ingestion_returns_service_unavailable(self):
        response = self.post(self.payload())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(JackrabbitEvent.objects.count(), 0)

    @override_settings(
        JACKRABBIT_WEBHOOK_TOKEN="replace-with-a-random-secret-of-at-least-32-characters"
    )
    def test_known_example_token_does_not_enable_ingestion(self):
        response = self.post(
            self.payload(),
            token="replace-with-a-random-secret-of-at-least-32-characters",
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(JackrabbitEvent.objects.count(), 0)

    def test_authentication_and_content_type_are_required(self):
        missing = self.client.post(self.endpoint, data="{}", content_type="application/json")
        self.assertEqual(missing.status_code, 401)
        wrong = self.post(self.payload(), token="wrong-token")
        self.assertEqual(wrong.status_code, 401)
        previous = self.post(self.payload(), token=REPORTING_SETTINGS["JACKRABBIT_WEBHOOK_PREVIOUS_TOKEN"])
        self.assertEqual(previous.status_code, 201)
        plain = self.post(self.payload(idempotency_key="other"), content_type="text/plain")
        self.assertEqual(plain.status_code, 415)

    @override_settings(JACKRABBIT_WEBHOOK_PREVIOUS_TOKEN="x")
    def test_short_previous_token_is_not_accepted(self):
        response = self.post(self.payload(), token="x")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(JackrabbitEvent.objects.count(), 0)

    def test_valid_delivery_is_idempotent_and_keeps_only_approved_fields(self):
        response = self.post(self.payload())
        self.assertEqual(response.status_code, 201)
        duplicate = self.post(self.payload())
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.json(), {"status": "duplicate"})
        self.assertEqual(JackrabbitEvent.objects.count(), 1)
        event = JackrabbitEvent.objects.get()
        self.assertEqual(event.student_id, "123")
        self.assertEqual(event.class_id, "456")
        self.assertNotIn("enroll-123", event.dedupe_hash)
        self.assertEqual(len(event.dedupe_hash), 64)

    def test_reused_idempotency_key_with_different_data_is_a_conflict(self):
        self.assertEqual(self.post(self.payload()).status_code, 201)
        conflict = self.post(self.payload(class_id="different-class"))
        self.assertEqual(conflict.status_code, 409)
        self.assertNotContains(conflict, "different-class", status_code=409)
        self.assertEqual(JackrabbitEvent.objects.count(), 1)
        self.assertEqual(JackrabbitEvent.objects.get().class_id, "456")

    def test_unknown_fields_prevent_accidental_pii_storage(self):
        response = self.post(self.payload(email="private@example.com"))
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, "private@example.com", status_code=400)
        self.assertEqual(JackrabbitEvent.objects.count(), 0)

    def test_schema_timestamp_event_type_and_required_ids_are_validated(self):
        invalid_payloads = (
            self.payload(schema_version=2),
            self.payload(occurred_at="2026-07-13 10:30"),
            self.payload(event_type="payment_created"),
            self.payload(student_id=""),
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                self.assertEqual(self.post(payload).status_code, 400)
        self.assertEqual(JackrabbitEvent.objects.count(), 0)

    def test_all_approved_event_types_accept_the_minimum_identifiers(self):
        required = {
            "family_created": {"family_id": "family-1"},
            "contact_created": {"contact_id": "contact-1"},
            "student_created": {"student_id": "student-1"},
            "lead_created": {"family_id": "family-1"},
            "student_enrolled": {"student_id": "student-1", "class_id": "class-1"},
            "student_dropped": {"student_id": "student-1", "class_id": "class-1"},
            "waitlist_added": {"student_id": "student-1", "class_id": "class-1"},
            "waitlist_removed": {"student_id": "student-1", "class_id": "class-1"},
            "student_inactive": {"student_id": "student-1"},
        }
        for index, (event_type, identifiers) in enumerate(required.items()):
            payload = {
                "schema_version": 1,
                "event_type": event_type,
                "idempotency_key": f"minimum-{index}",
                "occurred_at": "2026-07-13T10:30:00-04:00",
                **identifiers,
            }
            with self.subTest(event_type=event_type):
                self.assertEqual(self.post(payload).status_code, 201)
        self.assertEqual(JackrabbitEvent.objects.count(), len(required))

    def test_get_and_malformed_json_are_rejected(self):
        self.assertEqual(self.client.get(self.endpoint).status_code, 405)
        response = self.client.post(
            self.endpoint,
            data="{not-json",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {REPORTING_SETTINGS['JACKRABBIT_WEBHOOK_TOKEN']}",
        )
        self.assertEqual(response.status_code, 400)

    @override_settings(JACKRABBIT_WEBHOOK_MAX_BODY_BYTES=100)
    def test_oversized_body_is_rejected_without_storing_an_event(self):
        response = self.post(self.payload(idempotency_key="x" * 200))
        self.assertEqual(response.status_code, 413)
        self.assertEqual(JackrabbitEvent.objects.count(), 0)


@override_settings(**REPORTING_SETTINGS)
class ClassFeedTests(TestCase):
    def opener(self, payload):
        return lambda request, timeout: FakeResponse(payload)

    def test_successful_feed_sync_normalizes_public_class_data(self):
        run = sync_classes(opener=self.opener({"success": True, "message": "ok", "rows": [class_row()]}))
        self.assertEqual(run.status, ClassSyncRun.SUCCESS)
        self.assertEqual(run.created_count, 1)
        saved = JackrabbitClass.objects.get()
        self.assertEqual(saved.external_id, "18541238")
        self.assertEqual(saved.meeting_days_display, "Sat")
        self.assertEqual(saved.time_display, "11:30 AM–12:20 PM")
        self.assertEqual(saved.age_display, "3 yr 6 mo–5 yr")
        self.assertEqual(saved.date_display, "Jun 1, 2014")
        self.assertEqual(saved.tuition_display, "$85.00")
        self.assertEqual(str(saved.tuition), "85.00")
        self.assertEqual(saved.billing_cycle, "Monthly")
        self.assertIsNone(saved.end_date)
        self.assertIn("&WL=0&preLoadClassID=18541238", saved.online_registration_url)
        self.assertEqual(saved.availability_label, "3 open")

    def test_repeat_sync_updates_changed_rows_and_deactivates_missing_rows(self):
        initial = [class_row(), class_row(18541239, "Second class", 0, 95)]
        sync_classes(opener=self.opener({"success": True, "rows": initial}))
        changed = class_row(name="Renamed class", openings=1, tuition=90)
        run = sync_classes(opener=self.opener({"success": True, "rows": [changed]}))
        self.assertEqual(run.created_count, 0)
        self.assertEqual(run.updated_count, 1)
        self.assertEqual(run.deactivated_count, 0)
        first = JackrabbitClass.objects.get(external_id="18541238")
        second = JackrabbitClass.objects.get(external_id="18541239")
        self.assertEqual(first.name, "Renamed class")
        self.assertEqual(str(first.tuition), "90.00")
        self.assertTrue(first.is_current)
        self.assertTrue(second.is_current)
        self.assertEqual(second.missed_syncs, 1)
        self.assertEqual(
            dashboard_data(30)["class_summary"]["pending_confirmation"],
            1,
        )

        second_missing_run = sync_classes(
            opener=self.opener({"success": True, "rows": [changed]})
        )
        self.assertEqual(second_missing_run.deactivated_count, 1)
        second.refresh_from_db()
        self.assertFalse(second.is_current)

    def test_failed_sync_preserves_last_successful_snapshot(self):
        sync_classes(opener=self.opener({"success": True, "rows": [class_row()]}))
        with self.assertRaises(ClassFeedError):
            sync_classes(opener=self.opener({"success": False, "rows": {}}))
        saved = JackrabbitClass.objects.get()
        self.assertTrue(saved.is_current)
        self.assertEqual(ClassSyncRun.objects.filter(status=ClassSyncRun.SUCCESS).count(), 1)
        self.assertEqual(ClassSyncRun.objects.filter(status=ClassSyncRun.FAILED).count(), 1)

    def test_empty_feed_preserves_last_successful_snapshot(self):
        sync_classes(opener=self.opener({"success": True, "rows": [class_row()]}))
        with self.assertRaises(ClassFeedError):
            sync_classes(opener=self.opener({"success": True, "rows": []}))
        self.assertTrue(JackrabbitClass.objects.get().is_current)
        self.assertEqual(ClassSyncRun.objects.filter(status=ClassSyncRun.FAILED).count(), 1)

    def test_malformed_or_duplicate_rows_preserve_the_last_snapshot(self):
        sync_classes(opener=self.opener({"success": True, "rows": [class_row()]}))
        malformed = class_row()
        malformed["id"] = ""
        with self.assertRaises(ClassFeedError):
            sync_classes(opener=self.opener({"success": True, "rows": [malformed]}))
        duplicate = [class_row(), class_row(name="Duplicate ID")]
        with self.assertRaises(ClassFeedError):
            sync_classes(opener=self.opener({"success": True, "rows": duplicate}))
        saved = JackrabbitClass.objects.get()
        self.assertTrue(saved.is_current)
        self.assertEqual(saved.name, "Preschool Gymnastics")

    def test_per_day_class_labels_do_not_present_aggregate_values(self):
        row = class_row(openings=4, tuition=25)
        row["master_class"] = True
        row["meeting_days"]["mon"] = True
        row["meeting_days"]["tue"] = True
        row["openings"]["days"] = {"mon": 1, "tue": 4}
        row["tuition"]["days"] = {"day_2": 50, "day_3": 75}
        sync_classes(opener=self.opener({"success": True, "rows": [row]}))
        saved = JackrabbitClass.objects.get()
        self.assertEqual(saved.availability_label, "1–4 open by day")
        self.assertEqual(saved.tuition_display, "$25.00–$75.00 total")

    def test_full_and_waitlist_are_distinct_availability_labels(self):
        full = JackrabbitClass(calculated_openings=0, waitlist=False)
        waitlist = JackrabbitClass(calculated_openings=0, waitlist=True)
        self.assertEqual(full.availability_label, "Full")
        self.assertEqual(full.availability_state, "warning")
        self.assertFalse(full.is_waitlist_listing)
        self.assertEqual(waitlist.availability_label, "Waitlist")
        self.assertTrue(waitlist.is_waitlist_listing)

    def test_per_day_and_unknown_availability_have_consistent_states(self):
        per_day_full = JackrabbitClass(
            is_per_day=True,
            waitlist=False,
            meeting_days={"mon": True, "tue": True},
            openings_by_day={"mon": 0, "tue": 0},
        )
        unknown = JackrabbitClass(calculated_openings=None, waitlist=False)
        self.assertEqual(per_day_full.availability_label, "Full")
        self.assertEqual(per_day_full.availability_state, "warning")
        self.assertTrue(per_day_full.is_unavailable_listing)
        self.assertEqual(unknown.availability_label, "Check availability")
        self.assertEqual(unknown.availability_state, "neutral")
        self.assertFalse(unknown.is_unavailable_listing)

    @patch("jackrabbit_reporting.services.class_feed.connection")
    def test_postgresql_lock_rejects_an_overlapping_sync(self, mocked_connection):
        mocked_connection.vendor = "postgresql"
        cursor = mocked_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (False,)
        with self.assertRaisesMessage(
            ClassFeedError,
            "already running",
        ):
            sync_classes(opener=self.opener({"success": True, "rows": [class_row()]}))
        self.assertEqual(ClassSyncRun.objects.count(), 0)

    def test_untrusted_registration_url_is_not_stored(self):
        row = class_row()
        row["online_reg_link"] = "javascript:alert(1)"
        sync_classes(opener=self.opener({"success": True, "rows": [row]}))
        self.assertEqual(JackrabbitClass.objects.get().online_registration_url, "")

    @patch("jackrabbit_reporting.services.class_feed.urlopen")
    def test_management_command_uses_the_feed_service(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse({"success": True, "rows": [class_row()]})
        call_command("sync_jackrabbit_classes", verbosity=0)
        self.assertEqual(JackrabbitClass.objects.count(), 1)
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://app.jackrabbitclass.com/jr3.0/Openings/OpeningsJson")
        self.assertEqual(json.loads(request.data), {"OrgId": "154877", "ShowClosed": 1})
        self.assertEqual(
            request.get_header("User-agent"),
            "GyminatorsWebsite/1.0 (+https://www.gyminators.com/)",
        )


@override_settings(**REPORTING_SETTINGS)
class ReportingDashboardTests(TestCase):
    password = "safe-test-password"

    def setUp(self):
        self.user = get_user_model().objects.create_user("reporter", password=self.password, is_staff=True)
        permission = Permission.objects.get(
            content_type__app_label="jackrabbit_reporting",
            codename="view_reporting_dashboard",
        )
        self.user.user_permissions.add(permission)
        self.client.force_login(self.user)

    def add_event(self, event_type, key, occurred_at=None, **ids):
        return JackrabbitEvent.objects.create(
            organization_id="154877",
            event_type=event_type,
            source=JackrabbitEvent.TRIGGER,
            dedupe_hash=hashlib.sha256(key.encode()).hexdigest(),
            occurred_at=occurred_at or timezone.now(),
            **ids,
        )

    def test_reporting_permission_is_separate_from_content_management(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        reporting_response = self.client.get(reverse("jackrabbit_reporting:dashboard"))
        self.assertEqual(reporting_response.status_code, 200)
        self.assertNotContains(reporting_response, "Django admin")
        self.assertEqual(self.client.get(reverse("content_hub")).status_code, 403)

        cms_user = get_user_model().objects.create_user("cms-only", password=self.password, is_staff=True)
        cms_user.user_permissions.add(Permission.objects.get(content_type__app_label="website", codename="change_program"))
        self.client.force_login(cms_user)
        self.assertEqual(self.client.get(reverse("jackrabbit_reporting:dashboard")).status_code, 403)

    def test_empty_dashboard_does_not_report_false_zeroes(self):
        response = self.client.get(reverse("jackrabbit_reporting:dashboard"))
        self.assertContains(response, "Awaiting the first Zapier delivery")
        self.assertContains(response, "Awaiting this Zap/backfill")
        self.assertNotContains(response, "Net revenue")

    @override_settings(JACKRABBIT_WEBHOOK_TOKEN="too-short")
    def test_dashboard_does_not_call_a_short_token_ready(self):
        response = self.client.get(reverse("jackrabbit_reporting:dashboard"))
        self.assertContains(response, "Ingestion endpoint not configured")
        self.assertNotContains(response, "Ingestion endpoint configured")

    def test_dashboard_reports_all_approved_metrics_and_net_activity(self):
        now = timezone.now()
        current_events = (
            (JackrabbitEvent.FAMILY_CREATED, "family", {"family_id": "f1"}),
            (JackrabbitEvent.CONTACT_CREATED, "contact", {"contact_id": "c1"}),
            (JackrabbitEvent.STUDENT_CREATED, "student", {"student_id": "s1"}),
            (JackrabbitEvent.LEAD_CREATED, "lead", {"family_id": "f2"}),
            (JackrabbitEvent.STUDENT_ENROLLED, "enroll1", {"student_id": "s1", "class_id": "cl1"}),
            (JackrabbitEvent.STUDENT_ENROLLED, "enroll2", {"student_id": "s2", "class_id": "cl1"}),
            (JackrabbitEvent.STUDENT_DROPPED, "drop", {"student_id": "s1", "class_id": "cl1"}),
            (JackrabbitEvent.WAITLIST_ADDED, "wait-add", {"student_id": "s3", "class_id": "cl1"}),
            (JackrabbitEvent.WAITLIST_REMOVED, "wait-remove", {"student_id": "s3", "class_id": "cl1"}),
            (JackrabbitEvent.STUDENT_INACTIVE, "inactive", {"student_id": "s4"}),
        )
        for event_type, key, ids in current_events:
            self.add_event(event_type, key, occurred_at=now - timedelta(days=1), **ids)
        data = dashboard_data(30)
        metrics = {metric["label"]: metric for group in data["metric_groups"] for metric in group["metrics"]}
        self.assertEqual(metrics["New families"]["value"], 1)
        self.assertEqual(metrics["New contacts"]["value"], 1)
        self.assertEqual(metrics["New students"]["value"], 1)
        self.assertEqual(metrics["New leads"]["value"], 1)
        self.assertEqual(metrics["Enrollments"]["value"], 2)
        self.assertEqual(metrics["Drops"]["value"], 1)
        self.assertEqual(metrics["Net enrollment activity"]["value"], 1)
        self.assertEqual(metrics["Waitlist additions"]["value"], 1)
        self.assertEqual(metrics["Waitlist removals"]["value"], 1)
        self.assertEqual(metrics["Net waitlist activity"]["value"], 0)
        self.assertEqual(metrics["Students marked inactive"]["value"], 1)
        self.assertEqual(metrics["Students with churn signals"]["value"], 2)

        response = self.client.get(reverse("jackrabbit_reporting:dashboard"), {"period": "30"})
        for label in metrics:
            self.assertContains(response, label)
        self.assertContains(response, "Published tuition is a class-listing price")
        self.assertContains(response, "Previous-period comparison unavailable")
        self.assertContains(response, "selected period is partial")

    def test_previous_comparison_and_trend_require_earlier_stored_coverage(self):
        now = timezone.now()
        old_event = self.add_event(
            JackrabbitEvent.FAMILY_CREATED,
            "family-before-comparison",
            occurred_at=now - timedelta(days=61),
            family_id="f-old",
        )
        JackrabbitEvent.objects.filter(pk=old_event.pk).update(
            received_at=now - timedelta(days=61)
        )
        self.add_event(
            JackrabbitEvent.FAMILY_CREATED,
            "family-current",
            occurred_at=now - timedelta(days=1),
            family_id="f-new",
        )
        data = dashboard_data(30)
        family_metric = data["metric_groups"][0]["metrics"][0]
        self.assertTrue(family_metric["comparison_available"])
        self.assertEqual(family_metric["value"], 1)
        self.assertEqual(family_metric["previous"], 0)
        self.assertGreaterEqual(len(data["customer_trend"]), 5)
        self.assertTrue(
            all(len(row["values"]) == 1 for row in data["customer_trend"])
        )

    def test_backfilled_value_is_visible_but_marked_unverified_in_trend(self):
        now = timezone.now()
        self.add_event(
            JackrabbitEvent.FAMILY_CREATED,
            "historical-family-delivered-now",
            occurred_at=now - timedelta(days=10),
            family_id="historical-family",
        )
        data = dashboard_data(30)
        family_metric = data["metric_groups"][0]["metrics"][0]
        self.assertEqual(family_metric["value"], 1)
        stored_value = next(
            item
            for row in data["customer_trend"]
            for item in row["values"]
            if item["value"] == 1
        )
        self.assertTrue(stored_value["available"])
        self.assertTrue(stored_value["unverified"])

    def test_rolling_daily_trend_marks_first_and_last_buckets_partial(self):
        now = timezone.now()
        old_event = self.add_event(
            JackrabbitEvent.FAMILY_CREATED,
            "family-before-window",
            occurred_at=now - timedelta(days=30),
            family_id="old-family",
        )
        JackrabbitEvent.objects.filter(pk=old_event.pk).update(
            received_at=now - timedelta(days=30)
        )
        trend = dashboard_data(7)["customer_trend"]
        self.assertGreaterEqual(len(trend), 2)
        self.assertTrue(trend[0]["values"][0]["partial"])
        self.assertTrue(trend[-1]["values"][0]["partial"])

    def test_class_list_is_permissioned_searchable_and_escaped(self):
        JackrabbitClass.objects.create(
            organization_id="154877",
            external_id="1",
            name='<script>alert("class")</script> Beginner Gymnastics',
            category1="Beginner",
            instructors=["Coach One"],
            location_code="GG",
            location_name="Main Gym",
            session="50 Minutes",
            meeting_days={"mon": True},
            calculated_openings=4,
            tuition="85.00",
            online_registration_url="https://app.jackrabbitclass.com/reg.asp?id=154877",
        )
        response = self.client.get(reverse("jackrabbit_reporting:classes"), {"q": "Beginner", "availability": "open"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Class data has not been synchronized")
        self.assertContains(response, "Beginner Gymnastics")
        self.assertContains(response, "$85.00")
        self.assertContains(response, "Open registration page")
        self.assertNotContains(response, "Open in Jackrabbit")
        self.assertNotContains(response, '<script>alert("class")</script>')
        self.assertContains(response, "&lt;script&gt;")

    def test_class_availability_summary_and_filters_use_the_same_states(self):
        shared = {
            "organization_id": "154877",
            "category1": "Availability test",
            "is_current": True,
        }
        JackrabbitClass.objects.create(
            **shared,
            external_id="per-day-open",
            name="Per-day open",
            is_per_day=True,
            meeting_days={"mon": True, "tue": True},
            openings_by_day={"mon": 0, "tue": 3},
        )
        JackrabbitClass.objects.create(
            **shared,
            external_id="per-day-full",
            name="Per-day full",
            is_per_day=True,
            meeting_days={"mon": True, "tue": True},
            openings_by_day={"mon": 0, "tue": 0},
        )
        JackrabbitClass.objects.create(
            **shared,
            external_id="unknown",
            name="Availability unknown",
            calculated_openings=None,
        )
        JackrabbitClass.objects.create(
            **shared,
            external_id="waitlist",
            name="Explicit waitlist",
            calculated_openings=2,
            waitlist=True,
        )

        summary = class_reporting_summary()
        self.assertEqual(summary["count"], 4)
        self.assertEqual(summary["with_openings"], 1)
        self.assertEqual(summary["waitlist"], 2)

        open_response = self.client.get(
            reverse("jackrabbit_reporting:classes"), {"availability": "open"}
        )
        self.assertContains(open_response, "Per-day open")
        self.assertNotContains(open_response, "Per-day full")
        self.assertNotContains(open_response, "Availability unknown")

        warning_response = self.client.get(
            reverse("jackrabbit_reporting:classes"), {"availability": "waitlist"}
        )
        self.assertContains(warning_response, "Per-day full")
        self.assertContains(warning_response, "Explicit waitlist")
        self.assertNotContains(warning_response, "Availability unknown")

    @override_settings(JACKRABBIT_REPORTING_ENABLED=False)
    def test_disabled_reporting_is_explicit_and_hides_manual_refresh(self):
        self.user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="jackrabbit_reporting",
                codename="manage_jackrabbit_sync",
            )
        )
        response = self.client.get(reverse("jackrabbit_reporting:dashboard"))
        self.assertContains(response, "reporting and class refresh are disabled")
        self.assertContains(response, "Class feed refresh disabled")
        self.assertNotContains(response, "Refresh now")
        class_response = self.client.get(reverse("jackrabbit_reporting:classes"))
        self.assertContains(class_response, "Class refresh is disabled")

    def test_first_failed_class_refresh_is_not_reported_as_never_synchronized(self):
        ClassSyncRun.objects.create(
            organization_id="154877",
            status=ClassSyncRun.FAILED,
            finished_at=timezone.now(),
            error_message="sanitized failure",
        )
        response = self.client.get(reverse("jackrabbit_reporting:classes"))
        self.assertContains(response, "The first class refresh failed")
        self.assertNotContains(response, "Class data has not been synchronized")

    def test_dashboard_and_class_list_ignore_other_organizations(self):
        JackrabbitEvent.objects.create(
            organization_id="different-org",
            event_type=JackrabbitEvent.FAMILY_CREATED,
            dedupe_hash=hashlib.sha256(b"other-org-event").hexdigest(),
            occurred_at=timezone.now(),
            family_id="other-family",
        )
        JackrabbitClass.objects.create(
            organization_id="different-org",
            external_id="other-class",
            name="Other organization class",
        )
        data = dashboard_data(30)
        family_metric = data["metric_groups"][0]["metrics"][0]
        self.assertFalse(family_metric["available"])
        response = self.client.get(reverse("jackrabbit_reporting:classes"))
        self.assertNotContains(response, "Other organization class")

    def test_setup_roles_creates_separate_reporting_group(self):
        call_command("setup_roles", verbosity=0)
        reporting = Group.objects.get(name="Reporting Managers")
        codenames = set(reporting.permissions.values_list("codename", flat=True))
        self.assertIn("view_reporting_dashboard", codenames)
        self.assertNotIn("change_siteconfiguration", codenames)
        self.assertNotIn("view_jackrabbitevent", codenames)
        self.assertNotIn("view_jackrabbitclass", codenames)
        self.assertNotIn("view_classsyncrun", codenames)
        website = Group.objects.get(name="Website Managers")
        self.assertNotIn("view_reporting_dashboard", set(website.permissions.values_list("codename", flat=True)))

        self.user.user_permissions.clear()
        self.user.groups.add(reporting)
        self.user = get_user_model().objects.get(pk=self.user.pk)
        self.client.force_login(self.user)
        self.assertEqual(
            self.client.get(
                reverse("admin:jackrabbit_reporting_jackrabbitevent_changelist")
            ).status_code,
            403,
        )

    def test_reporting_status_command_reports_usable_token_without_revealing_it(self):
        output = StringIO()
        call_command("check_jackrabbit_reporting", stdout=output)
        status = output.getvalue()
        self.assertIn("Webhook token usable: yes", status)
        self.assertNotIn(REPORTING_SETTINGS["JACKRABBIT_WEBHOOK_TOKEN"], status)
