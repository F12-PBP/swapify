from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Max, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, ListView

from . import services
from .forms import ChatMessageForm
from .http import JsonChatMixin, error_response, json_response, wants_json
from .models import ChatMessage, ChatRoom, SwapRequest
from .queries import (
    InvalidMessageQuery,
    message_page,
    page_parameters,
    read_receipts,
    receipt_ids,
)
from .serializers import serialize_message


class ChatRoomListView(LoginRequiredMixin, ListView):
    """Daftar semua chat room milik user yang login."""

    template_name = "chat_room_list.html"
    context_object_name = "chat_rooms"

    def get_queryset(self):
        user = self.request.user
        last_message = ChatMessage.objects.filter(chat_room=OuterRef("pk")).order_by(
            "-sent_at", "-id"
        )
        return (
            ChatRoom.objects.for_user(user)
            .with_related()
            .annotate(
                last_activity=Coalesce(Max("messages__sent_at"), "created_at"),
                unread_count=Count(
                    "messages",
                    filter=Q(messages__is_read=False) & ~Q(messages__sender=user),
                ),
                last_message=Subquery(last_message.values("message")[:1]),
                last_sender_id=Subquery(last_message.values("sender_id")[:1]),
            )
            .order_by("-last_activity", "-id")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rooms = list(context["chat_rooms"])
        for room in rooms:
            room.partner = room.other_user(self.request.user)
        context["chat_rooms"] = rooms
        return context


class StartChatView(LoginRequiredMixin, View):
    """Buka chat dari sebuah swap request. Ditolak kalau belum Accepted."""

    http_method_names = ["post"]

    def post(self, request, swap_request_id):
        swap_request = get_object_or_404(
            SwapRequest.objects.for_user(request.user).select_related(
                "requester", "requested_clothing__owner"
            ),
            pk=swap_request_id,
        )

        try:
            room = services.open_chat_room(swap_request)
        except services.ChatNotAllowed as error:
            messages.error(request, str(error))
            return redirect("chat:list")

        return redirect("chat:detail", pk=room.pk)


class ChatRoomDetailView(LoginRequiredMixin, DetailView):
    """Detail chat dengan batch pesan terbaru."""

    template_name = "chat_room_detail.html"
    context_object_name = "chat_room"

    def get_queryset(self):
        return ChatRoom.objects.for_user(self.request.user).with_related()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = self.object
        user = self.request.user

        batch, has_older = message_page(
            room,
            direction="latest",
        )

        services.mark_read(
            room,
            user,
            loaded_messages=batch,
        )

        context.update(
            chat_messages=batch,
            partner=room.other_user(user),
            is_active=room.is_active,
            form=ChatMessageForm(),
            has_older_messages=has_older,
            oldest_message_id=batch[0].pk if batch else 0,
            latest_message_id=batch[-1].pk if batch else 0,
        )
        return context


class MessageCreateView(JsonChatMixin, LoginRequiredMixin, View):
    """Kirim pesan melalui AJAX atau form biasa."""

    http_method_names = ["post"]

    def post(self, request, pk):
        ajax = wants_json(request)

        room = get_object_or_404(
            ChatRoom.objects.for_user(request.user).with_related(), pk=pk
        )

        form = ChatMessageForm(request.POST)

        if not form.is_valid():
            error_message = "Pesan tidak boleh kosong atau lebih dari 2000 karakter."

            if ajax:
                return error_response(
                    "invalid_message",
                    error_message,
                    status=400,
                    errors=form.errors.get_json_data(),
                )

            messages.error(request, error_message)
            return redirect("chat:detail", pk=room.pk)

        try:
            message = services.send_message(
                room, request.user, form.cleaned_data["message"]
            )

        except services.ChatNotAllowed as error:
            if ajax:
                return error_response(
                    "chat_inactive",
                    str(error),
                    status=409,
                )
            messages.error(request, str(error))
            return redirect("chat:detail", pk=room.pk)

        if ajax:
            return json_response(
                {
                    "ok": True,
                    "message": serialize_message(message, request.user),
                },
                status=201,
            )

        return redirect("chat:detail", pk=room.pk)


class MessageListJsonView(JsonChatMixin, LoginRequiredMixin, View):
    """Endpoint JSON untuk polling pesan baru: ?after=<id_pesan_terakhir>."""

    http_method_names = ["get"]

    def get(self, request, pk):
        room = get_object_or_404(
            ChatRoom.objects.for_user(request.user).with_related(), pk=pk
        )

        try:
            direction, cursor, limit = page_parameters(request)
            ids = receipt_ids(request)
        except InvalidMessageQuery as error:
            return error_response(
                "invalid_query",
                str(error),
                status=400,
            )

        batch, has_more = message_page(
            room,
            direction=direction,
            cursor=cursor,
            limit=limit,
        )

        services.mark_read(
            room,
            request.user,
            loaded_messages=batch,
        )

        next_after = (
            (batch[-1].pk if batch else cursor) if direction == "newer" else None
        )

        return JsonResponse(
            {
                "ok": True,
                "is_active": room.is_active,
                "messages": [
                    serialize_message(message, request.user) for message in batch
                ],
                "direction": direction,
                "has_more": has_more,
                "next_after": next_after,
                "next_before": batch[0].pk if batch else None,
                "read_receipts": read_receipts(
                    room,
                    request.user,
                    ids,
                ),
            }
        )
