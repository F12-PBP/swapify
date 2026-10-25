from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

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
    class Meta:
        model = Profile
        fields = ("display_name", "bio")

        widgets = {
            "display_name": forms.TextInput(
                attrs={
                    "class": "input swap-input w-full",
                    "placeholder": "Enter you display name here...",
                }
            ),
            "bio": forms.Textarea(
                attrs={
                    "class": "textarea swap-input w-full",
                    "placeholder": "Enter your bio here...",
                    "rows": 4,
                }
            ),
        }

        labels = {
            "display_name": "Display Name",
            "bio": "Bio",
        }
