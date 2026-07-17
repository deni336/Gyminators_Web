import base64
from datetime import date, timedelta
import hashlib
from io import BytesIO, StringIO
import re
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image, ImageDraw
from pypdf import PdfReader

from website.models import SiteConfiguration

from .constants import AGREEMENTS, CAMP, REGULAR
from .forms import MAX_SIGNATURE_BYTES, NewWaiverForm, decode_signature_png
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
from .services import (
    PROFILE_TOKEN_MAX_AGE,
    SEARCH_IP_MAX_ATTEMPTS,
    SUBMISSION_IP_MAX_ATTEMPTS,
    SUBMISSION_TOKEN_MAX_AGE,
    issue_profile_token,
    issue_submission_token,
    read_profile_token,
)
from .views import CONFIRMATION_SESSION_KEY


def signature_data_url(*, blank=False):
    image = Image.new("RGBA", (500, 180), (255, 255, 255, 0))
    if not blank:
        draw = ImageDraw.Draw(image)
        draw.line(
            [(25, 125), (80, 55), (125, 130), (180, 45), (240, 125), (330, 70), (465, 110)],
            fill=(25, 25, 25, 255),
            width=7,
            joint="curve",
        )
    output = BytesIO()
    image.save(output, "PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


class WaiverTestMixin:
    def enable_public_waivers(self):
        configuration, _created = SiteConfiguration.objects.get_or_create(pk=1)
        configuration.show_online_waiver = True
        configuration.privacy_url = "https://example.test/privacy"
        configuration.save()

    def setUp(self):
        super().setUp()
        self.enable_public_waivers()

    @property
    def gymnast_dob(self):
        today = timezone.localdate()
        return date(today.year - 10, 1, 1)

    def new_payload(self, enrollment_type=REGULAR, **overrides):
        agreement = AGREEMENTS[enrollment_type]
        payload = {
            "gymnast_first_name": "Avery",
            "gymnast_last_name": "Example",
            "gymnast_dob": self.gymnast_dob.isoformat(),
            "gymnast_age": "10",
            "guardian_first_name": "Jordan",
            "guardian_last_name": "Example",
            "guardian_phone": "(904) 555-0199",
            "guardian_email": "guardian@example.test",
            "home_address": "123 Gym Lane",
            "city": "Jacksonville",
            "state": "Florida",
            "zip_code": "32210",
            "gender": "Female",
            "home_phone": "",
            "guardian_occupation": "Teacher",
            "guardian_work_phone": "",
            "guardian_cell_phone": "",
            "second_guardian_name": "",
            "second_guardian_occupation": "",
            "second_guardian_work_phone": "",
            "second_guardian_cell_phone": "",
            "primary_insurance": "Example Health",
            "policy_number": "POL-123",
            "citizen_usa": "yes",
            "medical_info": "No known allergies",
            "referral_source": "Friend",
            "emergency_first_name": "Casey",
            "emergency_last_name": "Helper",
            "emergency_relationship": "Aunt",
            "emergency_phone": "904-555-0188",
            "pickup_first_name": "Taylor",
            "pickup_last_name": "Pickup",
            "pickup_phone": "904-555-0177",
            "typed_signer_name": "Jordan Example",
            "signer_capacity": Waiver.PARENT,
            "agreement_accepted": "on",
            "signature_data": signature_data_url(),
            "submission_token": issue_submission_token(enrollment_type, Waiver.NEW),
        }
        if enrollment_type == CAMP:
            payload["activity_name"] = "Summer Camp Week 1"
        for number in range(1, agreement.clause_count + 1):
            payload[f"initial_{number}"] = "JE"
        payload.update(overrides)
        return payload

    def post_new(self, enrollment_type=REGULAR, payload=None):
        return self.client.post(
            reverse("waivers:new", args=[enrollment_type]),
            payload or self.new_payload(enrollment_type),
        )

    def create_profile(self, *, first_name="Avery", last_name="Example", phone="904-555-0199"):
        gymnast = GymnastProfile.objects.create(
            first_name=first_name,
            last_name=last_name,
            date_of_birth=self.gymnast_dob,
            age=10,
        )
        GuardianProfile.objects.create(
            gymnast=gymnast,
            first_name="Jordan",
            last_name=last_name,
            phone=phone,
            email="guardian-private@example.test",
        )
        EmergencyContactProfile.objects.create(
            gymnast=gymnast,
            first_name="Private",
            last_name="Emergency",
            relationship="Aunt",
            phone="904-555-0111",
        )
        AuthorizedPickupProfile.objects.create(
            gymnast=gymnast,
            first_name="Taylor",
            last_name="Pickup",
            phone="904-555-0177",
        )
        return gymnast

    def returning_payload(self, gymnast, enrollment_type=REGULAR, **overrides):
        agreement = AGREEMENTS[enrollment_type]
        payload = {
            "guardian_first_name": "Updated",
            "guardian_last_name": "Guardian",
            "guardian_phone": "904-555-0199",
            "guardian_email": "updated@example.test",
            "emergency_first_name": "Current",
            "emergency_last_name": "Contact",
            "emergency_relationship": "Uncle",
            "emergency_phone": "904-555-0144",
            "pickup_first_name": "Updated",
            "pickup_last_name": "Pickup",
            "pickup_phone": "904-555-0166",
            "pickup_verified": "on",
            "typed_signer_name": "Updated Guardian",
            "signer_capacity": Waiver.LEGAL_GUARDIAN,
            "agreement_accepted": "on",
            "signature_data": signature_data_url(),
            "submission_token": issue_submission_token(
                enrollment_type,
                Waiver.RETURNING,
                gymnast.pk,
            ),
        }
        if enrollment_type == CAMP:
            payload["activity_name"] = "Day Camp"
        for number in range(1, agreement.clause_count + 1):
            payload[f"initial_{number}"] = "UG"
        payload.update(overrides)
        return payload


class NewWaiverFlowTests(WaiverTestMixin, TestCase):
    def test_new_regular_waiver_creates_normalized_profiles_and_immutable_snapshot(self):
        response = self.post_new()
        waiver = Waiver.objects.get()
        self.assertRedirects(
            response,
            reverse("waivers:success", args=[waiver.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(GymnastProfile.objects.count(), 1)
        self.assertEqual(GuardianProfile.objects.count(), 1)
        self.assertEqual(EmergencyContactProfile.objects.count(), 1)
        self.assertEqual(AuthorizedPickupProfile.objects.count(), 1)
        self.assertEqual(waiver.legal_text_snapshot, AGREEMENTS[REGULAR].text)
        self.assertEqual(waiver.agreement_version, AGREEMENTS[REGULAR].version)
        self.assertEqual(waiver.agreement_sha256, AGREEMENTS[REGULAR].sha256)
        self.assertEqual(waiver.initials, {str(number): "JE" for number in range(1, 8)})
        self.assertEqual(waiver.details["guardian"]["email"], "guardian@example.test")
        self.assertEqual(waiver.details["enrollment"]["medical_info"], "No known allergies")
        self.assertEqual(waiver.signer_capacity, Waiver.PARENT)
        self.assertTrue(bytes(waiver.signature_png).startswith(b"\x89PNG"))
        self.assertEqual(waiver.signature_sha256, hashlib.sha256(bytes(waiver.signature_png)).hexdigest())
        artifact = waiver.stored_pdf
        content = artifact.validated_content()
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertTrue(content.rstrip().endswith(b"%%EOF"))
        self.assertEqual(artifact.pdf_sha256, hashlib.sha256(content).hexdigest())

    def test_submission_is_idempotent(self):
        payload = self.new_payload()
        first = self.post_new(payload=payload)
        second = self.post_new(payload=payload)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(first.url, second.url)
        self.assertEqual(Waiver.objects.count(), 1)
        self.assertEqual(GymnastProfile.objects.count(), 1)
        self.assertEqual(StoredWaiverPDF.objects.count(), 1)

    def test_idempotent_retry_refuses_a_corrupt_existing_artifact(self):
        payload = self.new_payload()
        self.assertEqual(self.post_new(payload=payload).status_code, 302)
        waiver = Waiver.objects.get()
        spoofed_pdf = b"%PDF-1.4\nnot readable\n%%EOF\n"
        StoredWaiverPDF._base_manager.filter(waiver_id=waiver.pk).update(
            pdf_bytes=spoofed_pdf,
            pdf_sha256=hashlib.sha256(spoofed_pdf).hexdigest(),
        )
        with self.assertRaises(ValidationError):
            self.post_new(payload=payload)
        self.assertEqual(Waiver.objects.count(), 1)
        self.assertEqual(StoredWaiverPDF.objects.count(), 1)

    def test_unreadable_pdf_rolls_back_the_entire_signing_transaction(self):
        spoofed_pdf = b"%PDF-1.4\n%%EOF\n"
        with patch("waivers.services.render_waiver_pdf", return_value=spoofed_pdf):
            with self.assertRaises(ValidationError):
                self.post_new()
        self.assertFalse(Waiver.objects.exists())
        self.assertFalse(StoredWaiverPDF.objects.exists())
        self.assertFalse(GymnastProfile.objects.exists())
        self.assertFalse(GuardianProfile.objects.exists())
        self.assertFalse(EmergencyContactProfile.objects.exists())
        self.assertFalse(AuthorizedPickupProfile.objects.exists())

    def test_blank_or_tap_signature_and_missing_explicit_agreement_are_rejected(self):
        payload = self.new_payload(signature_data=signature_data_url(blank=True))
        payload.pop("agreement_accepted")
        response = self.post_new(payload=payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Draw a signature")
        self.assertContains(response, "This field is required")
        self.assertEqual(Waiver.objects.count(), 0)
        self.assertNotContains(response, "data:image/png;base64,")

    def test_age_must_match_dob(self):
        response = self.post_new(payload=self.new_payload(gymnast_age="9"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Age must be 10")
        self.assertFalse(Waiver.objects.exists())

    def test_camp_requires_activity_and_three_initials(self):
        payload = self.new_payload(CAMP)
        payload["activity_name"] = ""
        response = self.post_new(CAMP, payload)
        self.assertContains(response, "This field is required")
        self.assertFalse(Waiver.objects.exists())
        payload = self.new_payload(CAMP)
        response = self.post_new(CAMP, payload)
        self.assertEqual(response.status_code, 302)
        waiver = Waiver.objects.get()
        self.assertEqual(waiver.activity_name, "Summer Camp Week 1")
        self.assertEqual(set(waiver.initials), {"1", "2", "3"})

    def test_signature_rejects_payload_above_limit(self):
        oversized = b"\x89PNG\r\n\x1a\n" + (b"x" * MAX_SIGNATURE_BYTES)
        value = "data:image/png;base64," + base64.b64encode(oversized).decode("ascii")
        with self.assertRaises(ValidationError):
            decode_signature_png(value)

    def test_fresh_sessions_and_tokens_cannot_bypass_submission_throttle(self):
        url = reverse("waivers:new", args=[REGULAR])
        for _number in range(SUBMISSION_IP_MAX_ATTEMPTS):
            client = Client()
            response = client.post(
                url,
                {"submission_token": issue_submission_token(REGULAR, Waiver.NEW)},
                REMOTE_ADDR="192.0.2.44",
            )
            self.assertEqual(response.status_code, 200)
        blocked = Client().post(
            url,
            {"submission_token": issue_submission_token(REGULAR, Waiver.NEW)},
            REMOTE_ADDR="192.0.2.44",
        )
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked["Retry-After"], "600")
        bucket = WaiverSubmissionThrottle.objects.get()
        self.assertEqual(bucket.attempts, SUBMISSION_IP_MAX_ATTEMPTS)
        self.assertNotIn("192.0.2.44", bucket.client_key)

    def test_confirmation_is_bound_to_submitting_session(self):
        response = self.post_new()
        confirmation_id = Waiver.objects.get().pk
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self.client.get(reverse("waivers:success", args=[confirmation_id])).status_code,
            200,
        )
        self.assertEqual(
            Client().get(reverse("waivers:success", args=[uuid.uuid4()])).status_code,
            404,
        )


class ReturningLookupTests(WaiverTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.gymnast = self.create_profile()
        self.search_url = reverse("waivers:returning_search", args=[REGULAR])

    def search(self, **overrides):
        data = {
            "gymnast_last_name": "Example",
            "gymnast_dob": self.gymnast_dob.isoformat(),
            "guardian_phone_last4": "0199",
        }
        data.update(overrides)
        return self.client.post(self.search_url, data, REMOTE_ADDR="203.0.113.10")

    def test_search_requires_exact_surname_dob_and_phone_and_keeps_results_private(self):
        response = self.search()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Avery E.")
        self.assertNotContains(response, "guardian-private@example.test")
        self.assertNotContains(response, "904-555-0199")
        self.assertNotContains(response, "Private Emergency")
        self.assertNotContains(response, str(self.gymnast.pk))
        self.assertContains(response, "returning/")

        wrong = self.search(gymnast_last_name="Exam")
        self.assertContains(wrong, "No matching gymnast was found")
        wrong_dob = self.search(gymnast_dob=(self.gymnast_dob + timedelta(days=1)).isoformat())
        self.assertContains(wrong_dob, "No matching gymnast was found")

    def test_session_throttle_blocks_sixth_attempt(self):
        for _number in range(5):
            self.assertEqual(self.search(guardian_phone_last4="0000").status_code, 200)
        response = self.search(guardian_phone_last4="0000")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "600")

    def test_rotating_sessions_cannot_bypass_central_hmac_bucket(self):
        data = {
            "gymnast_last_name": "Nobody",
            "gymnast_dob": self.gymnast_dob.isoformat(),
            "guardian_phone_last4": "0000",
        }
        for _number in range(SEARCH_IP_MAX_ATTEMPTS):
            client = Client()
            self.assertEqual(client.post(self.search_url, data, REMOTE_ADDR="198.51.100.8").status_code, 200)
        blocked = Client().post(self.search_url, data, REMOTE_ADDR="198.51.100.8")
        self.assertEqual(blocked.status_code, 429)
        bucket = ReturningSearchThrottle.objects.get()
        self.assertEqual(len(bucket.client_key), 64)
        self.assertNotIn("198.51.100.8", bucket.client_key)

    def test_bad_mismatched_and_expired_profile_tokens_return_404(self):
        bad_url = reverse("waivers:returning", args=[REGULAR, "not-a-token"])
        self.assertEqual(self.client.get(bad_url).status_code, 404)
        token = issue_profile_token(self.gymnast, REGULAR)
        mismatch = reverse("waivers:returning", args=[CAMP, token])
        self.assertEqual(self.client.get(mismatch).status_code, 404)
        with patch("waivers.views.read_profile_token", side_effect=signing.SignatureExpired("expired")):
            self.assertEqual(self.client.get(reverse("waivers:returning", args=[REGULAR, token])).status_code, 404)

    def test_profile_token_uses_full_two_hour_form_lifetime(self):
        self.assertEqual(PROFILE_TOKEN_MAX_AGE, SUBMISSION_TOKEN_MAX_AGE)
        with patch("django.core.signing.time.time", return_value=1_000):
            token = issue_profile_token(self.gymnast, REGULAR)
        with patch("django.core.signing.time.time", return_value=1_000 + (16 * 60)):
            self.assertEqual(read_profile_token(token, REGULAR), self.gymnast.pk)
        with patch("django.core.signing.time.time", return_value=1_000 + SUBMISSION_TOKEN_MAX_AGE + 1):
            with self.assertRaises(signing.SignatureExpired):
                read_profile_token(token, REGULAR)


class ReturningSigningTests(WaiverTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.gymnast = self.create_profile()
        self.token = issue_profile_token(self.gymnast, REGULAR)
        self.url = reverse("waivers:returning", args=[REGULAR, self.token])

    def test_form_does_not_disclose_saved_guardian_pickup_or_medical_data(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "guardian-private@example.test")
        self.assertNotContains(response, "904-555-0177")
        self.assertNotContains(response, "904-555-0199")
        self.assertNotContains(response, "Private Emergency")
        self.assertContains(response, "saved guardian, contact, and pickup details are not displayed")
        self.assertIn("no-store", response["Cache-Control"])

    def test_returning_save_keeps_profiles_private_and_uses_fresh_snapshot(self):
        old_dob = self.gymnast.date_of_birth
        GymnastProfile.objects.filter(pk=self.gymnast.pk).update(age=9)
        # The profile queryset is mutable; only Waiver's queryset blocks update.
        response = self.client.post(self.url, self.returning_payload(self.gymnast))
        self.assertEqual(response.status_code, 302)
        waiver = Waiver.objects.get()
        self.gymnast.refresh_from_db()
        self.gymnast.guardian.refresh_from_db()
        self.gymnast.authorized_pickup.refresh_from_db()
        self.assertEqual(self.gymnast.date_of_birth, old_dob)
        self.assertEqual(self.gymnast.age, 10)
        self.assertEqual(self.gymnast.guardian.first_name, "Jordan")
        self.assertEqual(self.gymnast.authorized_pickup.phone, "904-555-0177")
        self.assertEqual(waiver.participant_status, Waiver.RETURNING)
        self.assertTrue(waiver.pickup_verified)
        self.assertEqual(waiver.details["guardian"]["email"], "updated@example.test")
        self.assertEqual(waiver.details["emergency_contact"]["phone"], "904-555-0144")
        self.assertEqual(waiver.details["authorized_pickup"]["phone"], "904-555-0166")
        self.assertIsNone(waiver.guardian_id)
        self.assertIsNone(waiver.emergency_contact_id)
        self.assertIsNone(waiver.authorized_pickup_id)
        self.assertEqual(waiver.stored_pdf.waiver_id, waiver.pk)

    def test_pickup_verification_and_fresh_signature_are_required(self):
        payload = self.returning_payload(self.gymnast)
        payload.pop("pickup_verified")
        payload["signature_data"] = ""
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")
        self.assertFalse(Waiver.objects.exists())

    def test_returning_post_uses_submission_throttle_before_validation(self):
        with patch("waivers.views.consume_submission_attempt", return_value=False):
            response = self.client.post(self.url, {"signature_data": "malformed"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "600")

    def test_unreadable_pdf_rolls_back_returning_waiver_and_profile_age(self):
        GymnastProfile.objects.filter(pk=self.gymnast.pk).update(age=9)
        with patch(
            "waivers.services.render_waiver_pdf",
            return_value=b"%PDF-1.4\n%%EOF\n",
        ):
            with self.assertRaises(ValidationError):
                self.client.post(self.url, self.returning_payload(self.gymnast))

        self.gymnast.refresh_from_db()
        self.assertEqual(self.gymnast.age, 9)
        self.assertFalse(Waiver.objects.exists())
        self.assertFalse(StoredWaiverPDF.objects.exists())


class StaffAndImmutabilityTests(WaiverTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.post_new()
        self.waiver = Waiver.objects.get()
        self.list_url = reverse("waivers:staff_list")
        self.detail_url = reverse("waivers:staff_detail", args=[self.waiver.pk])
        self.pdf_url = reverse("waivers:staff_pdf", args=[self.waiver.pk])

    def permission_user(self, username="manager"):
        user = get_user_model().objects.create_user(username, password="test-password")
        permission = Permission.objects.get(content_type__app_label="waivers", codename="view_waiver")
        user.user_permissions.add(permission)
        return user

    def test_permission_boundaries_allow_non_staff_permission_holder(self):
        anonymous = self.client.get(self.list_url)
        self.assertEqual(anonymous.status_code, 302)
        self.assertTrue(anonymous.url.startswith("/staff/login/"))
        unprivileged = get_user_model().objects.create_user("plain", password="test-password")
        self.client.force_login(unprivileged)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        manager = self.permission_user()
        self.assertFalse(manager.is_staff)
        self.client.force_login(manager)
        self.assertEqual(self.client.get(self.list_url).status_code, 200)
        self.assertEqual(self.client.get(self.detail_url).status_code, 200)

    def test_staff_search_uses_post_and_get_query_is_ignored(self):
        self.client.force_login(self.permission_user())
        get_response = self.client.get(self.list_url, {"q": "DoesNotMatch"})
        self.assertContains(get_response, self.waiver.gymnast.first_name)
        post_response = self.client.post(self.list_url, {"q": "DoesNotMatch"})
        self.assertNotContains(post_response, self.waiver.gymnast.first_name)

    def test_staff_detail_shows_stored_pdf_metadata_but_not_binary_content(self):
        artifact = self.waiver.stored_pdf
        self.client.force_login(self.permission_user())
        response = self.client.get(self.detail_url)
        self.assertContains(response, "Stored PDF artifact")
        self.assertContains(response, artifact.pdf_sha256)
        self.assertNotContains(response, base64.b64encode(bytes(artifact.pdf_bytes)).decode("ascii"))

    def test_signed_waiver_cannot_be_saved_updated_or_deleted(self):
        self.waiver.typed_signer_name = "Changed"
        with self.assertRaises(ValidationError):
            self.waiver.save()
        with self.assertRaises(ValidationError):
            Waiver.objects.filter(pk=self.waiver.pk).update(typed_signer_name="Changed")
        with self.assertRaises(ValidationError):
            Waiver.objects.filter(pk=self.waiver.pk).delete()
        with self.assertRaises(ValidationError):
            Waiver.objects.bulk_create([])
        with self.assertRaises(ValidationError):
            self.waiver.delete()

        artifact = self.waiver.stored_pdf
        artifact.pdf_bytes = b"changed"
        with self.assertRaises(ValidationError):
            artifact.save()
        with self.assertRaises(ValidationError):
            StoredWaiverPDF.objects.filter(pk=artifact.pk).update(pdf_bytes=b"changed")
        with self.assertRaises(ValidationError):
            StoredWaiverPDF.objects.filter(pk=artifact.pk).delete()
        with self.assertRaises(ValidationError):
            StoredWaiverPDF.objects.bulk_create([])
        with self.assertRaises(ValidationError):
            artifact.delete()

    def test_pdf_is_permissioned_and_downloads_exact_stored_readable_artifact(self):
        self.assertEqual(self.client.get(self.pdf_url).status_code, 302)
        self.client.force_login(self.permission_user())
        artifact = self.waiver.stored_pdf
        stored_content = bytes(artifact.pdf_bytes)
        with patch(
            "waivers.pdf.render_waiver_pdf",
            side_effect=AssertionError("downloads must not rerender"),
        ):
            response = self.client.get(self.pdf_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response.content, stored_content)
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertTrue(response.content.rstrip().endswith(b"%%EOF"))
        self.assertIn(str(self.waiver.pk), response["Content-Disposition"])
        self.assertIn("no-store", response["Cache-Control"])

        reader = PdfReader(BytesIO(response.content), strict=True)
        self.assertGreaterEqual(len(reader.pages), 1)
        extracted = re.sub(
            r"\s+",
            " ",
            "\n".join(page.extract_text() or "" for page in reader.pages),
        )
        expected_legal_text = re.sub(r"\s+", " ", self.waiver.legal_text_snapshot)
        self.assertIn(expected_legal_text, extracted)
        self.assertIn(self.waiver.agreement_version, extracted)
        self.assertIn(str(self.waiver.pk), extracted)

    def test_direct_model_save_rejects_a_spoofed_pdf(self):
        artifact = StoredWaiverPDF(
            waiver=self.waiver,
            pdf_bytes=b"%PDF-1.4\nthis is not a readable PDF\n%%EOF\n",
        )
        with self.assertRaises(ValidationError):
            artifact.save()

    def test_stored_pdf_requires_an_embedded_signature_image(self):
        artifact = self.waiver.stored_pdf
        with patch("waivers.pdf._reader_contains_image", return_value=False):
            with self.assertRaisesMessage(
                ValidationError,
                "The signed-waiver PDF is not readable or complete.",
            ):
                artifact.validated_content()

    def test_corrupt_stored_pdf_fails_closed_without_regeneration(self):
        spoofed_pdf = b"%PDF-1.4\nthis is not a readable PDF\n%%EOF\n"
        StoredWaiverPDF._base_manager.filter(waiver_id=self.waiver.pk).update(
            pdf_bytes=spoofed_pdf,
            pdf_sha256=hashlib.sha256(spoofed_pdf).hexdigest(),
        )
        self.client.force_login(self.permission_user())
        with patch(
            "waivers.pdf.render_waiver_pdf",
            side_effect=AssertionError("corrupt artifacts must not be regenerated"),
        ):
            response = self.client.get(self.pdf_url)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertContains(
            response,
            "could not be verified",
            status_code=409,
        )
        self.assertIn("no-store", response["Cache-Control"])

    def test_missing_stored_pdf_fails_closed(self):
        StoredWaiverPDF._base_manager.filter(waiver_id=self.waiver.pk).delete()
        self.client.force_login(self.permission_user())
        response = self.client.get(self.pdf_url)
        self.assertEqual(response.status_code, 404)

    def test_xss_is_escaped_in_staff_detail_and_list(self):
        attack = '<script>alert("gymnast")</script>'
        self.assertEqual(
            self.post_new(payload=self.new_payload(gymnast_first_name=attack)).status_code,
            302,
        )
        xss_waiver = Waiver.objects.exclude(pk=self.waiver.pk).get()
        self.client.force_login(self.permission_user())
        for url in (self.list_url, reverse("waivers:staff_detail", args=[xss_waiver.pk])):
            response = self.client.get(url)
            self.assertNotContains(response, attack)
            self.assertContains(response, "&lt;script&gt;")

    def test_all_sensitive_responses_are_no_store(self):
        manager = self.permission_user()
        self.client.force_login(manager)
        for url in (self.list_url, self.detail_url, self.pdf_url):
            response = self.client.get(url)
            self.assertIn("no-store", response["Cache-Control"])
            self.assertEqual(response["Pragma"], "no-cache")

    def test_public_toggle_does_not_disable_staff_records(self):
        config = SiteConfiguration.objects.get(pk=1)
        config.show_online_waiver = False
        config.save()
        self.assertEqual(self.client.get(reverse("waivers:start")).status_code, 404)
        self.client.force_login(self.permission_user())
        self.assertEqual(self.client.get(self.list_url).status_code, 200)


class PDFBackfillCommandTests(WaiverTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.post_new().status_code, 302)
        self.waiver = Waiver.objects.get()
        StoredWaiverPDF._base_manager.filter(waiver_id=self.waiver.pk).delete()

    def test_backfill_creates_valid_artifact_once_and_records_generation_time(self):
        output = StringIO()
        call_command("backfill_waiver_pdfs", batch_size=1, stdout=output)
        artifact = StoredWaiverPDF.objects.get(waiver_id=self.waiver.pk)
        content = artifact.validated_content()
        self.assertGreaterEqual(artifact.created_at, self.waiver.signed_at)
        self.assertEqual(artifact.pdf_sha256, hashlib.sha256(content).hexdigest())
        self.assertIn("Stored 1 waiver PDF artifact", output.getvalue())

        original_hash = artifact.pdf_sha256
        original_created_at = artifact.created_at
        second_output = StringIO()
        call_command("backfill_waiver_pdfs", batch_size=1, stdout=second_output)
        artifact.refresh_from_db()
        self.assertEqual(artifact.pdf_sha256, original_hash)
        self.assertEqual(artifact.created_at, original_created_at)
        self.assertIn("Stored 0 waiver PDF artifact", second_output.getvalue())

    def test_backfill_rejects_invalid_batch_size(self):
        with self.assertRaisesMessage(CommandError, "--batch-size must be between 1 and 1000"):
            call_command("backfill_waiver_pdfs", batch_size=0)


class PublicCacheAndCopyTests(WaiverTestMixin, TestCase):
    def test_public_routes_are_no_store_and_toggle_blocks_direct_urls(self):
        for url in (
            reverse("waivers:start"),
            reverse("waivers:gymnast_status", args=[REGULAR]),
            reverse("waivers:new", args=[REGULAR]),
            reverse("waivers:returning_search", args=[REGULAR]),
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn("no-store", response["Cache-Control"])
        config = SiteConfiguration.objects.get(pk=1)
        config.show_online_waiver = False
        config.save()
        for url in (
            reverse("waivers:start"),
            reverse("waivers:new", args=[REGULAR]),
            reverse("waivers:returning_search", args=[REGULAR]),
        ):
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_copy_versions_are_commit_traceable_and_hashes_are_canonical(self):
        approved_hashes = {
            REGULAR: "e968971a67fc96279ffeaf96f43182e793377dfa1aea3feb621cd25c5c50506c",
            CAMP: "587e76773817edcce0f4befb0018a328c82bea2c0b15f9436dc94d4d0668fef6",
        }
        for agreement in AGREEMENTS.values():
            self.assertIn("b44ccb1", agreement.version)
            self.assertEqual(
                agreement.sha256,
                hashlib.sha256(agreement.text.encode("utf-8")).hexdigest(),
            )
        for enrollment_type, approved_hash in approved_hashes.items():
            self.assertEqual(AGREEMENTS[enrollment_type].sha256, approved_hash)
        response = self.client.get(reverse("waivers:new", args=[REGULAR]))
        self.assertContains(response, AGREEMENTS[REGULAR].version)
        self.assertContains(response, "ATHLETE MEMBERSHIP AGREEMENT")
        self.assertContains(response, "https://example.test/privacy")
