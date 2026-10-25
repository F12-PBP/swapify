from django.contrib import admin

from .models import ChatMessage, ChatRoom


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ("id", "swap_request", "created_at")
    raw_id_fields = ("swap_request",)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "chat_room", "sender", "sent_at", "is_read")
    list_filter = ("is_read",)
    raw_id_fields = ("chat_room", "sender")
