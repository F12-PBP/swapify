from django import forms

from .models import Transaction


class UpdateTransactionForm(forms.ModelForm):
    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)

        self.user = user
        self.is_requester = user.pk == self.instance.swap_request.requester_id

        if self.is_requester:
            other_party_fields = (
                "owner_courier",
                "owner_resi",
                "owner_delivery_estimate",
            )
        else:
            other_party_fields = (
                "requester_courier",
                "requester_resi",
                "requester_delivery_estimate",
            )

        for field in other_party_fields:
            self.fields.pop(field, None)

        # Drafts can be saved before the other participant supplies their details.
        for field in self.fields.values():
            field.required = False
        self.fields["method"].required = True

    def clean(self):
        cleaned_data = super().clean()
        method = cleaned_data.get("method")

        if method == "Delivery":
            if self.is_requester:
                resi = cleaned_data.get("requester_resi")
                courier = cleaned_data.get("requester_courier")
                field_name = "requester_resi"
            else:
                resi = cleaned_data.get("owner_resi")
                courier = cleaned_data.get("owner_courier")
                field_name = "owner_resi"

            if not resi or not courier:
                self.add_error(
                    field_name, "Tracking number and courier are required for delivery."
                )

        return cleaned_data

    class Meta:
        model = Transaction

        fields = [
            "method",
            "requester_courier",
            "requester_resi",
            "requester_delivery_estimate",
            "owner_courier",
            "owner_resi",
            "owner_delivery_estimate",
            "meetup_date",
            "meetup_location",
        ]

        widgets = {
            "method": forms.Select(attrs={"class": "select swap-input w-full"}),
            "requester_courier": forms.TextInput(
                attrs={
                    "class": ("select w-full border border-neutral-30 rounded-xl p-2"),
                    "placeholder": "e.g., Lefi",
                }
            ),
            "requester_resi": forms.TextInput(
                attrs={
                    "class": ("input w-full"),
                    "placeholder": "e.g., JNE1234567890",
                }
            ),
            "requester_delivery_estimate": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={
                    "class": ("input w-full"),
                    "type": "datetime-local",
                },
            ),
            "owner_courier": forms.TextInput(
                attrs={
                    "class": ("input w-full"),
                    "placeholder": "e.g., Lefi",
                }
            ),
            "owner_resi": forms.TextInput(
                attrs={
                    "class": ("input w-full"),
                    "placeholder": "e.g., JNT987654321",
                }
            ),
            "owner_delivery_estimate": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={
                    "class": ("input w-full"),
                    "type": "datetime-local",
                },
            ),
            "meetup_date": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={
                    "class": ("input w-full"),
                    "type": "datetime-local",
                },
            ),
            "meetup_location": forms.TextInput(
                attrs={
                    "class": ("input w-full"),
                    "placeholder": "e.g., Central Park Mall Lobby",
                }
            ),
        }

        labels = {
            "method": "Exchange method",
            "requester_courier": "Your Courier Name",
            "requester_resi": "Your Tracking Number",
            "requester_delivery_estimate": "Your Package's Estimated Arrival Time",
            "owner_courier": "Your Courier Name",
            "owner_resi": "Your Tracking Number",
            "owner_delivery_estimate": "Your Package's Estimated Arrival Time",
            "meetup_date": "Meetup Date & Time",
            "meetup_location": "Meetup Location",
        }
