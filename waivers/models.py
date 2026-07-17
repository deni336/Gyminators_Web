import hashlib
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Max
from django.utils import timezone

from .constants import CAMP, REGULAR


def phone_digits(value):
    return "".join(character for character in (value or "") if character.isdigit())


class TimestampedProfile(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class GymnastProfileQuerySet(models.QuerySet):
    def returning_matches(self, *, last_name, date_of_birth, phone_last4, limit=5):
        """Return a deliberately bounded queryset for the three-factor lookup."""
        last4 = phone_digits(phone_last4)
        return (
            self.filter(
                last_name__iexact=last_name.strip(),
                date_of_birth=date_of_birth,
                guardian__phone_digits__endswith=last4,
            )
            .annotate(last_signed_at=Max("waivers__signed_at"))
            .order_by("last_name", "first_name", "id")[:limit]
        )


class GymnastProfile(TimestampedProfile):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, db_index=True)
    date_of_birth = models.DateField(db_index=True)
    age = models.PositiveSmallIntegerField()

    objects = GymnastProfileQuerySet.as_manager()

    class Meta:
        ordering = ("last_name", "first_name")
        indexes = [
            models.Index(
                fields=("last_name", "date_of_birth"),
                name="waiver_gym_last_dob_idx",
            )
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class GuardianProfile(TimestampedProfile):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gymnast = models.OneToOneField(
        GymnastProfile,
        related_name="guardian",
        on_delete=models.PROTECT,
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=40)
    phone_digits = models.CharField(max_length=30, db_index=True, editable=False)
    email = models.EmailField()
    occupation = models.CharField(max_length=160, blank=True)
    work_phone = models.CharField(max_length=40, blank=True)
    cell_phone = models.CharField(max_length=40, blank=True)
    second_guardian_name = models.CharField(max_length=200, blank=True)
    second_guardian_occupation = models.CharField(max_length=160, blank=True)
    second_guardian_work_phone = models.CharField(max_length=40, blank=True)
    second_guardian_cell_phone = models.CharField(max_length=40, blank=True)

    def save(self, *args, **kwargs):
        self.phone_digits = phone_digits(self.phone)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Guardian for {self.gymnast}"


class EmergencyContactProfile(TimestampedProfile):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gymnast = models.OneToOneField(
        GymnastProfile,
        related_name="emergency_contact",
        on_delete=models.PROTECT,
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    relationship = models.CharField(max_length=100)
    phone = models.CharField(max_length=40)
    phone_digits = models.CharField(max_length=30, db_index=True, editable=False)

    def save(self, *args, **kwargs):
        self.phone_digits = phone_digits(self.phone)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Emergency contact for {self.gymnast}"


class AuthorizedPickupProfile(TimestampedProfile):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gymnast = models.OneToOneField(
        GymnastProfile,
        related_name="authorized_pickup",
        on_delete=models.PROTECT,
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=40)
    phone_digits = models.CharField(max_length=30, db_index=True, editable=False)

    def save(self, *args, **kwargs):
        self.phone_digits = phone_digits(self.phone)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Authorized pickup for {self.gymnast}"


class ReturningSearchThrottle(models.Model):
    """Central brute-force bucket keyed only by a one-way client-IP HMAC."""

    client_key = models.CharField(primary_key=True, max_length=64, editable=False)
    window_started_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "returning-waiver search throttle"
        verbose_name_plural = "returning-waiver search throttles"
        indexes = [
            models.Index(fields=("updated_at",), name="waiver_throttle_updated_idx")
        ]

    def __str__(self):
        return "Returning-waiver search throttle bucket"


class WaiverSubmissionThrottle(models.Model):
    """Central signing-POST bucket keyed only by a one-way client-IP HMAC."""

    client_key = models.CharField(primary_key=True, max_length=64, editable=False)
    window_started_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "waiver submission throttle"
        verbose_name_plural = "waiver submission throttles"
        indexes = [
            models.Index(fields=("updated_at",), name="waiver_submit_updated_idx")
        ]

    def __str__(self):
        return "Waiver submission throttle bucket"


class ImmutableWaiverQuerySet(models.QuerySet):
    def bulk_create(self, objs, **kwargs):
        raise ValidationError("Signed waivers must be created through the signing service.")

    def bulk_update(self, objs, fields, **kwargs):
        raise ValidationError("Signed waiver snapshots cannot be changed.")

    def update(self, **kwargs):
        raise ValidationError("Signed waiver snapshots cannot be changed.")

    def delete(self):
        raise ValidationError("Signed waiver snapshots cannot be deleted.")


class Waiver(models.Model):
    REGULAR = REGULAR
    CAMP = CAMP
    ENROLLMENT_TYPES = ((REGULAR, "Regular enrollment"), (CAMP, "Camp enrollment"))

    NEW = "new"
    RETURNING = "returning"
    PARTICIPANT_STATUSES = ((NEW, "New gymnast"), (RETURNING, "Returning gymnast"))

    PARENT = "parent"
    LEGAL_GUARDIAN = "legal_guardian"
    SIGNER_CAPACITIES = ((PARENT, "Parent"), (LEGAL_GUARDIAN, "Legal guardian"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gymnast = models.ForeignKey(
        GymnastProfile,
        related_name="waivers",
        on_delete=models.PROTECT,
    )
    guardian = models.ForeignKey(
        GuardianProfile,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    emergency_contact = models.ForeignKey(
        EmergencyContactProfile,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    authorized_pickup = models.ForeignKey(
        AuthorizedPickupProfile,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    participant_status = models.CharField(max_length=12, choices=PARTICIPANT_STATUSES)
    enrollment_type = models.CharField(max_length=12, choices=ENROLLMENT_TYPES)
    activity_name = models.CharField(max_length=200, blank=True)
    typed_signer_name = models.CharField(max_length=200)
    signer_capacity = models.CharField(max_length=20, choices=SIGNER_CAPACITIES)
    pickup_verified = models.BooleanField(default=False)
    agreement_accepted = models.BooleanField()
    agreement_version = models.CharField(max_length=100)
    agreement_sha256 = models.CharField(max_length=64, editable=False)
    legal_text_snapshot = models.TextField()
    initials = models.JSONField()
    details = models.JSONField()
    signature_png = models.BinaryField(editable=False)
    signature_sha256 = models.CharField(max_length=64, editable=False)
    submission_key = models.CharField(max_length=64, unique=True, editable=False)
    signed_at = models.DateTimeField(default=timezone.now, editable=False)

    objects = ImmutableWaiverQuerySet.as_manager()

    class Meta:
        ordering = ("-signed_at",)
        indexes = [
            models.Index(fields=("signed_at",), name="waiver_signed_at_idx"),
            models.Index(
                fields=("enrollment_type", "signed_at"),
                name="waiver_type_signed_idx",
            ),
            models.Index(
                fields=("gymnast", "signed_at"),
                name="waiver_gym_signed_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(agreement_accepted=True),
                name="waiver_agreement_required",
            )
        ]

    def clean(self):
        errors = {}
        signature = bytes(self.signature_png or b"")
        if not signature:
            errors["signature_png"] = "A validated PNG signature is required."
        if not self.legal_text_snapshot:
            errors["legal_text_snapshot"] = "The legal text snapshot is required."
        if not self.agreement_accepted:
            errors["agreement_accepted"] = "The signer must explicitly accept the agreement."
        if self.enrollment_type == self.CAMP and not (self.activity_name or "").strip():
            errors["activity_name"] = "The camp activity is required."
        if self.participant_status == self.NEW:
            if not self.guardian_id:
                errors["guardian"] = "A new-gymnast waiver requires its guardian profile."
            if not self.emergency_contact_id:
                errors["emergency_contact"] = (
                    "A new-gymnast waiver requires its emergency-contact profile."
                )
            if not self.authorized_pickup_id:
                errors["authorized_pickup"] = (
                    "A new-gymnast waiver requires its authorized-pickup profile."
                )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Signed waiver snapshots cannot be changed.")
        self.agreement_sha256 = hashlib.sha256(
            self.legal_text_snapshot.encode("utf-8")
        ).hexdigest()
        self.signature_sha256 = hashlib.sha256(bytes(self.signature_png or b"")).hexdigest()
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Signed waiver snapshots cannot be deleted.")

    def __str__(self):
        return f"{self.get_enrollment_type_display()} waiver {self.id}"


class ImmutableStoredWaiverPDFQuerySet(models.QuerySet):
    def bulk_create(self, objs, **kwargs):
        raise ValidationError("Stored signed-waiver PDFs must be created individually.")

    def bulk_update(self, objs, fields, **kwargs):
        raise ValidationError("Stored signed-waiver PDFs cannot be changed.")

    def update(self, **kwargs):
        raise ValidationError("Stored signed-waiver PDFs cannot be changed.")

    def delete(self):
        raise ValidationError("Stored signed-waiver PDFs cannot be deleted.")


class StoredWaiverPDF(models.Model):
    """The exact PDF artifact committed for a signed waiver."""

    waiver = models.OneToOneField(
        Waiver,
        related_name="stored_pdf",
        primary_key=True,
        on_delete=models.PROTECT,
    )
    pdf_bytes = models.BinaryField(editable=False)
    pdf_sha256 = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(
        auto_now_add=True,
        editable=False,
        help_text=(
            "When this exact artifact was generated; for a legacy backfill this is "
            "later than the waiver's signed timestamp."
        ),
    )

    objects = ImmutableStoredWaiverPDFQuerySet.as_manager()

    class Meta:
        verbose_name = "stored signed-waiver PDF"
        verbose_name_plural = "stored signed-waiver PDFs"

    def validated_content(self):
        """Return bytes only after hash, parser, and signed-content validation."""
        content = bytes(self.pdf_bytes or b"")
        actual_hash = hashlib.sha256(content).hexdigest()
        if self.pdf_sha256 != actual_hash:
            raise ValidationError({"pdf_bytes": "The stored PDF hash does not match."})
        # Local import avoids a model/PDF module cycle at application startup.
        from .pdf import WaiverPDFValidationError, validate_waiver_pdf

        try:
            validate_waiver_pdf(content, self.waiver)
        except WaiverPDFValidationError as exc:
            raise ValidationError(
                {"pdf_bytes": "The signed-waiver PDF is not readable or complete."}
            ) from exc
        return content

    def clean(self):
        self.validated_content()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Stored signed-waiver PDFs cannot be changed.")
        self.pdf_sha256 = hashlib.sha256(bytes(self.pdf_bytes or b"")).hexdigest()
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Stored signed-waiver PDFs cannot be deleted.")

    def __str__(self):
        return f"Stored PDF for waiver {self.waiver_id}"
