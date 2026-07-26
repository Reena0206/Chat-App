import mimetypes
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from apps.chats.models import (
    ChatRoom,
    ChatRoomParticipant,
    Message,
    MessageMedia,
    MessageReadReceipt,
)
from apps.connections.models import Connection, UserBlock
from apps.connections.services import are_users_blocked, restricts_user
from apps.profiles.models import Profile


User = get_user_model()


class ChatUserSerializer(serializers.ModelSerializer):
    profile_picture_url = serializers.SerializerMethodField()
    is_online = serializers.SerializerMethodField()
    last_seen_at = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "name",
            "profile_picture_url",
            "is_online",
            "last_seen_at",
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

    def can_view_presence(self, obj):
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            return False

        viewer = request.user

        if viewer.id == obj.id:
            return True

        if are_users_blocked(viewer, obj):
            return False

        if restricts_user(owner=obj, restricted_user=viewer):
            return False

        profile = getattr(obj, "profile", None)

        if not profile:
            return False

        if profile.last_seen_visibility == Profile.LastSeenVisibility.NOBODY:
            return False

        if profile.last_seen_visibility == Profile.LastSeenVisibility.CONNECTIONS:
            return Connection.are_connected(viewer, obj)

        return True

    def get_is_online(self, obj):
        if not self.can_view_presence(obj):
            return False

        presence = getattr(obj, "presence", None)

        if not presence:
            return False

        return presence.is_online

    def get_last_seen_at(self, obj):
        if not self.can_view_presence(obj):
            return None

        presence = getattr(obj, "presence", None)

        if not presence or not presence.last_seen_at:
            return None

        return presence.last_seen_at.isoformat()


class MessageMediaReadSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = MessageMedia
        fields = [
            "id",
            "media_type",
            "file_url",
            "thumbnail_url",
            "original_name",
            "file_size",
            "duration_seconds",
            "created_at",
        ]
        read_only_fields = fields

    def get_file_url(self, obj):
        request = self.context.get("request")

        if not obj.file:
            return None

        if request:
            return request.build_absolute_uri(obj.file.url)

        return obj.file.url

    def get_thumbnail_url(self, obj):
        request = self.context.get("request")

        if not obj.thumbnail:
            return None

        if request:
            return request.build_absolute_uri(obj.thumbnail.url)

        return obj.thumbnail.url


class MessageReadReceiptSerializer(serializers.ModelSerializer):
    user = ChatUserSerializer(read_only=True)

    class Meta:
        model = MessageReadReceipt
        fields = [
            "id",
            "user",
            "read_at",
        ]
        read_only_fields = fields


class MessageReadSerializer(serializers.ModelSerializer):
    sender = ChatUserSerializer(read_only=True)
    media_files = MessageMediaReadSerializer(many=True, read_only=True)
    read_receipts = MessageReadReceiptSerializer(many=True, read_only=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "room",
            "sender",
            "message_type",
            "text",
            "reply_to",
            "media_files",
            "read_receipts",
            "is_edited",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class MessageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            "text",
            "reply_to",
        ]

    def validate_text(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError("Message cannot be empty.")

        if len(value) > 5000:
            raise serializers.ValidationError("Message cannot exceed 5000 characters.")

        return value

    def validate_reply_to(self, value):
        room = self.context["room"]

        if value and value.room_id != room.id:
            raise serializers.ValidationError("Reply message must belong to the same room.")

        return value

    def create(self, validated_data):
        request = self.context["request"]
        room = self.context["room"]

        return Message.objects.create(
            room=room,
            sender=request.user,
            message_type=Message.MessageType.TEXT,
            **validated_data,
        )


class MediaMessageCreateSerializer(serializers.Serializer):
    media_type = serializers.ChoiceField(
        choices=MessageMedia.MediaType.choices,
    )
    file = serializers.FileField()
    text = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=5000,
    )
    thumbnail = serializers.ImageField(
        required=False,
        allow_null=True,
    )
    duration_seconds = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        max_value=3600,
    )
    reply_to = serializers.PrimaryKeyRelatedField(
        queryset=Message.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )

    IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp", ".gif"]
    VIDEO_EXTENSIONS = [".mp4", ".webm", ".mov", ".m4v", ".mkv", ".avi"]
    VOICE_EXTENSIONS = [".mp3", ".wav", ".m4a", ".ogg", ".webm", ".aac"]

    IMAGE_CONTENT_TYPES = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "application/octet-stream",
    ]
    VIDEO_CONTENT_TYPES = [
        "video/mp4",
        "video/webm",
        "video/quicktime",
        "video/x-m4v",
        "video/m4v",
        "video/x-matroska",
        "video/matroska",
        "application/x-matroska",
        "video/mkv",
        "video/x-mkv",
        "video/avi",
        "video/x-msvideo",
        "application/octet-stream",
    ]
    VOICE_CONTENT_TYPES = [
        "audio/mpeg",
        "audio/wav",
        "audio/x-wav",
        "audio/mp4",
        "audio/aac",
        "audio/ogg",
        "audio/webm",
        "application/octet-stream",
    ]

    def validate_text(self, value):
        return value.strip()

    def validate_reply_to(self, value):
        room = self.context["room"]

        if value and value.room_id != room.id:
            raise serializers.ValidationError("Reply message must belong to the same room.")

        return value

    def validate_thumbnail(self, value):
        if not value:
            return value

        max_size = getattr(settings, "CHAT_THUMBNAIL_MAX_SIZE", 5 * 1024 * 1024)

        if value.size > max_size:
            raise serializers.ValidationError("Thumbnail size cannot exceed 5 MB.")

        extension = Path(value.name).suffix.lower()
        content_type = getattr(value, "content_type", None)
        guessed_type = mimetypes.guess_type(value.name)[0]
        detected_type = content_type or guessed_type or ""

        if extension not in self.IMAGE_EXTENSIONS:
            raise serializers.ValidationError("Thumbnail must be JPG, PNG, WEBP, or GIF.")

        is_valid_type = (
            not detected_type
            or detected_type.startswith("image/")
            or detected_type in self.IMAGE_CONTENT_TYPES
        )

        if not is_valid_type:
            raise serializers.ValidationError("Invalid thumbnail file type.")

        return value

    def validate(self, attrs):
        media_type = attrs["media_type"]
        uploaded_file = attrs["file"]

        self.validate_uploaded_file(
            uploaded_file=uploaded_file,
            media_type=media_type,
        )

        return attrs

    def validate_uploaded_file(self, uploaded_file, media_type):
        extension = Path(uploaded_file.name).suffix.lower()
        content_type = getattr(uploaded_file, "content_type", None)
        guessed_type = mimetypes.guess_type(uploaded_file.name)[0]
        detected_type = content_type or guessed_type or ""
        size = uploaded_file.size

        if media_type == MessageMedia.MediaType.IMAGE:
            max_size = getattr(settings, "CHAT_IMAGE_MAX_SIZE", 5 * 1024 * 1024)

            if size > max_size:
                raise serializers.ValidationError({"file": "Image size cannot exceed 5 MB."})

            if extension not in self.IMAGE_EXTENSIONS:
                raise serializers.ValidationError({"file": "Image must be JPG, JPEG, PNG, WEBP, or GIF."})

            is_valid_type = (
                not detected_type
                or detected_type.startswith("image/")
                or detected_type in self.IMAGE_CONTENT_TYPES
            )

            if not is_valid_type:
                raise serializers.ValidationError({"file": "Invalid image file type."})

        elif media_type == MessageMedia.MediaType.VIDEO:
            max_size = getattr(settings, "CHAT_VIDEO_MAX_SIZE", 50 * 1024 * 1024)

            if size > max_size:
                raise serializers.ValidationError({"file": "Video size cannot exceed 50 MB."})

            if extension not in self.VIDEO_EXTENSIONS:
                raise serializers.ValidationError({"file": f"Video must be one of: {', '.join(self.VIDEO_EXTENSIONS)}."})

            is_valid_type = (
                not detected_type
                or detected_type.startswith("video/")
                or detected_type.startswith("application/")
                or detected_type in self.VIDEO_CONTENT_TYPES
            )

            if not is_valid_type:
                raise serializers.ValidationError({"file": "Invalid video file type."})

        elif media_type == MessageMedia.MediaType.VOICE:
            max_size = getattr(settings, "CHAT_VOICE_MAX_SIZE", 10 * 1024 * 1024)

            if size > max_size:
                raise serializers.ValidationError({"file": "Voice note size cannot exceed 10 MB."})

            if extension not in self.VOICE_EXTENSIONS:
                raise serializers.ValidationError({"file": "Voice note must be MP3, WAV, M4A, OGG, WEBM, or AAC."})

            is_valid_type = (
                not detected_type
                or detected_type.startswith("audio/")
                or detected_type.startswith("video/")
                or detected_type in self.VOICE_CONTENT_TYPES
            )

            if not is_valid_type:
                raise serializers.ValidationError({"file": "Invalid voice note file type."})

        elif media_type == MessageMedia.MediaType.DOCUMENT:
            max_size = getattr(settings, "CHAT_DOCUMENT_MAX_SIZE", 50 * 1024 * 1024)

            if size > max_size:
                raise serializers.ValidationError({"file": "Document file size cannot exceed 50 MB."})

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        room = self.context["room"]

        uploaded_file = validated_data["file"]
        media_type = validated_data["media_type"]
        text = validated_data.get("text", "")
        reply_to = validated_data.get("reply_to")
        thumbnail = validated_data.get("thumbnail")
        duration_seconds = validated_data.get("duration_seconds")

        message = Message.objects.create(
            room=room,
            sender=request.user,
            message_type=Message.MessageType.MEDIA,
            text=text,
            reply_to=reply_to,
        )

        MessageMedia.objects.create(
            message=message,
            media_type=media_type,
            file=uploaded_file,
            thumbnail=thumbnail,
            original_name=uploaded_file.name[:255],
            file_size=uploaded_file.size,
            duration_seconds=duration_seconds,
        )

        return message


class ChatRoomSerializer(serializers.ModelSerializer):
    participants = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    is_blocked = serializers.SerializerMethodField()
    blocked_participant_id = serializers.SerializerMethodField()
    block_status = serializers.SerializerMethodField()
    blocked_by_username = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = [
            "id",
            "room_type",
            "room_key",
            "participants",
            "last_message",
            "unread_count",
            "is_blocked",
            "blocked_participant_id",
            "block_status",
            "blocked_by_username",
            "created_at",
            "updated_at",
            "last_message_at",
        ]
        read_only_fields = fields


    def get_block_record(self, obj):
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            return None

        other_user_ids = [
            participant.user_id
            for participant in obj.participants.all()
            if participant.is_active and participant.user_id != request.user.id
        ]

        if not other_user_ids:
            return None

        return (
            UserBlock.objects.select_related("blocker", "blocked")
            .filter(
                Q(blocker=request.user, blocked_id__in=other_user_ids)
                | Q(blocker_id__in=other_user_ids, blocked=request.user)
            )
            .first()
        )

    def get_blocked_participant(self, obj):
        request = self.context.get("request")
        block = self.get_block_record(obj)

        if not request or not block:
            return None

        if block.blocker_id == request.user.id:
            return block.blocked

        return block.blocker

    def get_is_blocked(self, obj):
        return self.get_block_record(obj) is not None

    def get_blocked_participant_id(self, obj):
        blocked_user = self.get_blocked_participant(obj)
        return blocked_user.id if blocked_user else None

    def get_block_status(self, obj):
        request = self.context.get("request")
        block = self.get_block_record(obj)

        if not request or not block:
            return ""

        if block.blocker_id == request.user.id:
            return "you_blocked"

        return "blocked_by"

    def get_blocked_by_username(self, obj):
        request = self.context.get("request")
        block = self.get_block_record(obj)

        if not request or not block or block.blocker_id == request.user.id:
            return ""

        return block.blocker.username
    def get_participants(self, obj):
        request = self.context.get("request")

        participants = [
            participant.user
            for participant in obj.participants.all()
            if participant.is_active
        ]

        return ChatUserSerializer(
            participants,
            many=True,
            context={
                "request": request,
            },
        ).data

    def get_last_message(self, obj):
        request = self.context.get("request")

        message = (
            obj.messages.filter(is_deleted=False)
            .select_related(
                "sender",
                "sender__profile",
                "sender__presence",
            )
            .prefetch_related(
                "media_files",
                "read_receipts",
                "read_receipts__user",
                "read_receipts__user__profile",
                "read_receipts__user__presence",
            )
            .order_by("-created_at")
            .first()
        )

        if not message:
            return None

        return MessageReadSerializer(
            message,
            context={
                "request": request,
            },
        ).data

    def get_unread_count(self, obj):
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            return 0

        participant = obj.participants.filter(
            user=request.user,
            is_active=True,
        ).only("last_seen_at", "joined_at").first()

        if not participant:
            return 0

        seen_at = participant.last_seen_at or participant.joined_at
        queryset = obj.messages.filter(is_deleted=False).exclude(sender=request.user)

        if seen_at:
            queryset = queryset.filter(created_at__gt=seen_at)

        return queryset.count()


class CreateOneToOneRoomSerializer(serializers.Serializer):
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
                    "username": "You cannot create a chat with yourself."
                }
            )

        if are_users_blocked(request.user, target_user):
            raise serializers.ValidationError(
                "You cannot start a chat with this user."
            )

        if not Connection.are_connected(request.user, target_user):
            raise serializers.ValidationError(
                "You can start a chat only with an accepted connection."
            )

        attrs["target_user"] = target_user
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        target_user = validated_data["target_user"]

        return ChatRoom.get_or_create_one_to_one_room(
            request.user,
            target_user,
            created_by=request.user,
        )
