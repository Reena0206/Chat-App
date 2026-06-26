from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        CONNECTION_REQUEST = "connection_request", "Connection Request"
        CONNECTION_ACCEPTED = "connection_accepted", "Connection Accepted"
        NEW_MESSAGE = "new_message", "New Message"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="triggered_notifications",
        blank=True,
        null=True,
    )
    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
        db_index=True,
    )
    title = models.CharField(
        max_length=255,
    )
    body = models.TextField(
        blank=True,
    )

    chat_room = models.ForeignKey(
        "chats.ChatRoom",
        on_delete=models.CASCADE,
        related_name="notifications",
        blank=True,
        null=True,
    )
    message = models.ForeignKey(
        "chats.Message",
        on_delete=models.CASCADE,
        related_name="notifications",
        blank=True,
        null=True,
    )
    connection_request = models.ForeignKey(
        "connections.ConnectionRequest",
        on_delete=models.CASCADE,
        related_name="notifications",
        blank=True,
        null=True,
    )

    is_read = models.BooleanField(
        default=False,
        db_index=True,
    )
    read_at = models.DateTimeField(
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
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
            models.Index(fields=["recipient", "created_at"]),
            models.Index(fields=["notification_type"]),
            models.Index(fields=["created_at"]),
        ]

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at", "updated_at"])

    def __str__(self):
        return f"{self.notification_type} → {self.recipient}"