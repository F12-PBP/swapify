from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from apps.clothing_catalog.models import Clothing

from .models import SwapRequest


class SwapClothingSerializer(serializers.ModelSerializer):
    owner = serializers.CharField(source="owner.username", read_only=True)
    image_url = serializers.CharField(read_only=True)

    class Meta:
        model = Clothing
        fields = [
            "uuid",
            "owner",
            "name",
            "image_url",
            "type",
            "size",
            "condition",
            "status",
            "exchange_methods",
        ]
        read_only_fields = fields


class SwapRequestSerializer(serializers.ModelSerializer):
    requester = serializers.CharField(source="requester.username", read_only=True)
    owner = serializers.CharField(
        source="requested_clothing.owner.username",
        read_only=True,
    )
    requested_clothing = SwapClothingSerializer(read_only=True)
    offered_clothing = SwapClothingSerializer(read_only=True)
    role = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()
    transaction = serializers.SerializerMethodField()
    chat_room = serializers.SerializerMethodField()
    has_reviewed = serializers.SerializerMethodField()

    class Meta:
        model = SwapRequest
        fields = [
            "id",
            "status",
            "message",
            "requester",
            "owner",
            "role",
            "requested_clothing",
            "offered_clothing",
            "actions",
            "transaction",
            "chat_room",
            "has_reviewed",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def _viewer(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def get_role(self, obj):
        viewer = self._viewer()
        if viewer is None:
            return None
        if obj.requester_id == viewer.pk:
            return "sent"
        if obj.requested_clothing.owner_id == viewer.pk:
            return "received"
        return None

    def get_actions(self, obj):
        if obj.status != SwapRequest.Status.PENDING:
            return []
        role = self.get_role(obj)
        if role == "received":
            return ["accept", "reject"]
        if role == "sent":
            return ["cancel"]
        return []

    def get_transaction(self, obj):
        try:
            return str(obj.transaction.pk)
        except ObjectDoesNotExist:
            return None

    def get_chat_room(self, obj):
        try:
            return obj.chat_room.pk
        except ObjectDoesNotExist:
            return None

    def get_has_reviewed(self, obj):
        return bool(getattr(obj, "has_reviewed", False))


class SwapRequestCreateSerializer(serializers.Serializer):
    requested_clothing = serializers.UUIDField()
    offered_clothing = serializers.UUIDField()
    message = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000,
        default="",
    )

    def validate(self, attrs):
        if attrs["requested_clothing"] == attrs["offered_clothing"]:
            raise serializers.ValidationError(
                {"offered_clothing": "Choose a different piece to offer."}
            )
        return attrs
