from django import forms
from django.utils.text import slugify

from .models import Event, HomepageFeature, Program, SiteConfiguration, SocialLink


IMAGE_UPLOAD_RULES = "JPEG, PNG, or WebP; maximum 8 MB, 6,000 pixels per side, and 24 megapixels."


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, forms.ImageField):
                field.widget.template_name = "website/widgets/cms_image_input.html"
                field.widget.clear_checkbox_label = "Remove current picture"
                field.widget.attrs["accept"] = "image/jpeg,image/png,image/webp"
                field.widget.attrs["data-image-input"] = ""
            if isinstance(field.widget, forms.CheckboxInput):
                continue
            field.widget.attrs.setdefault("class", "cmsInput")


class SiteConfigurationForm(StyledModelForm):
    class Meta:
        model = SiteConfiguration
        exclude = ("phone_link", "updated_at")
        widgets = {
            name: forms.Textarea(attrs={"rows": 3})
            for name in (
                "hero_body",
                "intro_lead",
                "intro_body",
                "payment_body",
                "payment_portal_note",
                "payment_new_body",
                "payment_existing_body",
                "programs_body",
                "why_body",
                "events_body",
                "trial_body",
                "footer_body",
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        recommendations = {
            "logo": "Use a clear logo with a transparent background when available.",
            "favicon": "Use a small square picture; a simple logo mark works best.",
            "hero_image": "Use a wide landscape photograph. The edges may crop on phones and smaller screens.",
            "why_image": "Use a landscape photograph with the main subject near the center.",
        }
        for name, recommendation in recommendations.items():
            self.fields[name].help_text = f"{recommendation} {IMAGE_UPLOAD_RULES}"
        self.fields["logo_alt"].help_text = "Briefly identify the logo for visitors using screen readers."
        self.fields["hero_image_alt"].help_text = "Describe the important subject of the hero photograph in one short sentence."
        self.fields["why_image_alt"].help_text = "Describe the important subject of this photograph in one short sentence."

    def save(self, commit=True):
        instance = super().save(commit=False)
        digits = "".join(character for character in instance.phone if character.isdigit())
        instance.phone_link = f"tel:{digits}"
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ProgramForm(StyledModelForm):
    class Meta:
        model = Program
        exclude = ("fallback_image",)
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["image"].help_text = (
            "Use a landscape photograph for the program card. It will crop to fill the card and is shown only "
            "when Featured is selected. "
            f"{IMAGE_UPLOAD_RULES}"
        )
        self.fields["image_alt"].help_text = "Describe the program photograph in one short sentence."

    def clean_slug(self):
        return self.cleaned_data.get("slug") or slugify(self.cleaned_data.get("name", ""))


class EventForm(StyledModelForm):
    class Meta:
        model = Event
        fields = "__all__"
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "publish_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["image"].help_text = (
            "Use a landscape photograph. It appears as a small event thumbnail. "
            f"{IMAGE_UPLOAD_RULES}"
        )
        self.fields["image_alt"].help_text = "Required when a picture is uploaded; describe it in one short sentence."
        for name in ("starts_at", "ends_at", "publish_at", "expires_at"):
            self.fields[name].input_formats = ["%Y-%m-%dT%H:%M"]

    def clean_slug(self):
        return self.cleaned_data.get("slug") or slugify(self.cleaned_data.get("title", ""))


class HomepageFeatureForm(StyledModelForm):
    class Meta:
        model = HomepageFeature
        fields = "__all__"


class SocialLinkForm(StyledModelForm):
    class Meta:
        model = SocialLink
        fields = "__all__"
