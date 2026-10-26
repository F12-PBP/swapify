from django.db import transaction
from django.utils import timezone

from apps.chat.services import open_chat_room
from apps.clothing_catalog.models import Clothing
from apps.transaction.models import Transaction

from .models import SwapRequest


class SwapAcceptanceError(Exception):
    pass


class SwapCreationError(Exception):
    pass


@transaction.atomic
def create_swap_request(
    *, requester, requested_clothing_id, offered_clothing_id, message=""
):
    # Lock in the same order as acceptance, then recheck after form validation.
    items = {
        item.pk: item
        for item in Clothing.objects.select_for_update()
        .filter(pk__in=[requested_clothing_id, offered_clothing_id])
        .order_by("pk")
    }
    requested = items.get(requested_clothing_id)
    offered = items.get(offered_clothing_id)
    if not requested or not offered or requested.pk == offered.pk:
        raise SwapCreationError("Please choose two different, available pieces.")
    if requested.owner_id == requester.pk or offered.owner_id != requester.pk:
        raise SwapCreationError(
            "Choose one of your own pieces to offer another swapper."
        )
    if any(item.status != Clothing.Status.AVAILABLE for item in items.values()):
        raise SwapCreationError(
            "One of these pieces is no longer available. Please choose another."
        )
    if SwapRequest.objects.filter(
        requester=requester,
        requested_clothing=requested,
        status=SwapRequest.Status.PENDING,
    ).exists():
        raise SwapCreationError(
            "You already have a pending request for this piece. "
            "Check My swaps for updates."
        )
    return SwapRequest.objects.create(
        requester=requester,
        requested_clothing=requested,
        offered_clothing=offered,
        message=message,
    )


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
