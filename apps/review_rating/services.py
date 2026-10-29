from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.transaction.models import Transaction

from .models import Review


@transaction.atomic
def submit_review(*, transaction_id, author, rating, comment=""):
    if not author.is_authenticated:
        raise PermissionDenied("Please log in to write a review.")

    exchange = Transaction.objects.select_for_update().get(
        pk=transaction_id,
    )

    if not exchange.is_participant(author):
        raise PermissionDenied("Only exchange participants can write a review.")

    if exchange.status != Transaction.Status.COMPLETED:
        raise ValidationError("You can only review a completed transaction.")

    if Review.objects.filter(
        transaction=exchange,
        author=author,
    ).exists():
        raise ValidationError("You have already reviewed this transaction.")

    recipient = (
        exchange.owner if author.pk == exchange.requester.pk else exchange.requester
    )

    review = Review(
        transaction=exchange,
        author=author,
        recipient=recipient,
        rating=rating,
        comment=comment.strip(),
    )
    review.full_clean()
    review.save()

    return review
