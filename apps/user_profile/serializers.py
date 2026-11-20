from rest_framework import serializers

from apps.clothing_catalog.categories import STYLE_CHOICES

from .models import Profile


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        source="user.username",
        read_only=True,
    )
    profile_picture_url = serializers.SerializerMethodField()

    preferences = serializers.ListField(
        child=serializers.ChoiceField(choices=STYLE_CHOICES),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = Profile
        fields = [
            "username",
            "display_name",
            "bio",
            "preferences",
            "profile_picture_url",
            "district",
            "city",
            "province",
            "onboarding_completed",
        ]

        read_only_fields = [
            "username",
            "profile_picture_url",
            "district",
            "city",
            "province",
            "onboarding_completed",
        ]

    def get_profile_picture_url(self, obj):
        if not obj.profile_picture:
            return None

        return obj.profile_picture.url

    def validate_display_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError("Display name cannot be empty.")

        return value

    def validate_preferences(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "Preferences must not contain duplicates."
            )

        return value
