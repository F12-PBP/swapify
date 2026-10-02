from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class SwapRequestQuerySet(models.QuerySet):
    def for_user(self, user):
        """Swap request di mana user adalah pengaju atau pemilik pakaian."""
        return self.filter(Q(requester=user) | Q(requested_clothing__owner=user))


class SwapRequest(models.Model):
    """Entitas `swap_request` di ERD.

    Didefinisikan di app chat karena app swap belum ada di repo. Field dan
    nilai status mengikuti ERD persis, jadi model ini bisa dipindahkan ke app
    swap tanpa mengubah kontrak dengan modul chat.
    """

    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        ACCEPTED = "Accepted", "Accepted"
        REJECTED = "Rejected", "Rejected"
        CANCELLED = "Cancelled", "Cancelled"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="swap_requests_sent",
    )
    requested_clothing = models.ForeignKey(
        "clothing_catalog.Clothing",
        on_delete=models.CASCADE,
        related_name="swap_requests_received",
    )
    offered_clothing = models.ForeignKey(
        "clothing_catalog.Clothing",
        on_delete=models.CASCADE,
        related_name="swap_requests_offered",
    )
    message = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SwapRequestQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(requested_clothing=F("offered_clothing")),
                name="swap_request_distinct_clothing",
            ),
        ]

    def __str__(self):
        return f"SwapRequest #{self.pk} ({self.status})"

    @property
    def owner(self):
        """Pemilik pakaian yang diminta (penerima request)."""
        return self.requested_clothing.owner

    def is_participant(self, user):
        return user.pk in (self.requester_id, self.requested_clothing.owner_id)

    def clean(self):
        if not (self.requested_clothing_id and self.offered_clothing_id):
            return
        if self.requested_clothing_id == self.offered_clothing_id:
            raise ValidationError("Pakaian yang diminta dan ditawarkan harus berbeda.")
        if self.requested_clothing.owner_id == self.requester_id:
            raise ValidationError("Tidak bisa meminta pakaian milik sendiri.")
        if self.offered_clothing.owner_id != self.requester_id:
            raise ValidationError("Pakaian yang ditawarkan harus milik pengaju.")


class ChatRoomQuerySet(models.QuerySet):
    def for_user(self, user):
        """Chat room milik user (sebagai pengaju atau pemilik pakaian)."""
        return self.filter(
            Q(swap_request__requester=user)
            | Q(swap_request__requested_clothing__owner=user)
        )

    def with_related(self):
        return self.select_related(
            "swap_request__requester",
            "swap_request__requested_clothing__owner",
            "swap_request__offered_clothing",
        )


class ChatRoom(models.Model):
    """Entitas `chat_room`: satu room per swap request (relasi `opens`)."""

    swap_request = models.OneToOneField(
        SwapRequest,
        on_delete=models.CASCADE,
        related_name="chat_room",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ChatRoomQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

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
