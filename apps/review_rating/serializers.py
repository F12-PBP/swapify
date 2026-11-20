from rest_framework import serializers

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    author = serializers.CharField(
        source="author.username",
        read_only=True,
    )
    recipient = serializers.CharField(
        source="recipient.username",
        read_only=True,
    )
    transaction = serializers.UUIDField(
        source="transaction_id",
        read_only=True,
    )

    class Meta:
        model = Review
        fields = [
            "id",
            "transaction",
            "author",
            "recipient",
            "rating",
            "comment",
            "created_at",
        ]
        read_only_fields = fields


class ReviewCreateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000,
        default="",
    )
