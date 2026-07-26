import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


def chat_media_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    filename = f"{uuid.uuid4().hex}{extension}"
    return f"chats/room_{instance.message.room_id}/message_{instance.message_id}/{filename}"


class ChatRoom(models.Model):
    class RoomType(models.TextChoices):
        ONE_TO_ONE = "one_to_one", "One to One"

    room_type = models.CharField(
        max_length=20,
        choices=RoomType.choices,
        default=RoomType.ONE_TO_ONE,
        db_index=True,
    )
    room_key = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Unique key for one-to-one rooms.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_chat_rooms",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )
    last_message_at = models.DateTimeField(
        blank=True,
        null=True,
        db_index=True,
    )

    class Meta:
        ordering = ["-last_message_at", "-created_at"]
        indexes = [
            models.Index(fields=["room_type"]),
            models.Index(fields=["room_key"]),
            models.Index(fields=["last_message_at"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.room_type} - {self.room_key}"

    @staticmethod
    def build_one_to_one_room_key(user_a, user_b):
        if user_a.id == user_b.id:
            raise ValidationError("Cannot create a chat room with yourself.")

        first_id, second_id = sorted([user_a.id, user_b.id])
        return f"one_to_one:{first_id}:{second_id}"

    @classmethod
    def get_or_create_one_to_one_room(cls, user_a, user_b, created_by=None):
        room_key = cls.build_one_to_one_room_key(user_a, user_b)

        room, created = cls.objects.get_or_create(
            room_key=room_key,
            defaults={
                "room_type": cls.RoomType.ONE_TO_ONE,
                "created_by": created_by or user_a,
            },
        )

        if created:
            ChatRoomParticipant.objects.bulk_create(
                [
                    ChatRoomParticipant(room=room, user=user_a),
                    ChatRoomParticipant(room=room, user=user_b),
                ],
                ignore_conflicts=True,
            )

        return room


class ChatRoomParticipant(models.Model):
    room = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_participations",
    )
    joined_at = models.DateTimeField(
        auto_now_add=True,
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )
    muted_until = models.DateTimeField(
        blank=True,
        null=True,
    )
    last_seen_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ["joined_at"]
        indexes = [
            models.Index(fields=["room", "user"]),
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["joined_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["room", "user"],
                name="unique_chat_room_participant",
            ),
        ]

    def __str__(self):
        return f"{self.user} in room {self.room_id}"


class Message(models.Model):
    class MessageType(models.TextChoices):
        TEXT = "text", "Text"
        MEDIA = "media", "Media"
        SYSTEM = "system", "System"

    room = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    message_type = models.CharField(
        max_length=20,
        choices=MessageType.choices,
        default=MessageType.TEXT,
        db_index=True,
    )
    text = models.TextField(
        blank=True,
    )
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="replies",
        blank=True,
        null=True,
    )
    is_edited = models.BooleanField(
        default=False,
    )
    edited_at = models.DateTimeField(
        blank=True,
        null=True,
    )
    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
    )
    deleted_at = models.DateTimeField(
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["room", "created_at"]),
            models.Index(fields=["sender", "created_at"]),
            models.Index(fields=["message_type"]),
            models.Index(fields=["is_deleted"]),
        ]

    def clean(self):
        if self.message_type == self.MessageType.TEXT and not self.text.strip():
            raise ValidationError("Text message cannot be empty.")

    def save(self, *args, **kwargs):
        if self.text:
            self.text = self.text.strip()

        super().save(*args, **kwargs)

        ChatRoom.objects.filter(id=self.room_id).update(
            last_message_at=self.created_at,
        )

    def __str__(self):
        return f"Message {self.id} by {self.sender}"


class MessageMedia(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"
        VOICE = "voice", "Voice Note"
        DOCUMENT = "document", "Document"

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="media_files",
    )
    media_type = models.CharField(
        max_length=20,
        choices=MediaType.choices,
        db_index=True,
    )
    file = models.FileField(
        upload_to=chat_media_upload_to,
    )
    original_name = models.CharField(
        max_length=255,
        blank=True,
    )
    file_size = models.PositiveIntegerField(
        default=0,
    )
    duration_seconds = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Useful for videos and voice notes.",
    )
    thumbnail = models.ImageField(
        upload_to=chat_media_upload_to,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["message", "media_type"]),
            models.Index(fields=["media_type"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.media_type} for message {self.message_id}"


class MessageReadReceipt(models.Model):
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="read_receipts",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_read_receipts",
    )
    read_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-read_at"]
        indexes = [
            models.Index(fields=["message", "user"]),
            models.Index(fields=["user", "read_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["message", "user"],
                name="unique_message_read_receipt",
            ),
        ]

    def clean(self):
        if self.message_id and self.user_id:
            if self.message.sender_id == self.user_id:
                raise ValidationError("Sender does not need a read receipt.")

    def __str__(self):
        return f"{self.user} read message {self.message_id}"
    

class UserPresence(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="presence",
    )
    is_online = models.BooleanField(
        default=False,
        db_index=True,
    )
    last_seen_at = models.DateTimeField(
        blank=True,
        null=True,
        db_index=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["is_online"]),
            models.Index(fields=["last_seen_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {'online' if self.is_online else 'offline'}"


class UserChannelSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="channel_sessions",
    )
    channel_name = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
    )
    room = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name="channel_sessions",
        blank=True,
        null=True,
    )
    connected_at = models.DateTimeField(
        auto_now_add=True,
    )
    last_seen_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-connected_at"]
        indexes = [
            models.Index(fields=["user", "room"]),
            models.Index(fields=["channel_name"]),
            models.Index(fields=["connected_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.channel_name}"