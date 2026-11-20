from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import ChatRoom
from .queries import (
    InvalidMessageQuery,
    conversation_rooms,
    message_page,
    page_parameters,
)
from .serializers import (
    ChatMessageCreateSerializer,
    ChatMessageSerializer,
    ChatRoomSerializer,
)


class ChatRoomListAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rooms = conversation_rooms(request.user)
        serializer = ChatRoomSerializer(
            rooms,
            many=True,
            context={"request": request},
        )
        return Response(serializer.data)


class ChatRoomMessagesAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_room(self, request, room_id):
        return get_object_or_404(
            ChatRoom.objects.for_user(request.user).with_related(),
            pk=room_id,
        )

    def get(self, request, room_id):
        room = self.get_room(request, room_id)

        try:
            direction, cursor, limit = page_parameters(request)
            if (
                "after" not in request.query_params
                and "before" not in request.query_params
            ):
                direction = "latest"
        except InvalidMessageQuery as error:
            raise ValidationError({"detail": str(error)}) from error

        batch, has_more = message_page(
            room,
            direction=direction,
            cursor=cursor,
            limit=limit,
        )
        serializer = ChatMessageSerializer(
            batch,
            many=True,
            context={"request": request},
        )

        next_after = None
        if direction == "newer":
            next_after = batch[-1].pk if batch else cursor

        return Response(
            {
                "room_id": room.pk,
                "is_active": room.is_active,
                "messages": serializer.data,
                "direction": direction,
                "has_more": has_more,
                "next_after": next_after,
                "next_before": batch[0].pk if batch else None,
            }
        )

    def post(self, request, room_id):
        room = self.get_room(request, room_id)
        input_serializer = ChatMessageCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        try:
            message = services.send_message(
                room,
                request.user,
                input_serializer.validated_data["message"],
            )
        except services.ChatNotAllowed as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_409_CONFLICT,
            )

        output_serializer = ChatMessageSerializer(
            message,
            context={"request": request},
        )
        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class ChatRoomMarkReadAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        room = get_object_or_404(
            ChatRoom.objects.for_user(request.user),
            pk=room_id,
        )
        marked_read = services.mark_read(room, request.user)

        return Response(
            {
                "room_id": room.pk,
                "marked_read": marked_read,
            },
            status=status.HTTP_200_OK,
        )
