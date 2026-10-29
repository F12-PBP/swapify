from .models import ChatMessage, ChatRoom, SwapRequest


class ChatNotAllowed(Exception):
    """Dilempar kalau chat dibuka/dikirimi padahal tidak diizinkan."""


def open_chat_room(swap_request):
    """Ambil/buat chat room untuk swap request. Hanya untuk status Accepted."""
    if swap_request.status != SwapRequest.Status.ACCEPTED:
        raise ChatNotAllowed("Chat hanya tersedia setelah swap request diterima.")
    room, _created = ChatRoom.objects.get_or_create(swap_request=swap_request)
    return room


def send_message(room, sender, text):
    """Simpan pesan baru. Pengirim harus peserta dan room harus aktif."""
    if not room.is_participant(sender):
        raise ChatNotAllowed("Kamu bukan peserta chat ini.")
    if not room.is_active:
        raise ChatNotAllowed("Chat ini sudah tidak aktif.")
    return ChatMessage.objects.create(chat_room=room, sender=sender, message=text)


def mark_read(room, user, *, loaded_messages=None):
    """Tandai pesan lawan dibaca; dapat dibatasi pada batch yang dimuat."""

    queryset = room.messages.filter(is_read=False).exclude(sender=user)

    if loaded_messages is not None:
        loaded_messages = list(loaded_messages)
        queryset = queryset.filter(pk__in=[message.pk for message in loaded_messages])

    updated = queryset.update(is_read=True)

    if loaded_messages is not None:
        for message in loaded_messages:
            if message.sender_id != user.pk:
                message.is_read = True

    return updated
