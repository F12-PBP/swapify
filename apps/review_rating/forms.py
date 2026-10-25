from django import forms


class ReviewForm(forms.Form):
    rating = forms.TypedChoiceField(
        coerce=int, choices=[(value, f"{value}/5") for value in range(1, 6)]
    )
    comment = forms.CharField(
        required=False,
        max_length=1000,
        help_text="Leave your experince with this swapper (Optional).",
        widget=forms.Textarea(
            attrs={
                "class": "textarea swap-input w-full",
                "rows": 4,
                "placeholder": "Insert your comment here...",
            }
        ),
    )
