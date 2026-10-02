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


def mark_read(room, user):
    """Tandai semua pesan dari lawan bicara sebagai sudah dibaca."""
    return (
        ChatMessage.objects.filter(chat_room=room, is_read=False)
        .exclude(sender=user)
        .update(is_read=True)
    )
