import logging
from datetime import timedelta
from functools import partial

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models, transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from PIL import Image, UnidentifiedImageError


logger = logging.getLogger(__name__)


# Retained only so historical migration 0001 can be replayed before the
# Jackrabbit-only cleanup migration removes the old payment-request table.
def default_payment_expiry():
    return timezone.now() + timedelta(days=7)

def validate_image_upload(upload):
    if upload.size > 8 * 1024 * 1024:
        raise ValidationError("Images must be 8 MB or smaller.")
    try:
        image = Image.open(upload)
        width, height = image.size
        if (image.format or "").upper() not in {"JPEG", "PNG", "WEBP"}:
            raise ValidationError("Upload a valid JPEG, PNG, or WebP image.")
        image.verify()
    except ValidationError:
        raise
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError("Upload a valid JPEG, PNG, or WebP image.") from exc
    finally:
        try:
            upload.seek(0)
        except (AttributeError, OSError):
            pass
    if width > 6000 or height > 6000 or width * height > 24_000_000:
        raise ValidationError("Images must be no larger than 6000×6000 or 24 megapixels.")


image_validators = [FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), validate_image_upload]


class SiteConfiguration(models.Model):
    gym_name = models.CharField(max_length=120, default="Gyminators Gymnastics")
    announcement = models.CharField(max_length=160, default="Jacksonville’s home for confident kids")
    phone = models.CharField(max_length=30, default="(904) 388-5533")
    phone_link = models.CharField(max_length=40, default="tel:9043885533", editable=False)
    email = models.EmailField(default="gyminators.office@gmail.com")
    street_address = models.CharField(max_length=160, default="4603 Shirley Ave")
    city_state_zip = models.CharField(max_length=160, default="Jacksonville, FL 32210")
    hours_note = models.CharField(max_length=160, default="Call for current hours")
    registration_url = models.URLField(default="https://app3.jackrabbitclass.com/regv2.asp?id=154877")
    portal_url = models.URLField(default="https://app.jackrabbitclass.com/jr4.0/ParentPortal/Login?orgId=154877")
    class_schedule_url = models.URLField(default="https://app.jackrabbitclass.com/jr3.0/Openings/OpeningsDirect?OrgID=154877")
    jackrabbit_owner_url = models.URLField(default="https://app.jackrabbitclass.com/jr4.0/Login")
    staff_portal_url = models.URLField(default="https://app.jackrabbitclass.com/jr3.0/TimeClock/StaffLogin?orgId=154877")
    map_url = models.URLField(default="https://maps.google.com/?q=4603+Shirley+Ave+Jacksonville+FL+32210")
    accessibility_url = models.URLField(default="https://www.gyminators.com/our-commitment-to-accessibility")
    opened_year = models.PositiveSmallIntegerField(default=2003)
    age_range = models.CharField(max_length=80, default="Walking–17")

    meta_title = models.CharField(max_length=160, default="Gyminators Gymnastics | Jacksonville")
    meta_description = models.CharField(max_length=320, default="Jacksonville gymnastics, tumbling, camps and events for children and teens.")
    logo = models.ImageField(upload_to="site/", blank=True, validators=image_validators)
    favicon = models.ImageField(upload_to="site/", blank=True, validators=image_validators)
    logo_alt = models.CharField(max_length=160, default="Gyminators Gymnastics")

    hero_eyebrow = models.CharField(max_length=120, default="Gymnastics • Tumbling • More")
    hero_heading = models.CharField(max_length=120, default="Where kids")
    hero_accent = models.CharField(max_length=80, default="rise.")
    hero_body = models.TextField(default="Building strength, confidence, and lifelong friendships—one skill at a time.")
    hero_image = models.ImageField(upload_to="site/hero/", blank=True, validators=image_validators)
    hero_image_alt = models.CharField(max_length=200, default="Young gymnast practicing in a bright gym")
    hero_primary_button = models.CharField(max_length=80, default="Book a free trial")
    hero_secondary_button = models.CharField(max_length=80, default="Explore programs")
    header_button_text = models.CharField(max_length=80, default="Try a class")

    intro_eyebrow = models.CharField(max_length=120, default="More than a gym")
    intro_heading = models.CharField(max_length=200, default="Strong bodies. Brave minds.")
    intro_accent = models.CharField(max_length=100, default="Happy kids.")
    intro_lead = models.TextField(default="At Gyminators, every child gets a place to move, learn, and belong.")
    intro_body = models.TextField(default="Our instructors meet athletes where they are and help them discover what they’re capable of—inside our fully air-conditioned Jacksonville facility.")

    payment_eyebrow = models.CharField(max_length=120, default="Jackrabbit registration & billing")
    payment_heading = models.CharField(max_length=160, default="Classes and payments in one place.")
    payment_body = models.TextField(default="Gyminators uses Jackrabbit for registration, enrollment, family accounts, policies, and payments.")
    payment_benefit_one = models.CharField(max_length=160, default="Enroll in classes and events")
    payment_benefit_two = models.CharField(max_length=160, default="Review charges and payment history")
    payment_benefit_three = models.CharField(max_length=160, default="Manage policies and family details")
    payment_portal_note = models.CharField(max_length=240, default="New families begin with Online Registration. Existing families should use their Parent Portal account.")
    payment_new_heading = models.CharField(max_length=120, default="New families")
    payment_new_body = models.TextField(default="Create your family account, choose a class or trial, complete required policies, and provide billing details in Jackrabbit.")
    payment_new_button = models.CharField(max_length=80, default="Register with Jackrabbit")
    payment_existing_heading = models.CharField(max_length=120, default="Current families")
    payment_existing_body = models.TextField(default="Use the Parent Portal to view your balance, make payments, manage billing information, and enroll in available programs.")
    payment_existing_button = models.CharField(max_length=80, default="Open Parent Portal")
    show_payments = models.BooleanField(default=True)

    programs_eyebrow = models.CharField(max_length=120, default="Find their fit")
    programs_heading = models.CharField(max_length=160, default="Programs that grow with your child.")
    programs_body = models.TextField(default="From first steps to competitive routines, there’s a place to start—and room to soar.")
    show_programs = models.BooleanField(default=True)

    why_eyebrow = models.CharField(max_length=120, default="The Gyminators difference")
    why_heading = models.CharField(max_length=200, default="They’ll learn a lot more than gymnastics.")
    why_body = models.TextField(default="Every class is a chance to practice courage, focus, and resilience—with coaches who celebrate effort as much as achievement.")
    why_image = models.ImageField(upload_to="site/why/", blank=True, validators=image_validators)
    why_image_alt = models.CharField(max_length=200, default="Child enjoying a Gyminators event")
    show_why = models.BooleanField(default=True)

    events_eyebrow = models.CharField(max_length=120, default="Beyond weekly classes")
    events_heading = models.CharField(max_length=160, default="More ways to move.")
    events_body = models.TextField(default="School’s out? Birthday coming up? We keep the good energy going all year long. Call to confirm current schedules and availability.")
    show_events = models.BooleanField(default=True)

    trial_eyebrow = models.CharField(max_length=120, default="Your first move is free")
    trial_heading = models.CharField(max_length=160, default="Come see what they can do.")
    trial_body = models.TextField(default="New families can try a class, meet our coaches, and find the right program—no pressure, no commitment.")
    trial_button_text = models.CharField(max_length=80, default="Claim a free trial")
    show_trial = models.BooleanField(default=True)
    footer_body = models.TextField(default="Helping Jacksonville kids grow stronger, braver, and more confident through movement.")
    footer_credentials = models.CharField(max_length=200, default="USA Gymnastics & AAU Member • Jacksonville, Florida")
    privacy_url = models.URLField(blank=True, help_text="Optional link to the approved privacy policy.")
    terms_url = models.URLField(blank=True, help_text="Optional link to the approved website or payment terms.")
    cancellation_url = models.URLField(blank=True, help_text="Optional link to the approved cancellation and refund policy.")
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        verbose_name = "site configuration"
        verbose_name_plural = "site configuration"

    @classmethod
    def get_solo(cls):
        return cls.objects.first() or cls()

    def save(self, *args, **kwargs):
        self.pk = 1
        digits = "".join(character for character in self.phone if character.isdigit())
        self.phone_link = f"tel:{digits}"
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Site configuration cannot be deleted.")

    def __str__(self):
        return "Website content and business details"


class Program(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    age_range = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    image = models.ImageField(upload_to="programs/", blank=True, validators=image_validators)
    image_alt = models.CharField(max_length=200)
    fallback_image = models.CharField(max_length=120, blank=True, help_text="Bundled static image used until an upload is provided.")
    call_to_action_url = models.URLField(blank=True)
    call_to_action_label = models.CharField(max_length=120, default="Register")
    featured = models.BooleanField(default=False, help_text="Show as a full card on the homepage.")
    published = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ("display_order", "name")

    def __str__(self):
        return self.name


class Event(models.Model):
    title = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    image = models.ImageField(upload_to="events/", blank=True, validators=image_validators)
    image_alt = models.CharField(max_length=200, blank=True)
    external_url = models.URLField(blank=True)
    call_to_action_label = models.CharField(max_length=100, default="Learn more")
    schedule_text = models.CharField(max_length=200, blank=True, help_text="Optional public schedule note, such as ‘Call for current dates’.")
    price_text = models.CharField(max_length=120, blank=True, help_text="Optional public price note. Confirm with the owner before publishing.")
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    publish_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    published = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ("display_order", "starts_at", "title")

    @property
    def is_visible(self):
        now = timezone.now()
        return self.published and (not self.publish_at or self.publish_at <= now) and (not self.expires_at or self.expires_at > now)

    def clean(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "End time must be after the start time."})
        if self.publish_at and self.expires_at and self.expires_at <= self.publish_at:
            raise ValidationError({"expires_at": "Expiration must be after publication."})
        if self.image and not self.image_alt:
            raise ValidationError({"image_alt": "Alternative text is required for uploaded event images."})

    def __str__(self):
        return self.title


class HomepageFeature(models.Model):
    SECTIONS = (("proof", "Hero proof point"), ("benefit", "Why Gyminators benefit"))
    section = models.CharField(max_length=20, choices=SECTIONS)
    title = models.CharField(max_length=100)
    body = models.CharField(max_length=200)
    published = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ("section", "display_order", "title")

    def __str__(self):
        return f"{self.get_section_display()}: {self.title}"


class SocialLink(models.Model):
    label = models.CharField(max_length=60)
    url = models.URLField()
    published = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ("display_order", "label")

    def __str__(self):
        return self.label


MANAGED_IMAGE_FIELDS = {
    SiteConfiguration: ("logo", "favicon", "hero_image", "why_image"),
    Program: ("image",),
    Event: ("image",),
}


def _delete_unreferenced_image(storage, name):
    if not name:
        return
    for model, field_names in MANAGED_IMAGE_FIELDS.items():
        if any(model._default_manager.filter(**{field_name: name}).exists() for field_name in field_names):
            return
    try:
        storage.delete(name)
    except Exception:
        logger.exception("Could not delete superseded website image %s", name)


@receiver(pre_save)
def remember_replaced_images(sender, instance, **kwargs):
    field_names = MANAGED_IMAGE_FIELDS.get(sender)
    if not field_names or not instance.pk:
        return
    previous = sender._default_manager.filter(pk=instance.pk).first()
    if not previous:
        return
    superseded = []
    for field_name in field_names:
        old_file = getattr(previous, field_name)
        new_file = getattr(instance, field_name)
        old_name = getattr(old_file, "name", "")
        new_name = getattr(new_file, "name", "")
        if old_name and old_name != new_name:
            superseded.append((old_file.storage, old_name))
    instance._superseded_image_files = superseded


@receiver(post_save)
def schedule_replaced_image_cleanup(sender, instance, **kwargs):
    if sender not in MANAGED_IMAGE_FIELDS:
        return
    superseded = getattr(instance, "_superseded_image_files", ())
    for storage, name in superseded:
        transaction.on_commit(partial(_delete_unreferenced_image, storage, name))
    if hasattr(instance, "_superseded_image_files"):
        del instance._superseded_image_files


@receiver(post_delete)
def schedule_deleted_image_cleanup(sender, instance, **kwargs):
    field_names = MANAGED_IMAGE_FIELDS.get(sender)
    if not field_names:
        return
    for field_name in field_names:
        deleted_file = getattr(instance, field_name)
        if deleted_file and deleted_file.name:
            transaction.on_commit(partial(_delete_unreferenced_image, deleted_file.storage, deleted_file.name))
