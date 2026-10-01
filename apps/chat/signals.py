from django.db.models.signals import post_save
from django.dispatch import receiver

from . import services
from .models import SwapRequest


@receiver(post_save, sender=SwapRequest, dispatch_uid="chat_open_room_on_accept")
def open_chat_room_when_accepted(sender, instance, raw=False, **kwargs):
    """Relasi `opens` di ERD: swap request Accepted otomatis punya chat room."""
    if raw:
        return
    if instance.status == SwapRequest.Status.ACCEPTED:
        services.open_chat_room(instance)
