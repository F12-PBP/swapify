from django import forms

from .models import ChatMessage


class ChatMessageForm(forms.ModelForm):
    class Meta:
        model = ChatMessage
        fields = ["message"]
        widgets = {
            "message": forms.Textarea(
                attrs={"rows": 2, "placeholder": "Tulis pesan...", "maxlength": 2000}
            )
        }
