from rest_framework import serializers

from .models import ChatMessage, ChatRoom


def serialize_message(message, user):
    return {
        "id": message.pk,
        "sender": message.sender.get_username(),
        "is_mine": message.sender_id == user.pk,
        "message": message.message,
        "sent_at": message.sent_at.isoformat(),
        "is_read": message.is_read,
    }


class ChatRoomSerializer(serializers.ModelSerializer):
    swap_request = serializers.IntegerField(
        source="swap_request_id",
        read_only=True,
    )
    partner_username = serializers.SerializerMethodField()
    partner_display_name = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)
    unread_count = serializers.IntegerField(read_only=True)
    last_message = serializers.CharField(read_only=True, allow_null=True)

    class Meta:
        model = ChatRoom
        fields = [
            "id",
            "swap_request",
            "partner_username",
            "partner_display_name",
            "is_active",
            "unread_count",
            "last_message",
            "created_at",
        ]
        read_only_fields = fields

    def get_partner_username(self, obj):
        partner = obj.other_user(self.context["request"].user)
        return partner.get_username()

    def get_partner_display_name(self, obj):
        partner = obj.other_user(self.context["request"].user)
        profile = getattr(partner, "profile", None)
        return profile.display_name if profile else partner.get_username()


class ChatMessageSerializer(serializers.ModelSerializer):
    chat_room = serializers.IntegerField(
        source="chat_room_id",
        read_only=True,
    )
    sender_username = serializers.CharField(
        source="sender.username",
        read_only=True,
    )
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "chat_room",
            "sender_username",
            "message",
            "sent_at",
            "is_read",
            "is_mine",
        ]
        read_only_fields = [
            "id",
            "chat_room",
            "sender_username",
            "sent_at",
            "is_read",
            "is_mine",
        ]

    def get_is_mine(self, obj):
        return obj.sender_id == self.context["request"].user.pk


class ChatMessageCreateSerializer(serializers.Serializer):
    message = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=2000,
        trim_whitespace=True,
    )
