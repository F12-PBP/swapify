from django import forms

from common.images import validate_uploaded_image

from .categories import DISCOVERY_TYPES
from .models import Clothing, default_exchange_methods


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
    exchange_methods = forms.MultipleChoiceField(
        choices=[("meetup", "Meet nearby"), ("delivery", "Send a package")],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Choose how you can swap",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, placeholder in (
            ("type", "Select category"),
            ("size", "Select size"),
            ("condition", "How has it been loved?"),
        ):
            self.fields[name].choices = [
                (value, placeholder if value == "" else label)
                for value, label in self.fields[name].choices
            ]
        current_form = not self.is_bound or self.data.get("wardrobe_form") == "1"
        self.fields["new_image"].required = current_form and not self.instance.image_url

    def clean_exchange_methods(self):
        methods = self.cleaned_data["exchange_methods"]
        if not methods:
            if self.data.get("wardrobe_form") == "1":
                raise forms.ValidationError("Choose at least one exchange method.")
            return self.instance.exchange_methods or default_exchange_methods()
        return methods

    new_image = forms.ImageField(
        required=False,
        label="Clothing photo",
        help_text=(
            "JPG, PNG, or WebP, up to 5 MB. Leave blank to keep the current photo."
        ),
        validators=[validate_uploaded_image],
        widget=forms.FileInput(
            attrs={
                "class": "peer sr-only",
                "data-clothing-photo": "",
                "aria-describedby": "photo-help",
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
            "exchange_methods",
        )
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "input swap-input w-full",
                    "placeholder": "e.g. The everyday denim jacket",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": (
                        "textarea swap-input min-h-[170px] w-full rounded-2xl "
                        "border-0 bg-neutral-30 px-5 py-3 text-b7 shadow-sm "
                        "placeholder:text-neutral-60 focus:outline-primary-base"
                    ),
                    "placeholder": "Describe the fit, fabric, and any signs of wear…",
                    "rows": 6,
                }
            ),
            "type": forms.Select(attrs={"class": "select swap-input w-full"}),
            "size": forms.Select(attrs={"class": "select swap-input w-full"}),
            "condition": forms.Select(attrs={"class": "select swap-input w-full"}),
        }
