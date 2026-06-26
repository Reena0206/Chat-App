import uuid
from pathlib import Path

from django.conf import settings
from django.db import models


def profile_picture_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    filename = f"{uuid.uuid4().hex}{extension}"
    return f"profiles/user_{instance.user_id}/profile_pictures/{filename}"


class Profile(models.Model):
    class AccountVisibility(models.TextChoices):
        PUBLIC = "public", "Public"
        PRIVATE = "private", "Private"

    class LastSeenVisibility(models.TextChoices):
        EVERYONE = "everyone", "Everyone"
        CONNECTIONS = "connections", "Connections"
        NOBODY = "nobody", "Nobody"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    profile_picture = models.ImageField(
        upload_to=profile_picture_upload_to,
        blank=True,
        null=True,
    )
    bio = models.TextField(
        max_length=500,
        blank=True,
    )
    account_visibility = models.CharField(
        max_length=10,
        choices=AccountVisibility.choices,
        default=AccountVisibility.PUBLIC,
        db_index=True,
    )

    last_seen_visibility = models.CharField(
        max_length=20,
        choices=LastSeenVisibility.choices,
        default=LastSeenVisibility.CONNECTIONS,
        db_index=True,
    )
    read_receipts_enabled = models.BooleanField(
        default=True,
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["account_visibility"]),
            models.Index(fields=["last_seen_visibility"]),
            models.Index(fields=["read_receipts_enabled"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.user.username}'s profile"

    @property
    def is_private(self):
        return self.account_visibility == self.AccountVisibility.PRIVATE