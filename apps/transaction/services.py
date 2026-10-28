from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.clothing_catalog.models import Clothing
from apps.swap_request.models import SwapRequest

from .models import Transaction


def _get_participant_transaction(transaction_id, user):
    # Lock only the transaction row, not the joined users or request.
    exchange = Transaction.objects.select_for_update().get(pk=transaction_id)
    if not user.is_authenticated or not exchange.is_participant(user):
        raise PermissionDenied("Only exchange participants can perform this action.")
    if exchange.swap_request.status != SwapRequest.Status.ACCEPTED:
        raise ValidationError("The swap request must still be accepted.")
    return exchange


def _reserved_clothing(exchange):
    swap = exchange.swap_request
    items = list(
        Clothing.objects.select_for_update()
        .filter(pk__in=[swap.requested_clothing_id, swap.offered_clothing_id])
        .order_by("pk")
    )
    if len(items) != 2 or any(
        item.status != Clothing.Status.RESERVED for item in items
    ):
        raise ValidationError("Both clothing items must be reserved for this exchange.")
    return items


@transaction.atomic
def start_transaction(transaction_id, user):
    exchange = _get_participant_transaction(transaction_id, user)
    party = "requester" if user.pk == exchange.swap_request.requester_id else "owner"
    if exchange.status == Transaction.Status.IN_PROGRESS:
        return exchange
    if exchange.status != Transaction.Status.WAITING:
        raise ValidationError("Only a waiting transaction can be started.")

    start_field = f"{party}_started"
    updated_fields = []

    if not getattr(exchange, start_field):
        setattr(exchange, start_field, True)
        updated_fields.append(start_field)

    if exchange.requester_started and exchange.owner_started:
        exchange.status = Transaction.Status.IN_PROGRESS
        updated_fields.append("status")
        exchange.full_clean()
        _reserved_clothing(exchange)

    exchange.save(update_fields=updated_fields)
    return exchange


@transaction.atomic
def cancel_ready_transaction(transaction_id, user):
    exchange = _get_participant_transaction(transaction_id, user)
    party = "requester" if user.pk == exchange.swap_request.requester_id else "owner"
    if exchange.status == Transaction.Status.IN_PROGRESS:
        return exchange
    if exchange.status != Transaction.Status.WAITING:
        raise ValidationError("Exchange has been started.")

    start_field = f"{party}_started"
    updated_fields = []

    if getattr(exchange, start_field):
        setattr(exchange, start_field, False)
        updated_fields.append(start_field)

    exchange.save(update_fields=updated_fields)
    return exchange


@transaction.atomic
def confirm_receipt(transaction_id, user):
    exchange = _get_participant_transaction(transaction_id, user)
    party = "requester" if user.pk == exchange.swap_request.requester_id else "owner"
    received_field = f"{party}_received"
    received_at_field = f"{party}_received_at"

    if exchange.status == Transaction.Status.COMPLETED:
        if getattr(exchange, received_field):
            return exchange
        raise ValidationError("This exchange has already been completed.")
    if exchange.status != Transaction.Status.IN_PROGRESS:
        raise ValidationError("Start the exchange before confirming receipt.")

    now = timezone.now()
    updated_fields = []
    if not getattr(exchange, received_field):
        setattr(exchange, received_field, True)
        updated_fields.append(received_field)
    if getattr(exchange, received_at_field) is None:
        setattr(exchange, received_at_field, now)
        updated_fields.append(received_at_field)

    if exchange.requester_received and exchange.owner_received:
        items = _reserved_clothing(exchange)
        swapped = Clothing.objects.filter(
            pk__in=[item.pk for item in items], status=Clothing.Status.RESERVED
        ).update(status=Clothing.Status.SWAPPED, updated_at=now)
        if swapped != 2:
            raise ValidationError("The clothing items are no longer reserved.")
        exchange.status = Transaction.Status.COMPLETED
        exchange.completed_at = now
        updated_fields.extend(["status", "completed_at"])

    if updated_fields:
        exchange.save(update_fields=updated_fields)
    return exchange
