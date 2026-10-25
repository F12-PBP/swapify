# Create your models here.
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q


class Review(models.Model):
    transaction = models.ForeignKey(
        "transaction.Transaction", on_delete=models.PROTECT, related_name="reviews"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="written_reviews",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_reviews",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["transaction", "author"],
                name="review_unique_author_transaction",
            ),
            models.CheckConstraint(
                condition=Q(rating__gte=1, rating__lte=5),
                name="review_rating_between_1_and_5",
            ),
            models.CheckConstraint(
                condition=~Q(author=F("recipient")), name="review_author_not_recipient"
            ),
        ]

    def __str__(self):
        return f"{self.author} -> {self.recipient}: {self.rating}/5"
