from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from common.images import ImageUploadError, upload_image, validate_uploaded_image

from .models import Clothing


class ClothingSerializer(serializers.ModelSerializer):
    owner = serializers.CharField(source="owner.username", read_only=True)
    image_url = serializers.CharField(read_only=True)

    class Meta:
        model = Clothing
        fields = [
            "id",
            "uuid",
            "owner",
            "name",
            "description",
            "image_url",
            "type",
            "size",
            "condition",
            "status",
            "exchange_methods",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ClothingWriteSerializer(serializers.ModelSerializer):
    new_image = serializers.ImageField(required=False, write_only=True)
    exchange_methods = serializers.ListField(
        child=serializers.ChoiceField(
            choices=(("meetup", "Meetup"), ("delivery", "Delivery"))
        ),
        required=False,
    )

    class Meta:
        model = Clothing
        fields = [
            "name",
            "description",
            "new_image",
            "type",
            "size",
            "condition",
            "exchange_methods",
        ]

    def validate_new_image(self, value):
        try:
            validate_uploaded_image(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error
        return value

    def validate(self, attrs):
        if self.instance is None and not attrs.get("new_image"):
            raise serializers.ValidationError({"new_image": "This field is required."})
        return attrs

    def _upload_image(self, image):
        try:
            return upload_image(
                image,
                folder=f"swapify/clothing/{self.context['request'].user.pk}",
            )
        except ImageUploadError as error:
            raise serializers.ValidationError({"new_image": str(error)}) from error

    def create(self, validated_data):
        image = validated_data.pop("new_image", None)
        if image is not None:
            validated_data["image"] = self._upload_image(image)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        image = validated_data.pop("new_image", None)
        if image is not None:
            instance.image = self._upload_image(image)
        return super().update(instance, validated_data)
