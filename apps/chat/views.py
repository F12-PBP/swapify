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
from .models import ChatMessage, ChatRoom, SwapRequest


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
    """Isi chat + form kirim pesan (form hanya muncul kalau chat aktif)."""

    template_name = "chat_room_detail.html"
    context_object_name = "chat_room"

    def get_queryset(self):
        return ChatRoom.objects.for_user(self.request.user).with_related()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = self.object
        user = self.request.user

        context["chat_messages"] = list(room.messages.select_related("sender"))
        services.mark_read(room, user)

        context["partner"] = room.other_user(user)
        context["is_active"] = room.is_active
        context["form"] = ChatMessageForm()
        return context


class MessageCreateView(LoginRequiredMixin, View):
    """Terima pesan baru (POST). Ditolak kalau chat tidak aktif."""

    http_method_names = ["post"]

    def post(self, request, pk):
        room = get_object_or_404(
            ChatRoom.objects.for_user(request.user).with_related(), pk=pk
        )

        form = ChatMessageForm(request.POST)
        if not form.is_valid():
            messages.error(
                request, "Pesan tidak boleh kosong atau lebih dari 2000 karakter."
            )
            return redirect("chat:detail", pk=room.pk)

        try:
            services.send_message(room, request.user, form.cleaned_data["message"])
        except services.ChatNotAllowed as error:
            messages.error(request, str(error))

        return redirect("chat:detail", pk=room.pk)


class MessageListJsonView(LoginRequiredMixin, View):
    """Endpoint JSON untuk polling pesan baru: ?after=<id_pesan_terakhir>."""

    http_method_names = ["get"]

    def get(self, request, pk):
        room = get_object_or_404(
            ChatRoom.objects.for_user(request.user).with_related(), pk=pk
        )
        try:
            after = int(request.GET.get("after", 0))
        except (TypeError, ValueError):
            after = 0

        new_messages = list(room.messages.filter(id__gt=after).select_related("sender"))

        unread_ids = [
            m.id
            for m in new_messages
            if m.sender_id != request.user.id and not m.is_read
        ]
        if unread_ids:
            ChatMessage.objects.filter(id__in=unread_ids).update(is_read=True)

        return JsonResponse(
            {
                "is_active": room.is_active,
                "messages": [
                    {
                        "id": m.id,
                        "sender": m.sender.get_username(),
                        "is_mine": m.sender_id == request.user.id,
                        "message": m.message,
                        "sent_at": m.sent_at.isoformat(),
                    }
                    for m in new_messages
                ],
            }
        )
