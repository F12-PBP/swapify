from django import forms

from apps.clothing_catalog.models import Clothing

from .models import SwapRequest


class SwapRequestForm(forms.ModelForm):
    class Meta:
        model = SwapRequest
        fields = ("offered_clothing", "message")
        widgets = {
            "offered_clothing": forms.Select(
                attrs={"class": "select swap-input w-full"}
            ),
            "message": forms.Textarea(
                attrs={
                    "class": "textarea swap-input w-full",
                    "placeholder": "Tulis pesan untuk pemilik pakaian (opsional).",
                    "rows": 4,
                }
            ),
        }

    def __init__(self, *args, requester, requested_clothing, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.requester = requester
        self.instance.requested_clothing = requested_clothing
        offered_field = self.fields["offered_clothing"]
        offered_field.queryset = Clothing.objects.filter(
            owner=requester,
            availability=Clothing.Availability.AVAILABLE,
        )
        offered_field.empty_label = "Pilih pakaianmu"

    def clean(self):
        cleaned_data = super().clean()
        has_pending_request = SwapRequest.objects.filter(
            requester=self.instance.requester,
            requested_clothing=self.instance.requested_clothing,
            status=SwapRequest.Status.PENDING,
        ).exists()
        if has_pending_request:
            raise forms.ValidationError(
                "Kamu masih punya swap request yang menunggu untuk pakaian ini."
            )
        return cleaned_data
