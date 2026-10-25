from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("", views.ChatRoomListView.as_view(), name="list"),
    path(
        "start/<int:swap_request_id>/",
        views.StartChatView.as_view(),
        name="start",
    ),
    path("<int:pk>/", views.ChatRoomDetailView.as_view(), name="detail"),
    path("<int:pk>/send/", views.MessageCreateView.as_view(), name="send"),
    path(
        "<int:pk>/messages/",
        views.MessageListJsonView.as_view(),
        name="messages_json",
    ),
]
