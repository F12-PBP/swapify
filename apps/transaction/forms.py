from django import forms

from .models import Transaction


class CreateTransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction

        fields = [
            "method",
            "requester_resi",
            "requester_delivery_estimate",
            "meetup_date",
            "meetup_location",
        ]

        widgets = {
            "method": forms.Select(
                attrs={
                    "class": ("select w-full border border-neutral-30 rounded-xl p-2"),
                    "id": "methodSelect",
                }
            ),
            "requester_resi": forms.TextInput(
                attrs={
                    "class": ("input w-full"),
                    "placeholder": "e.g., JNE1234567890",
                }
            ),
            "requester_delivery_estimate": forms.DateTimeInput(
                attrs={
                    "class": ("input w-full"),
                    "type": "datetime-local",
                }
            ),
            "meetup_date": forms.DateTimeInput(
                attrs={
                    "class": ("input w-full"),
                    "type": "datetime-local",
                }
            ),
            "meetup_location": forms.TextInput(
                attrs={
                    "class": ("input w-full"),
                    "placeholder": "e.g., Taman Nasional Komodo",
                }
            ),
        }

        labels = {
            "method": "Transaction Method",
            "requester_resi": "Your Tracking Number (Resi)",
            "requester_delivery_estimate": "Estimated Delivery Date",
            "meetup_date": "Agreed Meetup Date & Time",
            "meetup_location": "Agreed Meetup Location",
        }

    def clean(self):
        cleaned_data = super().clean()

        method = cleaned_data.get("method")

        if method == "Delivery":
            if not cleaned_data.get("requester_resi"):
                self.add_error(
                    "requester_resi", "Tracking number is required for delivery."
                )

            if not cleaned_data.get("requester_delivery_estimate"):
                self.add_error(
                    "requester_delivery_estimate",
                    "Estimated delivery date is required for delivery.",
                )

        elif method == "Meetup":
            if not cleaned_data.get("meetup_date"):
                self.add_error("meetup_date", "Meetup date is required.")

            if not cleaned_data.get("meetup_location"):
                self.add_error("meetup_location", "Meetup location is required.")

        return cleaned_data


class UpdateTransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction

        fields = [
            "requester_resi",
            "requester_delivery_estimate",
            "owner_resi",
            "owner_delivery_estimate",
            "meetup_date",
            "meetup_location",
        ]

        widgets = {
            "requester_resi": forms.TextInput(
                attrs={
                    "class": ("select w-full border border-neutral-30 rounded-xl p-2"),
                    "placeholder": "e.g., JNE1234567890",
                }
            ),
            "requester_delivery_estimate": forms.DateTimeInput(
                attrs={
                    "class": ("input w-full"),
                    "type": "datetime-local",
                }
            ),
            "owner_resi": forms.TextInput(
                attrs={
                    "class": ("input w-full"),
                    "placeholder": "e.g., JNT987654321",
                }
            ),
            "owner_delivery_estimate": forms.DateTimeInput(
                attrs={
                    "class": ("input w-full"),
                    "type": "datetime-local",
                }
            ),
            "meetup_date": forms.DateTimeInput(
                attrs={
                    "class": ("input w-full"),
                    "type": "datetime-local",
                }
            ),
            "meetup_location": forms.TextInput(
                attrs={
                    "class": ("input w-full"),
                    "placeholder": "e.g., Central Park Mall Lobby",
                }
            ),
        }

        labels = {
            "requester_resi": "Requester Tracking Number",
            "requester_delivery_estimate": "Requester Estimated Delivery",
            "owner_resi": "Owner Tracking Number",
            "owner_delivery_estimate": "Owner Estimated Delivery",
            "meetup_date": "Meetup Date & Time",
            "meetup_location": "Meetup Location",
        }
