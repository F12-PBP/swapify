from django import forms

from common.images import validate_uploaded_image

from .categories import DISCOVERY_TYPES
from .models import Clothing


class DiscoveryFilterForm(forms.Form):
    distance = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Any distance"),
            ("5", "Within 5 km"),
            ("10", "Within 10 km"),
            ("25", "Within 25 km"),
            ("50", "Within 50 km"),
        ],
    )

    def __init__(self, *args, has_location=False, **kwargs):
        super().__init__(*args, **kwargs)
        if has_location:
            self.fields["sort"].choices = [
                *self.fields["sort"].choices,
                ("nearest", "Nearest first"),
            ]
        else:
            self.fields["distance"].disabled = True

    search = forms.CharField(required=False, max_length=150)
    type = forms.ChoiceField(
        required=False, choices=[("", "All finds"), *DISCOVERY_TYPES]
    )
    size = forms.ChoiceField(
        required=False, choices=[("", "All sizes"), *Clothing.Size.choices]
    )
    condition = forms.ChoiceField(
        required=False, choices=[("", "Any condition"), *Clothing.Condition.choices]
    )
    sort = forms.ChoiceField(
        required=False,
        choices=[("recommended", "Recommended"), ("newest", "Newest first")],
    )


class ClothingForm(forms.ModelForm):
    new_image = forms.ImageField(
        required=False,
        label="Clothing photo",
        help_text=(
            "JPG, PNG, or WebP, up to 5 MB. Leave blank to keep the current photo."
        ),
        validators=[validate_uploaded_image],
        widget=forms.FileInput(
            attrs={
                "class": "file-input swap-input w-full",
                "accept": "image/jpeg,image/png,image/webp",
            }
        ),
    )

    class Meta:
        model = Clothing
        fields = (
            "name",
            "description",
            "new_image",
            "type",
            "size",
            "condition",
        )
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "input swap-input w-full",
                    "placeholder": "Example: Linen Shirt",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "textarea swap-input w-full",
                    "placeholder": "Describe condition and details of clothing.",
                    "rows": 5,
                }
            ),
            "type": forms.Select(attrs={"class": "select swap-input w-full"}),
            "size": forms.Select(attrs={"class": "select swap-input w-full"}),
            "condition": forms.Select(attrs={"class": "select swap-input w-full"}),
        }
