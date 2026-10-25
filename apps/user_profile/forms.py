from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from common.images import validate_uploaded_image

from .models import Profile


class ProfileLocationForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("district", "city", "province")
        labels = {
            "district": "District",
            "city": "City or regency",
            "province": "Province",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input swap-input w-full"
        self.fields["district"].help_text = "Optional."
        self.fields["city"].required = True
        self.fields["province"].required = True

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.changed_data:
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
