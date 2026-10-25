from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from common.images import validate_uploaded_image

from .models import Profile


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
