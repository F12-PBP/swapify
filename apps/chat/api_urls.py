from django.urls import path

from .api_views import (
    ChatRoomListAPIView,
    ChatRoomMarkReadAPIView,
    ChatRoomMessagesAPIView,
)

app_name = "chat_api"

urlpatterns = [
    path(
        "rooms/",
        ChatRoomListAPIView.as_view(),
        name="room-list",
    ),
    path(
        "rooms/<int:room_id>/messages/",
        ChatRoomMessagesAPIView.as_view(),
        name="room-messages",
    ),
    path(
        "rooms/<int:room_id>/read/",
        ChatRoomMarkReadAPIView.as_view(),
        name="room-mark-read",
    ),
]
