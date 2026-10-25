from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core import signing

from common.images import validate_uploaded_image

from .models import Profile


class LocationCoordinatesForm(forms.Form):
    latitude = forms.FloatField(min_value=-90, max_value=90)
    longitude = forms.FloatField(min_value=-180, max_value=180)


class ProfileLocationForm(forms.ModelForm):
    location_token = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Profile
        fields = ("district", "city", "province")
        labels = {
            "district": "District",
            "city": "City or regency",
            "province": "Province",
        }

    def __init__(self, *args, user_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = user_id
        self.resolved_location = None
        for field in self.fields.values():
            field.widget.attrs["class"] = "input swap-input w-full"
        self.fields["district"].help_text = "Optional."
        self.fields["city"].required = True
        self.fields["province"].required = True

    def clean(self):
        cleaned = super().clean()
        token = cleaned.get("location_token")
        if token:
            try:
                location = signing.loads(
                    token, salt="user_profile.location", max_age=1800
                )
            except signing.BadSignature:
                raise forms.ValidationError(
                    "Your detected location has expired or is invalid. "
                    "Please detect it again or enter your area manually."
                ) from None
            if location["user_id"] != self.user_id:
                raise forms.ValidationError("Please detect your location again.")
            if all(cleaned.get(field) == location[field] for field in self.Meta.fields):
                self.resolved_location = location
        return cleaned

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.resolved_location:
            profile.latitude = self.resolved_location["latitude"]
            profile.longitude = self.resolved_location["longitude"]
        elif any(field in self.changed_data for field in self.Meta.fields):
            # Manually entered area names cannot establish exact coordinates.
            profile.latitude = None
            profile.longitude = None
        if commit:
            profile.save(update_fields=[*self.Meta.fields, "latitude", "longitude"])
        return profile


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["username"].widget.attrs.update(
            {
                "class": "input swap-input w-full",
                "placeholder": "Enter your username",
                "autocomplete": "username",
            }
        )
        self.fields["password"].widget.attrs.update(
            {
                "class": "input swap-input w-full",
                "placeholder": "Enter your password",
                "autocomplete": "current-password",
            }
        )


class RegisterForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["username"].widget.attrs.update(
            {
                "class": "input swap-input w-full",
                "placeholder": "Choose a username",
                "autocomplete": "username",
            }
        )
        self.fields["password1"].widget.attrs.update(
            {
                "class": "input swap-input w-full",
                "placeholder": "Create a password",
                "autocomplete": "new-password",
            }
        )
        self.fields["password2"].widget.attrs.update(
            {
                "class": "input swap-input w-full",
                "placeholder": "Repeat your password",
                "autocomplete": "new-password",
            }
        )


class ProfileUpdateForm(forms.ModelForm):
    new_profile_picture = forms.ImageField(
        required=False,
        label="Profile photo",
        help_text=(
            "JPG, PNG, or WebP, up to 5 MB. Leave blank to keep your current photo."
        ),
        validators=[validate_uploaded_image],
        widget=forms.FileInput(
            attrs={
                "class": "file-input w-full",
                "accept": "image/jpeg,image/png,image/webp",
            }
        ),
    )

    class Meta:
        model = Profile
        fields = ("display_name", "bio", "new_profile_picture")

        widgets = {
            "display_name": forms.TextInput(
                attrs={
                    "class": "input swap-input w-full",
                    "placeholder": "Enter your display name",
                }
            ),
            "bio": forms.Textarea(
                attrs={
                    "class": "textarea swap-input w-full",
                    "placeholder": "Tell other swappers a little about yourself",
                    "rows": 4,
                }
            ),
        }

        labels = {
            "display_name": "Display name",
            "bio": "Bio",
        }
