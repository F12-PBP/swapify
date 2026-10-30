from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.swap_request.models import SwapRequest


class ChatRoomQuerySet(models.QuerySet):
    def for_user(self, user):
        """Chat room milik user (sebagai pengaju atau pemilik pakaian)."""
        return self.filter(
            Q(swap_request__requester=user)
            | Q(swap_request__requested_clothing__owner=user)
        )

    def with_related(self):
        return self.select_related(
            "swap_request__requester__profile",
            "swap_request__requested_clothing__owner__profile",
            "swap_request__offered_clothing",
        )


class ChatRoom(models.Model):
    """Entitas `chat_room`: satu room per swap request (relasi `opens`)."""

    swap_request = models.OneToOneField(
        "swap_request.SwapRequest",
        on_delete=models.CASCADE,
        related_name="chat_room",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ChatRoomQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "swap request"
        verbose_name_plural = "swap request"

    def __str__(self):
        return f"ChatRoom #{self.pk} (swap request #{self.swap_request_id})"

    @property
    def is_active(self):
        """Dihitung tiap kali (tidak disimpan): chat terkunci otomatis kalau
        status swap request tidak lagi Accepted."""
        return self.swap_request.status == SwapRequest.Status.ACCEPTED

    def is_participant(self, user):
        return self.swap_request.is_participant(user)

    def other_user(self, user):
        swap_request = self.swap_request
        if user.pk == swap_request.requester_id:
            return swap_request.owner
        return swap_request.requester


class ChatMessage(models.Model):
    """Entitas `chat_message`."""

    chat_room = models.ForeignKey(
        ChatRoom, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_messages_sent",
    )
    message = models.TextField(max_length=2000)
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["sent_at", "id"]
        indexes = [
            models.Index(fields=["chat_room", "sent_at"], name="chatmsg_room_sent_idx"),
        ]

    def __str__(self):
        return f"{self.sender}: {self.message[:30]}"
