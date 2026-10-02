from django.contrib import admin

from .models import ChatMessage, ChatRoom, SwapRequest


@admin.register(SwapRequest)
class SwapRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "requester",
        "requested_clothing",
        "offered_clothing",
        "status",
        "created_at",
    )
    list_filter = ("status",)
    raw_id_fields = ("requester", "requested_clothing", "offered_clothing")


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ("id", "swap_request", "created_at")
    raw_id_fields = ("swap_request",)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "chat_room", "sender", "sent_at", "is_read")
    list_filter = ("is_read",)
    raw_id_fields = ("chat_room", "sender")
