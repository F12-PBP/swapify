from rest_framework import serializers

from apps.chat.models import ChatMessage, ChatRoom
from apps.clothing_catalog.categories import STYLE_CHOICES
from apps.clothing_catalog.models import Clothing
from apps.review_rating.models import Review
from apps.swap_request.models import SwapRequest
from apps.transaction.models import Transaction
from apps.user_profile.models import Profile


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    profile_picture_url = serializers.SerializerMethodField()
    preferences = serializers.ListField(
        child=serializers.ChoiceField(choices=[key for key, _ in STYLE_CHOICES]),
        required=False,
    )
    latitude = serializers.FloatField(min_value=-90, max_value=90, allow_null=True)
    longitude = serializers.FloatField(min_value=-180, max_value=180, allow_null=True)

    class Meta:
        model = Profile
        fields = (
            "username",
            "display_name",
            "bio",
            "profile_picture_url",
            "preferences",
            "onboarding_completed",
            "latitude",
            "longitude",
            "district",
            "city",
            "province",
        )
        read_only_fields = ("username", "onboarding_completed")

    def validate(self, attrs):
        latitude = attrs.get("latitude", self.instance.latitude)
        longitude = attrs.get("longitude", self.instance.longitude)
        if (latitude is None) != (longitude is None):
            raise serializers.ValidationError(
                "Latitude and longitude must be set or cleared together."
            )
        return attrs

    def get_profile_picture_url(self, profile):
        if not profile.profile_picture:
            return None
        return profile.profile_picture.url


class ClothingSerializer(serializers.ModelSerializer):
    owner = serializers.CharField(source="owner.username", read_only=True)
    owner_display_name = serializers.CharField(
        source="owner.profile.display_name", read_only=True
    )
    image_url = serializers.CharField(read_only=True)

    class Meta:
        model = Clothing
        fields = (
            "id",
            "uuid",
            "owner",
            "owner_display_name",
            "name",
            "description",
            "image_url",
            "type",
            "size",
            "condition",
            "status",
            "exchange_methods",
            "created_at",
        )
        read_only_fields = fields


class SwapRequestSerializer(serializers.ModelSerializer):
    requester = serializers.CharField(source="requester.username", read_only=True)
    requested_clothing = serializers.CharField(
        source="requested_clothing.name", read_only=True
    )
    offered_clothing = serializers.CharField(
        source="offered_clothing.name", read_only=True
    )

    class Meta:
        model = SwapRequest
        fields = (
            "id",
            "requester",
            "requested_clothing",
            "offered_clothing",
            "message",
            "status",
            "created_at",
        )
        read_only_fields = fields


class TransactionSerializer(serializers.ModelSerializer):
    swap_request_id = serializers.IntegerField(read_only=True)
    requester = serializers.CharField(
        source="swap_request.requester.username", read_only=True
    )
    owner = serializers.CharField(
        source="swap_request.requested_clothing.owner.username", read_only=True
    )

    class Meta:
        model = Transaction
        fields = (
            "id",
            "swap_request_id",
            "requester",
            "owner",
            "method",
            "status",
            "requester_courier",
            "requester_resi",
            "requester_delivery_estimate",
            "requester_resi_valid",
            "requester_started",
            "requester_received",
            "owner_courier",
            "owner_resi",
            "owner_delivery_estimate",
            "owner_resi_valid",
            "owner_started",
            "owner_received",
            "meetup_date",
            "meetup_location",
            "created_at",
            "completed_at",
        )
        read_only_fields = fields


class ChatRoomSerializer(serializers.ModelSerializer):
    swap_request_status = serializers.CharField(
        source="swap_request.status", read_only=True
    )
    other_user = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = ChatRoom
        fields = ("id", "swap_request_status", "other_user", "is_active", "created_at")
        read_only_fields = fields

    def get_other_user(self, room):
        user = room.other_user(self.context["request"].user)
        return {
            "username": user.username,
            "display_name": user.profile.display_name,
        }


class ChatMessageSerializer(serializers.ModelSerializer):
    sender = serializers.CharField(source="sender.username", read_only=True)
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = ("id", "sender", "is_mine", "message", "sent_at", "is_read")
        read_only_fields = fields

    def get_is_mine(self, message):
        return message.sender_id == self.context["request"].user.pk


class CreateChatMessageSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=2000, trim_whitespace=True)

    def validate_message(self, value):
        if not value:
            raise serializers.ValidationError("Message cannot be empty.")
        return value


class ReviewSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="author.username", read_only=True)
    recipient = serializers.CharField(source="recipient.username", read_only=True)
    transaction_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Review
        fields = (
            "id",
            "transaction_id",
            "author",
            "recipient",
            "rating",
            "comment",
            "created_at",
        )
        read_only_fields = fields
