import tempfile
import uuid
from datetime import timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .forms import SiteConfigurationForm
from .models import Event, Program, SiteConfiguration


class WebsiteTests(TestCase):
    def test_homepage_uses_verified_business_and_jackrabbit_content(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Since 2003")
        self.assertContains(response, "Ages 2½ – 5")
        self.assertContains(response, "app3.jackrabbitclass.com/regv2.asp?id=154877")
        self.assertContains(response, "ParentPortal/Login?orgId=154877")
        self.assertContains(response, "OpeningsDirect?OrgID=154877")
        self.assertContains(response, "Jackrabbit registration &amp; billing")
        self.assertNotContains(response, "Stripe")
        self.assertNotContains(response, "private payment link")

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
    def image_upload(name="gymnast.png"):
        buffer = BytesIO()
        Image.new("RGB", (32, 24), color=(116, 52, 230)).save(buffer, format="PNG")
        return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


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
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
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
        self.assertContains(homepage, "OrgID=999999")

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


class JackrabbitWorkflowTests(CMSBaseTests):
    def test_public_actions_use_hosted_jackrabbit_pages(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Register with Jackrabbit")
        self.assertContains(response, "Open Parent Portal")
        self.assertContains(response, "View live classes")
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
