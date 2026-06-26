from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.connections.models import (
    Connection,
    ConnectionRequest,
    UserBlock,
    UserRestriction,
)
from apps.connections.services import are_users_blocked


User = get_user_model()


class ConnectionUserSerializer(serializers.ModelSerializer):
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


class ConnectionRequestReadSerializer(serializers.ModelSerializer):
    from_user = ConnectionUserSerializer(read_only=True)
    to_user = ConnectionUserSerializer(read_only=True)

    class Meta:
        model = ConnectionRequest
        fields = [
            "id",
            "from_user",
            "to_user",
            "status",
            "created_at",
            "updated_at",
            "responded_at",
        ]
        read_only_fields = fields


class SendConnectionRequestSerializer(serializers.Serializer):
    username = serializers.CharField()

    def validate_username(self, value):
        username = value.strip().lower()

        if not username:
            raise serializers.ValidationError("Username is required.")

        return username

    def validate(self, attrs):
        request = self.context["request"]
        username = attrs["username"]

        try:
            target_user = User.objects.get(
                username=username,
                is_active=True,
            )
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {
                    "username": "User not found."
                }
            )

        if target_user.id == request.user.id:
            raise serializers.ValidationError(
                {
                    "username": "You cannot send a connection request to yourself."
                }
            )

        if are_users_blocked(request.user, target_user):
            raise serializers.ValidationError(
                "You cannot send a connection request to this user."
            )

        if Connection.are_connected(request.user, target_user):
            raise serializers.ValidationError(
                "You are already connected with this user."
            )

        reverse_pending_request = ConnectionRequest.objects.filter(
            from_user=target_user,
            to_user=request.user,
            status=ConnectionRequest.Status.PENDING,
        ).first()

        if reverse_pending_request:
            raise serializers.ValidationError(
                "This user has already sent you a request. Please accept that request instead."
            )

        attrs["target_user"] = target_user
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        target_user = validated_data["target_user"]

        connection_request, created = ConnectionRequest.objects.get_or_create(
            from_user=request.user,
            to_user=target_user,
            defaults={
                "status": ConnectionRequest.Status.PENDING,
            },
        )

        if not created:
            if connection_request.status == ConnectionRequest.Status.PENDING:
                raise serializers.ValidationError(
                    "A connection request is already pending."
                )

            connection_request.status = ConnectionRequest.Status.PENDING
            connection_request.responded_at = None
            connection_request.save(
                update_fields=[
                    "status",
                    "responded_at",
                    "updated_at",
                ]
            )

        return connection_request


class ConnectionSerializer(serializers.ModelSerializer):
    connected_user = serializers.SerializerMethodField()

    class Meta:
        model = Connection
        fields = [
            "id",
            "connected_user",
            "created_at",
        ]
        read_only_fields = fields

    def get_connected_user(self, obj):
        request = self.context["request"]
        other_user = obj.get_other_user(request.user)

        return ConnectionUserSerializer(
            other_user,
            context={
                "request": request,
            },
        ).data


class UserActionSerializer(serializers.Serializer):
    username = serializers.CharField()
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
    )

    def validate_username(self, value):
        username = value.strip().lower()

        if not username:
            raise serializers.ValidationError("Username is required.")

        return username

    def validate(self, attrs):
        request = self.context["request"]
        username = attrs["username"]

        try:
            target_user = User.objects.get(
                username=username,
                is_active=True,
            )
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {
                    "username": "User not found."
                }
            )

        if target_user.id == request.user.id:
            raise serializers.ValidationError(
                {
                    "username": "You cannot perform this action on yourself."
                }
            )

        attrs["target_user"] = target_user
        return attrs


class UserBlockSerializer(serializers.ModelSerializer):
    blocked = ConnectionUserSerializer(read_only=True)

    class Meta:
        model = UserBlock
        fields = [
            "id",
            "blocked",
            "reason",
            "created_at",
        ]
        read_only_fields = fields


class UserRestrictionSerializer(serializers.ModelSerializer):
    restricted_user = ConnectionUserSerializer(read_only=True)

    class Meta:
        model = UserRestriction
        fields = [
            "id",
            "restricted_user",
            "created_at",
        ]
        read_only_fields = fields