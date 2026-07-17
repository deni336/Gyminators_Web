import base64
from io import BytesIO
import re

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from PIL import Image, ImageChops, UnidentifiedImageError

from .constants import CAMP, get_agreement
from .models import Waiver, phone_digits


MAX_SIGNATURE_BYTES = 750 * 1024
MAX_SIGNATURE_WIDTH = 1800
MAX_SIGNATURE_HEIGHT = 900
MIN_SIGNATURE_INK_PIXELS = 100
MIN_SIGNATURE_INK_WIDTH = 40
MIN_SIGNATURE_INK_HEIGHT = 10
DATA_URL_PATTERN = re.compile(r"\Adata:image/png;base64,([A-Za-z0-9+/=\r\n]+)\Z")


def validate_phone(value):
    digits = phone_digits(value)
    if not 7 <= len(digits) <= 15:
        raise ValidationError("Enter a phone number with 7 to 15 digits.")


def decode_signature_png(value):
    """Validate a canvas data URL and return a canonical, nonblank PNG."""
    match = DATA_URL_PATTERN.fullmatch((value or "").strip())
    if not match:
        raise ValidationError("Draw a signature in the signature box.")
    try:
        raw = base64.b64decode(match.group(1), validate=True)
    except (ValueError, TypeError) as exc:
        raise ValidationError("The signature image is invalid. Please clear and sign again.") from exc
    if not raw or len(raw) > MAX_SIGNATURE_BYTES or not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValidationError("The signature image is invalid. Please clear and sign again.")

    try:
        with Image.open(BytesIO(raw)) as probe:
            if (probe.format or "").upper() != "PNG":
                raise ValidationError("The signature must be a PNG image.")
            width, height = probe.size
            if (
                width < 2
                or height < 2
                or width > MAX_SIGNATURE_WIDTH
                or height > MAX_SIGNATURE_HEIGHT
            ):
                raise ValidationError("The signature image dimensions are invalid.")
            probe.verify()

        with Image.open(BytesIO(raw)) as image:
            rgba = image.convert("RGBA")
            red, green, blue, alpha = rgba.split()
            darkest = ImageChops.darker(ImageChops.darker(red, green), blue)
            dark_mask = darkest.point([255 if value < 245 else 0 for value in range(256)])
            alpha_mask = alpha.point([255 if value > 10 else 0 for value in range(256)])
            ink_mask = ImageChops.multiply(dark_mask, alpha_mask)
            ink_pixels = ink_mask.histogram()[255]
            bounding_box = ink_mask.getbbox()
            if bounding_box:
                min_x, min_y, max_x, max_y = bounding_box
                ink_width = max_x - min_x
                ink_height = max_y - min_y
            else:
                ink_width = ink_height = 0
            if (
                ink_pixels < MIN_SIGNATURE_INK_PIXELS
                or ink_width < MIN_SIGNATURE_INK_WIDTH
                or ink_height < MIN_SIGNATURE_INK_HEIGHT
            ):
                raise ValidationError("Draw a signature in the signature box.")
            output = BytesIO()
            rgba.save(output, format="PNG", compress_level=6)
            canonical = output.getvalue()
    except ValidationError:
        raise
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError("The signature image is invalid. Please clear and sign again.") from exc

    if len(canonical) > MAX_SIGNATURE_BYTES:
        raise ValidationError("The signature image is too large. Please clear and sign again.")
    return canonical


def text_field(label, *, required=True, max_length=160, **kwargs):
    return forms.CharField(
        label=label,
        required=required,
        max_length=max_length,
        strip=True,
        **kwargs,
    )


def phone_field(label, *, required=True):
    return forms.CharField(
        label=label,
        required=required,
        max_length=40,
        strip=True,
        validators=[validate_phone] if required else [],
        widget=forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel"}),
    )


class WaiverSigningForm(forms.Form):
    """Shared signing behavior; profile fields are supplied by subclasses."""

    typed_signer_name = text_field(
        "Signer’s full legal name",
        max_length=200,
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
    )
    signer_capacity = forms.ChoiceField(
        label="I am the gymnast’s",
        choices=Waiver.SIGNER_CAPACITIES,
    )
    agreement_accepted = forms.BooleanField(
        label="I have read and agree to the complete agreement above.",
        required=True,
    )
    signature_data = forms.CharField(
        required=True,
        widget=forms.HiddenInput(attrs={"data-signature-output": ""}),
    )
    submission_token = forms.CharField(required=True, widget=forms.HiddenInput())

    def __init__(self, *args, enrollment_type, **kwargs):
        self.enrollment_type = enrollment_type
        self.agreement = get_agreement(enrollment_type)
        super().__init__(*args, **kwargs)
        initials_position = list(self.fields).index("typed_signer_name")
        for clause in range(1, self.agreement.clause_count + 1):
            self.fields[f"initial_{clause}"] = forms.CharField(
                label=f"Clause {clause} initials",
                max_length=6,
                min_length=1,
                strip=True,
                widget=forms.TextInput(
                    attrs={
                        "autocomplete": "off",
                        "class": "initials-input",
                        "aria-describedby": "initials-help",
                    }
                ),
            )
        ordered = list(self.fields)
        initial_names = [f"initial_{number}" for number in range(1, self.agreement.clause_count + 1)]
        ordered = [name for name in ordered if name not in initial_names]
        ordered[initials_position:initials_position] = initial_names
        self.order_fields(ordered)

    @property
    def initial_fields(self):
        return [self[f"initial_{number}"] for number in range(1, self.agreement.clause_count + 1)]

    @property
    def signing_fields(self):
        return [self[name] for name in ("typed_signer_name", "signer_capacity", "agreement_accepted")]

    def clean_signature_data(self):
        return decode_signature_png(self.cleaned_data["signature_data"])

    def clean(self):
        cleaned = super().clean()
        signature = cleaned.get("signature_data")
        if signature:
            cleaned["signature_png"] = signature
        return cleaned


class EnrollmentFieldsMixin:
    common_enrollment_names = (
        "activity_name",
        "home_address",
        "city",
        "state",
        "zip_code",
        "gender",
        "home_phone",
        "guardian_occupation",
        "guardian_work_phone",
        "guardian_cell_phone",
        "second_guardian_name",
        "second_guardian_occupation",
        "second_guardian_work_phone",
        "second_guardian_cell_phone",
        "primary_insurance",
        "policy_number",
        "citizen_usa",
        "medical_info",
        "referral_source",
    )

    def configure_enrollment_fields(self, *, returning):
        core_required = not returning
        if self.enrollment_type == CAMP:
            for name in (
                "state",
                "gender",
                "guardian_occupation",
                "second_guardian_name",
                "second_guardian_occupation",
                "second_guardian_work_phone",
                "second_guardian_cell_phone",
                "primary_insurance",
                "policy_number",
                "citizen_usa",
            ):
                self.fields.pop(name, None)
            self.fields["activity_name"].required = True
        else:
            self.fields.pop("activity_name", None)
            self.fields["state"].required = core_required
            self.fields["gender"].required = core_required

        for name in ("home_address", "city", "zip_code"):
            self.fields[name].required = core_required

    def clean(self):
        cleaned = super().clean()
        for name in (
            "home_phone",
            "guardian_work_phone",
            "guardian_cell_phone",
            "second_guardian_work_phone",
            "second_guardian_cell_phone",
        ):
            value = cleaned.get(name)
            if value:
                try:
                    validate_phone(value)
                except ValidationError as exc:
                    self.add_error(name, exc)
        return cleaned


class NewWaiverForm(EnrollmentFieldsMixin, WaiverSigningForm):
    gymnast_first_name = text_field(
        "Gymnast first name", max_length=100, widget=forms.TextInput(attrs={"autocomplete": "given-name"})
    )
    gymnast_last_name = text_field(
        "Gymnast last name", max_length=100, widget=forms.TextInput(attrs={"autocomplete": "family-name"})
    )
    gymnast_dob = forms.DateField(
        label="Date of birth",
        widget=forms.DateInput(attrs={"type": "date", "autocomplete": "bday"}),
    )
    gymnast_age = forms.IntegerField(label="Age", min_value=0, max_value=25)

    guardian_first_name = text_field(
        "Parent or guardian first name",
        max_length=100,
        widget=forms.TextInput(attrs={"autocomplete": "given-name"}),
    )
    guardian_last_name = text_field(
        "Parent or guardian last name",
        max_length=100,
        widget=forms.TextInput(attrs={"autocomplete": "family-name"}),
    )
    guardian_phone = phone_field("Parent or guardian phone")
    guardian_email = forms.EmailField(
        label="Parent or guardian email",
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )

    activity_name = text_field("Camp activity", required=False, max_length=200)
    home_address = text_field(
        "Home address", required=False, max_length=200, widget=forms.TextInput(attrs={"autocomplete": "street-address"})
    )
    city = text_field("City", required=False, max_length=100, widget=forms.TextInput(attrs={"autocomplete": "address-level2"}))
    state = text_field("State", required=False, max_length=60, widget=forms.TextInput(attrs={"autocomplete": "address-level1"}))
    zip_code = text_field(
        "ZIP code",
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={"autocomplete": "postal-code", "inputmode": "numeric"}),
    )
    gender = text_field("Gender", required=False, max_length=80)
    home_phone = phone_field("Home phone", required=False)
    guardian_occupation = text_field("Parent or guardian occupation", required=False)
    guardian_work_phone = phone_field("Parent or guardian work phone", required=False)
    guardian_cell_phone = phone_field("Parent or guardian cell phone, if different", required=False)
    second_guardian_name = text_field("Second parent or guardian name", required=False, max_length=200)
    second_guardian_occupation = text_field("Second parent or guardian occupation", required=False)
    second_guardian_work_phone = phone_field("Second parent or guardian work phone", required=False)
    second_guardian_cell_phone = phone_field("Second parent or guardian cell phone", required=False)
    primary_insurance = text_field("Primary medical insurance", required=False, max_length=200)
    policy_number = text_field("Policy number", required=False, max_length=100)
    citizen_usa = forms.ChoiceField(
        label="Citizen of the USA?",
        required=False,
        choices=(("", "Prefer not to answer"), ("yes", "Yes"), ("no", "No")),
    )
    medical_info = forms.CharField(
        label="Medical conditions, allergies, or pertinent information",
        required=False,
        max_length=3000,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    referral_source = text_field("How did you hear about us / referred by", required=False, max_length=300)

    emergency_first_name = text_field("Emergency contact first name", max_length=100)
    emergency_last_name = text_field("Emergency contact last name", max_length=100)
    emergency_relationship = text_field("Emergency contact relationship", max_length=100)
    emergency_phone = phone_field("Emergency contact phone")

    pickup_first_name = text_field("Authorized pickup first name", max_length=100)
    pickup_last_name = text_field("Authorized pickup last name", max_length=100)
    pickup_phone = phone_field("Authorized pickup phone")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.configure_enrollment_fields(returning=False)

    def clean(self):
        cleaned = super().clean()
        dob = cleaned.get("gymnast_dob")
        posted_age = cleaned.get("gymnast_age")
        if dob:
            today = timezone.localdate()
            if dob > today:
                self.add_error("gymnast_dob", "Date of birth cannot be in the future.")
            else:
                actual_age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                if posted_age is not None and posted_age != actual_age:
                    self.add_error(
                        "gymnast_age",
                        f"Age must be {actual_age} for the date of birth entered.",
                    )
        return cleaned

    @property
    def profile_fieldsets(self):
        groups = [
            ("Gymnast", ("gymnast_first_name", "gymnast_last_name", "gymnast_dob", "gymnast_age")),
            (
                "Parent or guardian",
                ("guardian_first_name", "guardian_last_name", "guardian_phone", "guardian_email"),
            ),
            ("Enrollment information", self.common_enrollment_names),
            (
                "Emergency contact",
                ("emergency_first_name", "emergency_last_name", "emergency_relationship", "emergency_phone"),
            ),
            ("Authorized pickup", ("pickup_first_name", "pickup_last_name", "pickup_phone")),
        ]
        return [
            (title, [self[name] for name in names if name in self.fields])
            for title, names in groups
        ]


class ReturningWaiverForm(EnrollmentFieldsMixin, WaiverSigningForm):
    guardian_first_name = NewWaiverForm.base_fields["guardian_first_name"]
    guardian_last_name = NewWaiverForm.base_fields["guardian_last_name"]
    guardian_phone = NewWaiverForm.base_fields["guardian_phone"]
    guardian_email = NewWaiverForm.base_fields["guardian_email"]

    activity_name = NewWaiverForm.base_fields["activity_name"]
    home_address = NewWaiverForm.base_fields["home_address"]
    city = NewWaiverForm.base_fields["city"]
    state = NewWaiverForm.base_fields["state"]
    zip_code = NewWaiverForm.base_fields["zip_code"]
    gender = NewWaiverForm.base_fields["gender"]
    home_phone = NewWaiverForm.base_fields["home_phone"]
    guardian_occupation = NewWaiverForm.base_fields["guardian_occupation"]
    guardian_work_phone = NewWaiverForm.base_fields["guardian_work_phone"]
    guardian_cell_phone = NewWaiverForm.base_fields["guardian_cell_phone"]
    second_guardian_name = NewWaiverForm.base_fields["second_guardian_name"]
    second_guardian_occupation = NewWaiverForm.base_fields["second_guardian_occupation"]
    second_guardian_work_phone = NewWaiverForm.base_fields["second_guardian_work_phone"]
    second_guardian_cell_phone = NewWaiverForm.base_fields["second_guardian_cell_phone"]
    primary_insurance = NewWaiverForm.base_fields["primary_insurance"]
    policy_number = NewWaiverForm.base_fields["policy_number"]
    citizen_usa = NewWaiverForm.base_fields["citizen_usa"]
    medical_info = NewWaiverForm.base_fields["medical_info"]
    referral_source = NewWaiverForm.base_fields["referral_source"]

    emergency_first_name = NewWaiverForm.base_fields["emergency_first_name"]
    emergency_last_name = NewWaiverForm.base_fields["emergency_last_name"]
    emergency_relationship = NewWaiverForm.base_fields["emergency_relationship"]
    emergency_phone = NewWaiverForm.base_fields["emergency_phone"]

    pickup_first_name = NewWaiverForm.base_fields["pickup_first_name"]
    pickup_last_name = NewWaiverForm.base_fields["pickup_last_name"]
    pickup_phone = NewWaiverForm.base_fields["pickup_phone"]
    pickup_verified = forms.BooleanField(
        label="I verified the authorized pickup information for today.",
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.configure_enrollment_fields(returning=True)

    @property
    def profile_fieldsets(self):
        groups = [
            (
                "Parent or guardian",
                ("guardian_first_name", "guardian_last_name", "guardian_phone", "guardian_email"),
            ),
            ("Enrollment information", self.common_enrollment_names),
            (
                "Emergency contact",
                (
                    "emergency_first_name",
                    "emergency_last_name",
                    "emergency_relationship",
                    "emergency_phone",
                ),
            ),
            (
                "Verify authorized pickup",
                ("pickup_first_name", "pickup_last_name", "pickup_phone", "pickup_verified"),
            ),
        ]
        return [
            (title, [self[name] for name in names if name in self.fields])
            for title, names in groups
        ]


class ReturningSearchForm(forms.Form):
    gymnast_last_name = text_field(
        "Gymnast last name",
        max_length=100,
        widget=forms.TextInput(attrs={"autocomplete": "family-name"}),
    )
    gymnast_dob = forms.DateField(
        label="Gymnast date of birth",
        widget=forms.DateInput(attrs={"type": "date", "autocomplete": "bday"}),
    )
    guardian_phone_last4 = forms.CharField(
        label="Last 4 digits of parent or guardian phone",
        min_length=4,
        max_length=4,
        strip=True,
        widget=forms.TextInput(
            attrs={"inputmode": "numeric", "pattern": "[0-9]{4}", "autocomplete": "off"}
        ),
    )

    def clean_guardian_phone_last4(self):
        value = phone_digits(self.cleaned_data["guardian_phone_last4"])
        if len(value) != 4:
            raise ValidationError("Enter exactly 4 phone digits.")
        return value
