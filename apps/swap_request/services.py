from django.db import transaction
from django.utils import timezone

from apps.chat.services import open_chat_room
from apps.clothing_catalog.models import Clothing
from apps.transaction.models import Transaction

from .models import SwapRequest


class SwapAcceptanceError(Exception):
    pass


@transaction.atomic
def accept_swap_request(request_id, acting_user):
    swap_request = SwapRequest.objects.select_for_update().get(pk=request_id)

    if not acting_user.is_authenticated or swap_request.owner.pk != acting_user.pk:
        raise SwapAcceptanceError("Only the clothing owner can accept this request.")

    if swap_request.status == SwapRequest.Status.PENDING:
        items = list(
            Clothing.objects.select_for_update()
            .filter(
                pk__in=[
                    swap_request.requested_clothing_id,
                    swap_request.offered_clothing_id,
                ]
            )
            .order_by("pk")
        )

        if len(items) != 2 or any(
            item.status != Clothing.Status.AVAILABLE for item in items
        ):
            raise SwapAcceptanceError("Both clothing items must still be available.")

        swap_request.clean()

        reserved = Clothing.objects.filter(
            pk__in=[item.pk for item in items],
            status=Clothing.Status.AVAILABLE,
        ).update(
            status=Clothing.Status.RESERVED,
            updated_at=timezone.now(),
        )

        if reserved != 2:
            raise SwapAcceptanceError("The clothing items are no longer available.")

        SwapRequest.objects.filter(pk=swap_request.pk).update(
            status=SwapRequest.Status.ACCEPTED,
            updated_at=timezone.now(),
        )

        swap_request.status = SwapRequest.Status.ACCEPTED

    elif swap_request.status != SwapRequest.Status.ACCEPTED:
        raise SwapAcceptanceError("This request can no longer be accepted.")

    open_chat_room(swap_request)

    Transaction.objects.get_or_create(
        swap_request=swap_request,
        defaults={"status": Transaction.Status.WAITING},
    )

    return swap_request
