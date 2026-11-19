from django.db.models import Q
from rest_framework import generics, status, viewsets
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.chat import services as chat_services
from apps.chat.models import ChatRoom
from apps.clothing_catalog.models import Clothing
from apps.review_rating.models import Review
from apps.swap_request.models import SwapRequest
from apps.transaction.models import Transaction
from apps.user_profile.models import Profile

from .serializers import (
    ChatMessageSerializer,
    ChatRoomSerializer,
    ClothingSerializer,
    CreateChatMessageSerializer,
    ProfileSerializer,
    ReviewSerializer,
    SwapRequestSerializer,
    TransactionSerializer,
)


class MobileTokenView(ObtainAuthToken):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "username": user.username})


class MobileLogoutView(generics.GenericAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        profile, _ = Profile.objects.get_or_create(
            user=self.request.user,
            defaults={"display_name": self.request.user.get_username()},
        )
        return profile


class UserScopedReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]


class ClothingViewSet(UserScopedReadOnlyViewSet):
    serializer_class = ClothingSerializer

    def get_queryset(self):
        return (
            Clothing.objects.filter(
                Q(status=Clothing.Status.AVAILABLE) | Q(owner=self.request.user)
            )
            .select_related("owner", "owner__profile")
            .order_by("-created_at")
        )


class SwapRequestViewSet(UserScopedReadOnlyViewSet):
    serializer_class = SwapRequestSerializer

    def get_queryset(self):
        return SwapRequest.objects.for_user(self.request.user).select_related(
            "requester",
            "requested_clothing",
            "requested_clothing__owner",
            "offered_clothing",
        )


class TransactionViewSet(UserScopedReadOnlyViewSet):
    serializer_class = TransactionSerializer

    def get_queryset(self):
        return (
            Transaction.objects.select_related(
                "swap_request__requester",
                "swap_request__requested_clothing__owner",
            )
            .filter(
                Q(swap_request__requester=self.request.user)
                | Q(swap_request__requested_clothing__owner=self.request.user)
            )
            .order_by("-created_at")
        )


class ChatViewSet(UserScopedReadOnlyViewSet):
    serializer_class = ChatRoomSerializer

    def get_queryset(self):
        return ChatRoom.objects.for_user(self.request.user).with_related()

    @action(detail=True, methods=["get", "post"])
    def messages(self, request, pk=None):
        room = self.get_object()
        if request.method == "GET":
            messages = room.messages.select_related("sender").order_by("sent_at", "id")
            page = self.paginate_queryset(messages)
            serializer = ChatMessageSerializer(
                page if page is not None else messages,
                many=True,
                context=self.get_serializer_context(),
            )
            if page is not None:
                return self.get_paginated_response(serializer.data)
            return Response(serializer.data)

        serializer = CreateChatMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            message = chat_services.send_message(
                room, request.user, serializer.validated_data["message"]
            )
        except chat_services.ChatNotAllowed as error:
            raise PermissionDenied(str(error)) from error
        response = ChatMessageSerializer(message, context=self.get_serializer_context())
        return Response(response.data, status=status.HTTP_201_CREATED)


class ReviewViewSet(UserScopedReadOnlyViewSet):
    serializer_class = ReviewSerializer

    def get_queryset(self):
        return Review.objects.filter(
            Q(author=self.request.user) | Q(recipient=self.request.user)
        ).select_related("author", "recipient", "transaction")
