from django import forms
from django.utils.text import slugify

from .models import Event, HomepageFeature, Program, SiteConfiguration, SocialLink


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
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

