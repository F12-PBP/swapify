from django import forms

from apps.clothing_catalog.models import Clothing

from .models import SwapRequest


class SwapRequestForm(forms.ModelForm):
    message = forms.CharField(
        required=False,
        max_length=1000,
        widget=forms.Textarea(
            attrs={
                "class": "market-input min-h-36 resize-y rounded-[20px]",
                "rows": 5,
                "placeholder": "Say hello and tell them what you’d love to swap.",
            }
        ),
    )

    class Meta:
        model = SwapRequest
        fields = ("offered_clothing", "message")
        widgets = {
            "offered_clothing": forms.Select(attrs={"class": "market-input"}),
        }

    def __init__(self, *args, requester, requested_clothing, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.requester = requester
        self.instance.requested_clothing = requested_clothing
        offered_field = self.fields["offered_clothing"]
        offered_field.queryset = Clothing.objects.filter(
            owner=requester,
            status=Clothing.Status.AVAILABLE,
        )
        offered_field.empty_label = "Pick your piece"

    def clean(self):
        cleaned_data = super().clean()
        has_pending_request = SwapRequest.objects.filter(
            requester=self.instance.requester,
            requested_clothing=self.instance.requested_clothing,
            status=SwapRequest.Status.PENDING,
        ).exists()
        if has_pending_request:
            raise forms.ValidationError(
                "You already have a pending request for this piece. "
                "Check My swaps for updates."
            )
        return cleaned_data


class SwapRequestFilterForm(forms.Form):
    """GET filters for My swaps. Invalid values are dropped, not rejected."""

    search = forms.CharField(required=False, max_length=100)
    role = forms.ChoiceField(
        required=False,
        choices=(("", "All swaps"), ("received", "Received"), ("sent", "Sent")),
    )
    status = forms.ChoiceField(
        required=False,
        choices=(("", "Any status"), *SwapRequest.Status.choices),
    )

    @property
    def values(self):
        self.is_valid()
        return {name: self.cleaned_data.get(name) or "" for name in self.fields}
