from django import forms

from common.images import validate_uploaded_image

from .models import Clothing


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
