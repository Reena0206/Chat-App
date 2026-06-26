from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.notifications.models import Notification


User = get_user_model()


class NotificationUserSerializer(serializers.ModelSerializer):
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "name",
            "profile_picture_url",
        ]
        read_only_fields = fields

    def get_profile_picture_url(self, obj):
        request = self.context.get("request")
        profile = getattr(obj, "profile", None)

        if not profile or not profile.profile_picture:
            return None

        if request:
            return request.build_absolute_uri(profile.profile_picture.url)

        return profile.profile_picture.url


class NotificationReadSerializer(serializers.ModelSerializer):
    actor = NotificationUserSerializer(read_only=True)
    reference = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "notification_type",
            "title",
            "body",
            "actor",
            "reference",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_reference(self, obj):
        return {
            "chat_room_id": obj.chat_room_id,
            "message_id": obj.message_id,
            "connection_request_id": obj.connection_request_id,
        }