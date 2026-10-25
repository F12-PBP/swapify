from django import forms

from .models import Clothing


class ClothingForm(forms.ModelForm):
    class Meta:
        model = Clothing
        fields = (
            "name",
            "description",
            "image",
            "type",
            "size",
            "condition",
            "status",
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
            "image": forms.FileInput(attrs={"class": "file-input swap-input w-full"}),
            "type": forms.Select(attrs={"class": "select swap-input w-full"}),
            "size": forms.Select(attrs={"class": "select swap-input w-full"}),
            "condition": forms.Select(attrs={"class": "select swap-input w-full"}),
            "status": forms.Select(attrs={"class": "select swap-input w-full"}),
        }
