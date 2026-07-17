import tempfile
import uuid
from datetime import date, timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from jackrabbit_reporting.models import ClassSyncRun, JackrabbitClass

from .forms import SiteConfigurationForm
from .models import Event, Program, SiteConfiguration


class WebsiteTests(TestCase):
    def test_homepage_uses_verified_business_and_jackrabbit_content(self):
        site = SiteConfiguration.get_solo()
        site.show_online_waiver = True
        site.privacy_url = "https://example.com/privacy"
        site.save()

        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Since 2003")
        self.assertContains(response, "Ages 2½ – 5")
        self.assertContains(response, "app3.jackrabbitclass.com/regv2.asp?id=154877")
        self.assertContains(response, "ParentPortal/Login?orgId=154877")
        self.assertContains(
            response,
            f'href="{reverse("class_schedule")}"',
            html=False,
        )
        self.assertNotContains(
            response,
            f'href="{site.class_schedule_url}"',
            html=False,
        )
        self.assertContains(response, "Jackrabbit registration &amp; billing")
        self.assertContains(response, "Online Waiver")
        self.assertContains(response, reverse("waivers:start"))
        self.assertContains(response, site.privacy_url)
        self.assertNotContains(response, "Stripe")
        self.assertNotContains(response, "private payment link")

    def test_online_waiver_is_disabled_by_default(self):
        site = SiteConfiguration.get_solo()
        self.assertFalse(site.show_online_waiver)

        response = self.client.get(reverse("home"))

        self.assertNotContains(response, "Online Waiver")
        self.assertNotContains(
            response,
            f'href="{reverse("waivers:start")}"',
            html=False,
        )
        self.assertEqual(self.client.get(reverse("waivers:start")).status_code, 404)

    def test_online_waiver_requires_an_approved_privacy_policy_url(self):
        site = SiteConfiguration.get_solo()
        site.show_online_waiver = True

        with self.assertRaisesMessage(
            ValidationError,
            "Add the approved privacy policy URL before enabling the online waiver.",
        ):
            site.full_clean()

    def test_online_waiver_help_locks_the_approved_agreement_wording(self):
        help_text = SiteConfiguration._meta.get_field("show_online_waiver").help_text

        self.assertIn("legally approved", help_text)
        self.assertIn("must remain unchanged", help_text)
        self.assertIn("any text or version change requires renewed legal review", help_text)
        self.assertIn("approved privacy policy URL", help_text)
        self.assertIn("retention and security checks", help_text)

    def test_health_endpoint_checks_database(self):
        self.assertEqual(self.client.get(reverse("health")).json(), {"status": "ok"})

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_container_health_header_avoids_https_redirect(self):
        response = self.client.get(reverse("health"), HTTP_X_FORWARDED_PROTO="https")
        self.assertEqual(response.status_code, 200)

    def test_dashboard_requires_content_permission(self):
        user = get_user_model().objects.create_user("staff", password="safe-test-password", is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)
        user.user_permissions.add(Permission.objects.get(codename="change_program"))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_waiver_viewer_can_open_dashboard_and_waiver_records(self):
        user = get_user_model().objects.create_user(
            "waiver-reviewer",
            password="safe-test-password",
            is_staff=True,
        )
        user.user_permissions.add(
            Permission.objects.get(content_type__app_label="waivers", codename="view_waiver")
        )
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("waivers:staff_list"))
        self.assertContains(response, "stored, validated PDF artifact")
        self.assertNotContains(response, "Django admin")
        self.assertNotContains(
            response,
            f'href="{reverse("waivers:start")}"',
            html=False,
        )

    def test_website_admin_login_accepts_superuser_credentials(self):
        get_user_model().objects.create_superuser("owner-admin", "owner@example.com", "safe-test-password")
        response = self.client.post(reverse("login"), {"username": "owner-admin", "password": "safe-test-password"})
        self.assertRedirects(response, reverse("dashboard"))

    def test_repeated_bad_logins_are_throttled(self):
        get_user_model().objects.create_user("locked-owner", password="correct-password")
        response = None
        with self.assertLogs("axes", level="WARNING"):
            for _ in range(5):
                response = self.client.post(reverse("login"), {"username": "locked-owner", "password": "wrong-password"})
        self.assertEqual(response.status_code, 429)


@override_settings(JACKRABBIT_ORG_ID="154877")
class PublicClassScheduleTests(TestCase):
    @staticmethod
    def add_class(external_id, name, **overrides):
        today = timezone.localdate()
        values = {
            "organization_id": "154877",
            "external_id": external_id,
            "name": name,
            "category1": "Recreation",
            "location_code": "GG",
            "location_name": "Main Gym",
            "start_date": date(today.year, today.month, 1),
            "end_date": date(today.year, 12, 31),
            "start_time": "09:00",
            "end_time": "09:50",
            "meeting_days": {"mon": True},
            "calculated_openings": 4,
            "tuition": "85.00",
            "online_registration_url": (
                "https://app.jackrabbitclass.com/reg.asp?id=154877"
                f"&class={external_id}"
            ),
        }
        values.update(overrides)
        return JackrabbitClass.objects.create(**values)

    def test_calendar_is_anonymous_and_has_no_manager_controls(self):
        today = timezone.localdate()
        current = self.add_class("public-current", "Public Current Gymnastics")

        response = self.client.get(
            reverse("class_schedule"),
            {"month": f"{today.year}-{today.month:02d}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["user"].is_anonymous)
        self.assertContains(response, "Find a class that")
        self.assertContains(response, "Public Current Gymnastics")
        self.assertContains(response, current.online_registration_url.replace("&", "&amp;"))
        self.assertContains(response, "Dates are projected from recurring weekdays")
        self.assertNotContains(response, "Back to reports")
        self.assertNotContains(response, "Refresh now")
        self.assertNotContains(response, "Financial boundary")
        self.assertNotContains(response, reverse("jackrabbit_reporting:dashboard"))
        self.assertNotContains(response, reverse("jackrabbit_reporting:classes"))
        self.assertNotContains(response, reverse("jackrabbit_reporting:sync_classes"))

    def test_calendar_includes_current_classes_but_excludes_legacy_and_out_of_window_rows(self):
        today = timezone.localdate()
        self.add_class("current", "Current Horizon Class")
        self.add_class(
            "legacy",
            "Legacy Historical Class",
            start_date=date(today.year - 1, 1, 1),
            end_date=date(today.year - 1, 12, 31),
        )
        self.add_class(
            "outside",
            "Beyond Calendar Window Class",
            start_date=date(today.year + 2, 1, 1),
            end_date=date(today.year + 2, 12, 31),
        )
        self.add_class(
            "inactive",
            "Inactive Current Class",
            is_current=False,
        )
        self.add_class(
            "other-organization",
            "Other Organization Class",
            organization_id="different-organization",
        )

        response = self.client.get(
            reverse("class_schedule"),
            {"month": f"{today.year}-{today.month:02d}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["candidate_class_count"], 1)
        self.assertEqual(response.context["class_count"], 1)
        self.assertContains(response, "Current Horizon Class")
        self.assertNotContains(response, "Legacy Historical Class")
        self.assertNotContains(response, "Beyond Calendar Window Class")
        self.assertNotContains(response, "Inactive Current Class")
        self.assertNotContains(response, "Other Organization Class")

    def test_next_year_is_inside_the_public_calendar_horizon(self):
        today = timezone.localdate()
        self.add_class(
            "next-year",
            "Next Year Gymnastics",
            start_date=date(today.year + 1, 1, 1),
            end_date=date(today.year + 1, 1, 31),
            meeting_days={"wed": True},
        )

        response = self.client.get(
            reverse("class_schedule"),
            {"month": f"{today.year + 1}-01"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["schedule_year_end"], today.year + 1)
        self.assertEqual(response.context["class_count"], 1)
        self.assertContains(response, "Next Year Gymnastics")

    @override_settings(JACKRABBIT_CLASS_STALE_AFTER_MINUTES=60)
    def test_stale_empty_snapshot_is_not_labeled_current(self):
        ClassSyncRun.objects.create(
            organization_id="154877",
            status=ClassSyncRun.SUCCESS,
            started_at=timezone.now() - timedelta(hours=2),
            finished_at=timezone.now() - timedelta(hours=2),
        )

        response = self.client.get(reverse("class_schedule"))

        self.assertContains(response, "Please verify before registering")
        self.assertNotContains(response, "Current schedule snapshot")

    @override_settings(JACKRABBIT_REPORTING_ENABLED=False)
    def test_disabled_refresh_and_pending_rows_are_not_labeled_current(self):
        self.add_class(
            "pending-public",
            "Pending Confirmation Gymnastics",
            missed_syncs=1,
        )
        ClassSyncRun.objects.create(
            organization_id="154877",
            status=ClassSyncRun.SUCCESS,
            finished_at=timezone.now(),
        )

        response = self.client.get(reverse("class_schedule"))

        self.assertContains(response, "Please verify before registering")
        self.assertNotContains(response, "Current schedule snapshot")

    def test_undated_matches_do_not_claim_that_no_classes_match(self):
        self.add_class(
            "schedule-tbc",
            "Schedule To Be Confirmed Gymnastics",
            meeting_days={},
        )

        response = self.client.get(reverse("class_schedule"))

        self.assertEqual(response.context["class_count"], 1)
        self.assertEqual(response.context["calendar_occurrence_count"], 0)
        self.assertContains(response, "No dated meetings are listed")
        self.assertContains(response, "Schedule To Be Confirmed Gymnastics")
        self.assertNotContains(response, "No classes match this month")


class CMSBaseTests(TestCase):
    password = "safe-test-password"

    def create_staff_user(self, username="manager"):
        return get_user_model().objects.create_user(username, password=self.password, is_staff=True)

    def grant(self, user, *codenames):
        permissions = list(Permission.objects.filter(content_type__app_label="website", codename__in=codenames))
        self.assertEqual({permission.codename for permission in permissions}, set(codenames))
        user.user_permissions.add(*permissions)

    def site_payload(self, site=None, **overrides):
        form = SiteConfigurationForm(instance=site or SiteConfiguration.get_solo())
        data = {}
        for name, field in form.fields.items():
            input_type = getattr(field.widget, "input_type", "")
            if input_type == "file":
                continue
            value = form[name].value()
            if input_type == "checkbox":
                if value:
                    data[name] = "on"
            elif value is not None:
                data[name] = value
        data.update(overrides)
        return data

    @staticmethod
    def program_payload(name="Test program", **overrides):
        data = {
            "name": name,
            "slug": "",
            "age_range": "Ages 6-12",
            "description": "A manager-created program description.",
            "image_alt": "A gymnast practicing during class",
            "call_to_action_url": "https://example.com/register",
            "call_to_action_label": "Register",
            "featured": "on",
            "published": "on",
            "display_order": "10",
        }
        data.update(overrides)
        return data

    @staticmethod
    def image_upload(name="gymnast.png", image_format="PNG"):
        buffer = BytesIO()
        Image.new("RGB", (32, 24), color=(116, 52, 230)).save(buffer, format=image_format)
        content_types = {"BMP": "image/bmp", "JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
        return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_types[image_format])


class CMSPermissionTests(CMSBaseTests):
    def test_content_management_requires_login_and_model_permissions(self):
        content_url = reverse("content_hub")
        response = self.client.get(content_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

        user = self.create_staff_user()
        self.client.force_login(user)
        self.assertEqual(self.client.get(content_url).status_code, 403)
        self.assertEqual(self.client.get(reverse("site_configuration_edit")).status_code, 403)
        self.assertEqual(self.client.get(reverse("content_list", args=["programs"])).status_code, 403)

    def test_program_editor_cannot_manage_site_configuration(self):
        user = self.create_staff_user()
        self.grant(user, "change_program")
        self.client.force_login(user)
        dashboard = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Django admin")
        self.assertEqual(self.client.get(reverse("content_hub")).status_code, 200)
        self.assertEqual(self.client.get(reverse("content_list", args=["programs"])).status_code, 200)
        self.assertEqual(self.client.get(reverse("site_configuration_edit")).status_code, 403)

    def test_retired_plan_and_payment_link_collections_are_not_available(self):
        user = get_user_model().objects.create_superuser("admin", "admin@example.com", self.password)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("content_list", args=["plans"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("content_list", args=["payment-links"])).status_code, 404)


class CMSContentTests(CMSBaseTests):
    def setUp(self):
        self.user = self.create_staff_user()
        self.client.force_login(self.user)

    def test_site_configuration_shows_approved_waiver_launch_help(self):
        self.grant(self.user, "change_siteconfiguration")

        response = self.client.get(reverse("site_configuration_edit"))

        self.assertContains(
            response,
            "The current Regular and Camp wording is legally approved and must remain unchanged",
        )
        self.assertContains(response, "any text or version change requires renewed legal review")
        self.assertContains(
            response,
            "Required before the public online-waiver workflow can be enabled.",
        )

    def test_site_configuration_and_jackrabbit_links_render_publicly(self):
        self.grant(self.user, "change_siteconfiguration")
        payload = self.site_payload(
            hero_heading="Manager controlled headline",
            phone="(904) 555-0199",
            registration_url="https://app3.jackrabbitclass.com/regv2.asp?id=999999",
            portal_url="https://app.jackrabbitclass.com/jr4.0/ParentPortal/Login?orgId=999999",
            class_schedule_url="https://app.jackrabbitclass.com/jr3.0/Openings/OpeningsDirect?OrgID=999999",
        )
        response = self.client.post(reverse("site_configuration_edit"), payload)
        self.assertRedirects(response, reverse("site_configuration_edit"))

        site = SiteConfiguration.objects.get(pk=1)
        self.assertEqual(site.phone_link, "tel:9045550199")
        homepage = self.client.get(reverse("home"))
        self.assertContains(homepage, "Manager controlled headline")
        self.assertContains(homepage, "orgId=999999")
        self.assertContains(
            homepage,
            f'href="{reverse("class_schedule")}"',
            html=False,
        )
        self.assertNotContains(
            homepage,
            f'href="{site.class_schedule_url}"',
            html=False,
        )

    def test_manager_can_upload_a_homepage_picture_with_content_changes(self):
        self.grant(self.user, "change_siteconfiguration")
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            site = SiteConfiguration.get_solo()
            payload = self.site_payload(
                site,
                hero_heading="Homepage picture changed",
                hero_image_alt="A gymnast celebrating after practice",
            )
            payload["hero_image"] = self.image_upload("new-hero.jpg", "JPEG")
            response = self.client.post(reverse("site_configuration_edit"), payload)
            self.assertRedirects(response, reverse("site_configuration_edit"))

            site.refresh_from_db()
            self.assertTrue(site.hero_image.storage.exists(site.hero_image.name))
            homepage = self.client.get(reverse("home"))
            self.assertContains(homepage, "Homepage picture changed")
            self.assertContains(homepage, site.hero_image.url)
            self.assertContains(homepage, "A gymnast celebrating after practice")

    def test_program_crud_publication_and_order_are_reflected_publicly(self):
        self.grant(self.user, "add_program", "change_program", "delete_program")
        add_response = self.client.post(reverse("content_add", args=["programs"]), self.program_payload(name="CMS middle program", display_order="15"))
        self.assertRedirects(add_response, reverse("content_list", args=["programs"]))
        middle = Program.objects.get(name="CMS middle program")
        Program.objects.create(name="CMS first program", slug="cms-first-program", age_range="Ages 5-8", description="First by display order.", image_alt="Gymnast in the first program", featured=True, published=True, display_order=3)
        Program.objects.create(name="CMS hidden program", slug="cms-hidden-program", description="This draft must not be public.", image_alt="Gymnast in an unpublished program", featured=True, published=False, display_order=1)

        body = self.client.get(reverse("home")).content.decode()
        self.assertNotIn("CMS hidden program", body)
        self.assertLess(body.index("CMS first program"), body.index("CMS middle program"))

        edit_payload = self.program_payload(name="CMS renamed program", slug=middle.slug, display_order="15")
        edit_payload.pop("published")
        self.client.post(reverse("content_edit", args=["programs", middle.pk]), edit_payload)
        middle.refresh_from_db()
        self.assertFalse(middle.published)
        self.client.post(reverse("content_delete", args=["programs", middle.pk]))
        self.assertFalse(Program.objects.filter(pk=middle.pk).exists())

    def test_manager_entered_markup_is_escaped(self):
        self.grant(self.user, "add_program")
        response = self.client.post(reverse("content_add", args=["programs"]), self.program_payload(name='<script>alert("cms")</script>'))
        self.assertRedirects(response, reverse("content_list", args=["programs"]), fetch_redirect_response=False)
        homepage = self.client.get(reverse("home"))
        self.assertNotContains(homepage, '<script>alert("cms")</script>')
        self.assertContains(homepage, "&lt;script&gt;")

    def test_event_publication_window_controls_visibility(self):
        now = timezone.now()
        visible = Event.objects.create(title="CMS visible event", slug="cms-visible-event", description="Currently available.", published=True, publish_at=now - timedelta(minutes=1), expires_at=now + timedelta(days=1), display_order=1)
        Event.objects.create(title="CMS draft event", slug="cms-draft-event", description="Draft.", published=False)
        Event.objects.create(title="CMS future event", slug="cms-future-event", description="Not published yet.", published=True, publish_at=now + timedelta(days=1))
        Event.objects.create(title="CMS expired event", slug="cms-expired-event", description="No longer public.", published=True, expires_at=now - timedelta(minutes=1))
        homepage = self.client.get(reverse("home"))
        self.assertTrue(visible.is_visible)
        self.assertContains(homepage, "CMS visible event")
        self.assertNotContains(homepage, "CMS draft event")
        self.assertNotContains(homepage, "CMS future event")
        self.assertNotContains(homepage, "CMS expired event")

    def test_valid_image_upload_is_saved_and_invalid_image_is_rejected(self):
        self.grant(self.user, "add_program")
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            valid_payload = self.program_payload(name="CMS image program")
            valid_payload["image"] = self.image_upload()
            response = self.client.post(reverse("content_add", args=["programs"]), valid_payload)
            self.assertRedirects(response, reverse("content_list", args=["programs"]), fetch_redirect_response=False)
            program = Program.objects.get(name="CMS image program")
            self.assertTrue(program.image.storage.exists(program.image.name))

            invalid_payload = self.program_payload(name="CMS invalid image")
            invalid_payload["image"] = SimpleUploadedFile("broken.jpg", b"not actually an image", content_type="image/jpeg")
            invalid_response = self.client.post(reverse("content_add", args=["programs"]), invalid_payload)
            self.assertEqual(invalid_response.status_code, 200)
            self.assertIn("image", invalid_response.context["form"].errors)

    def test_dashboard_shows_current_image_preview_and_supported_file_types(self):
        self.grant(self.user, "add_program", "change_program", "view_program")
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            payload = self.program_payload(name="Previewed program")
            payload["image"] = self.image_upload()
            self.client.post(reverse("content_add", args=["programs"]), payload)
            program = Program.objects.get(name="Previewed program")

            edit_response = self.client.get(reverse("content_edit", args=["programs", program.pk]))
            self.assertContains(edit_response, "Current picture")
            self.assertContains(edit_response, "Open full size")
            self.assertContains(edit_response, "Remove current picture when I save")
            self.assertContains(edit_response, 'accept="image/jpeg,image/png,image/webp"')
            self.assertContains(edit_response, program.image.url)

            list_response = self.client.get(reverse("content_list", args=["programs"]))
            self.assertContains(list_response, "Uploaded")
            self.assertContains(list_response, program.image.url)

    def test_manager_can_replace_and_remove_an_uploaded_picture(self):
        self.grant(self.user, "add_program", "change_program")
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            add_payload = self.program_payload(name="Picture workflow")
            add_payload["image"] = self.image_upload("first.png")
            self.client.post(reverse("content_add", args=["programs"]), add_payload)
            program = Program.objects.get(name="Picture workflow")
            storage = program.image.storage
            first_name = program.image.name
            self.assertTrue(storage.exists(first_name))

            replace_payload = self.program_payload(name=program.name, slug=program.slug)
            replace_payload["image"] = self.image_upload("replacement.webp", "WEBP")
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse("content_edit", args=["programs", program.pk]), replace_payload)
            self.assertRedirects(response, reverse("content_list", args=["programs"]), fetch_redirect_response=False)
            program.refresh_from_db()
            replacement_name = program.image.name
            self.assertTrue(storage.exists(replacement_name))
            self.assertFalse(storage.exists(first_name))

            clear_payload = self.program_payload(name=program.name, slug=program.slug)
            clear_payload["image-clear"] = "on"
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse("content_edit", args=["programs", program.pk]), clear_payload)
            self.assertRedirects(response, reverse("content_list", args=["programs"]), fetch_redirect_response=False)
            program.refresh_from_db()
            self.assertFalse(program.image)
            self.assertFalse(storage.exists(replacement_name))

    def test_picture_content_must_match_an_allowed_format(self):
        self.grant(self.user, "add_program")
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            payload = self.program_payload(name="Disguised picture")
            payload["image"] = self.image_upload("disguised.jpg", "BMP")
            response = self.client.post(reverse("content_add", args=["programs"]), payload)
            self.assertEqual(response.status_code, 200)
            self.assertIn("image", response.context["form"].errors)
            self.assertFalse(Program.objects.filter(name="Disguised picture").exists())

    def test_deleting_content_removes_its_unreferenced_picture(self):
        self.grant(self.user, "add_program", "delete_program")
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            payload = self.program_payload(name="Deleted picture")
            payload["image"] = self.image_upload("delete-me.png")
            self.client.post(reverse("content_add", args=["programs"]), payload)
            program = Program.objects.get(name="Deleted picture")
            storage = program.image.storage
            image_name = program.image.name

            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse("content_delete", args=["programs", program.pk]))
            self.assertRedirects(response, reverse("content_list", args=["programs"]), fetch_redirect_response=False)
            self.assertFalse(storage.exists(image_name))


class JackrabbitWorkflowTests(CMSBaseTests):
    def test_registration_and_portal_stay_hosted_while_schedule_is_internal(self):
        site = SiteConfiguration.get_solo()
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Register with Jackrabbit")
        self.assertContains(response, "Open Parent Portal")
        self.assertContains(response, "Browse class calendar")
        self.assertContains(
            response,
            f'href="{site.registration_url}"',
            html=False,
        )
        self.assertContains(
            response,
            f'href="{site.portal_url}"',
            html=False,
        )
        self.assertContains(
            response,
            f'href="{reverse("class_schedule")}"',
            html=False,
        )
        self.assertNotContains(
            response,
            f'href="{site.class_schedule_url}"',
            html=False,
        )
        self.assertContains(response, 'target="_blank"')
        self.assertContains(response, 'rel="noopener noreferrer"')
        self.assertNotContains(response, "Stripe checkout")
        self.assertNotContains(response, "planGrid")

    def test_legacy_private_payment_links_redirect_to_parent_portal(self):
        token = uuid.uuid4()
        response = self.client.get(reverse("payment_request", args=[token]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, SiteConfiguration.get_solo().portal_url)
        checkout = self.client.post(reverse("payment_request_checkout", args=[token]))
        self.assertEqual(checkout.status_code, 302)
        self.assertEqual(checkout.url, SiteConfiguration.get_solo().portal_url)

    def test_retired_stripe_webhook_returns_gone(self):
        response = self.client.post(reverse("stripe_webhook"), data=b"{}", content_type="application/json")
        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "Jackrabbit", status_code=410)

    def test_dashboard_links_to_jackrabbit_without_local_financial_metrics(self):
        user = self.create_staff_user("website-owner")
        self.grant(user, "change_siteconfiguration")
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Jackrabbit is the source of truth")
        self.assertContains(response, SiteConfiguration.get_solo().jackrabbit_owner_url)
        self.assertContains(response, SiteConfiguration.get_solo().staff_portal_url)
        self.assertNotContains(response, "Net revenue this month")
        self.assertNotContains(response, "Active subscriptions")

    def test_setup_roles_removes_retired_billing_permissions(self):
        call_command("setup_roles", verbosity=0)
        retired = {"view_membershipplan", "add_paymentrequest", "view_payment", "view_business_dashboard"}
        for group_name in ("Website Managers", "Business Managers"):
            group = Group.objects.get(name=group_name)
            codenames = set(group.permissions.values_list("codename", flat=True))
            self.assertTrue({"change_siteconfiguration", "change_program"}.issubset(codenames))
            self.assertTrue(codenames.isdisjoint(retired))

        waiver_managers = Group.objects.get(name="Waiver Managers")
        self.assertEqual(
            set(waiver_managers.permissions.values_list("codename", flat=True)),
            {"view_waiver"},
        )
