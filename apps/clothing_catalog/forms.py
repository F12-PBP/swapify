from django import forms

from .models import Clothing


class ClothingForm(forms.ModelForm):
    class Meta:
        model = Clothing
        fields = (
            "name",
            "description",
            "category",
            "size",
            "condition",
            "availability",
        )
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "input swap-input w-full",
                    "placeholder": "Contoh: Kemeja Linen",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "textarea swap-input w-full",
                    "placeholder": "Jelaskan kondisi dan detail pakaian.",
                    "rows": 5,
                }
            ),
            "category": forms.Select(attrs={"class": "select swap-input w-full"}),
            "size": forms.Select(attrs={"class": "select swap-input w-full"}),
            "condition": forms.Select(attrs={"class": "select swap-input w-full"}),
            "availability": forms.Select(attrs={"class": "select swap-input w-full"}),
        }
