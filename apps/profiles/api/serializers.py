from rest_framework import serializers

from apps.connections.services import are_users_blocked, restricts_user
from apps.profiles.models import Profile

class ProfilePublicSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="user.id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    name = serializers.CharField(source="user.name", read_only=True)
    profile_picture_url = serializers.SerializerMethodField()
    is_private = serializers.BooleanField(read_only=True)

    class Meta:
        model = Profile
        fields = [
            "id",
            "email",
            "username",
            "name",
            "profile_picture_url",
            "bio",
            "account_visibility",
            "is_private",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_profile_picture_url(self, obj):
        request = self.context.get("request")

        if not obj.profile_picture:
            return None

        if request:
            return request.build_absolute_uri(obj.profile_picture.url)

        return obj.profile_picture.url


class PrivateProfilePreviewSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    name = serializers.CharField(source="user.name", read_only=True)
    profile_picture_url = serializers.SerializerMethodField()
    is_private = serializers.BooleanField(read_only=True)
    message = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "id",
            "username",
            "name",
            "profile_picture_url",
            "account_visibility",
            "is_private",
            "message",
        ]
        read_only_fields = fields

    def get_profile_picture_url(self, obj):
        request = self.context.get("request")

        if not obj.profile_picture:
            return None

        if request:
            return request.build_absolute_uri(obj.profile_picture.url)

        return obj.profile_picture.url

    def get_message(self, obj):
        return "This account is private."


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = [
            "profile_picture",
            "bio",
            "account_visibility",
            "last_seen_visibility",
            "read_receipts_enabled",
        ]

    def validate_profile_picture(self, value):
        if not value:
            return value

        max_size = 5 * 1024 * 1024

        if value.size > max_size:
            raise serializers.ValidationError("Profile picture size cannot exceed 5 MB.")

        allowed_content_types = [
            "image/jpeg",
            "image/png",
            "image/webp",
        ]

        content_type = getattr(value, "content_type", None)

        if content_type not in allowed_content_types:
            raise serializers.ValidationError(
                "Only JPEG, PNG, and WEBP images are allowed."
            )

        return value

    def validate_bio(self, value):
        return value.strip()

    def validate_account_visibility(self, value):
        allowed_values = [
            Profile.AccountVisibility.PUBLIC,
            Profile.AccountVisibility.PRIVATE,
        ]

        if value not in allowed_values:
            raise serializers.ValidationError("Invalid account visibility.")

        return value

    def validate_last_seen_visibility(self, value):
        allowed_values = [
            Profile.LastSeenVisibility.EVERYONE,
            Profile.LastSeenVisibility.CONNECTIONS,
            Profile.LastSeenVisibility.NOBODY,
        ]

        if value not in allowed_values:
            raise serializers.ValidationError("Invalid last seen visibility.")

        return value