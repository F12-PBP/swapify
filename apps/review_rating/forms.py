from django import forms


class ReviewForm(forms.Form):
    rating = forms.TypedChoiceField(
        coerce=int,
        choices=[(value, f"{value} out of 5 stars") for value in range(1, 6)],
        widget=forms.RadioSelect(
            attrs={"class": "peer sr-only", "aria-describedby": "review-rating-error"}
        ),
    )
    comment = forms.CharField(
        required=False,
        max_length=1000,
        widget=forms.Textarea(
            attrs={
                "class": (
                    "min-h-[152px] w-full resize-y rounded-3xl border-0 "
                    "bg-neutral-30 px-6 py-4 text-b7 text-neutral-100 "
                    "placeholder:text-neutral-70 focus-visible:outline-2 "
                    "focus-visible:outline-offset-2 focus-visible:outline-primary-base"
                ),
                "rows": 4,
                "placeholder": "What made the exchange special?",
            }
        ),
    )
