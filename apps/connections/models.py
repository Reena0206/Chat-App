from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class ConnectionRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_connection_requests",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_connection_requests",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )
    responded_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["from_user", "status"]),
            models.Index(fields=["to_user", "status"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["from_user", "to_user"],
                name="unique_directed_connection_request",
            ),
            models.CheckConstraint(
                condition=~Q(from_user=F("to_user")),
                name="prevent_self_connection_request",
            ),
        ]

    def clean(self):
        if self.from_user_id and self.to_user_id:
            if self.from_user_id == self.to_user_id:
                raise ValidationError("You cannot send a connection request to yourself.")

    def mark_accepted(self):
        self.status = self.Status.ACCEPTED
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at", "updated_at"])

    def mark_rejected(self):
        self.status = self.Status.REJECTED
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at", "updated_at"])

    def mark_cancelled(self):
        self.status = self.Status.CANCELLED
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at", "updated_at"])

    def __str__(self):
        return f"{self.from_user} → {self.to_user} ({self.status})"


class Connection(models.Model):
    user1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="connections_as_user1",
    )
    user2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="connections_as_user2",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user1", "user2"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user1", "user2"],
                name="unique_connection_pair",
            ),
            models.CheckConstraint(
                condition=~Q(user1=F("user2")),
                name="prevent_self_connection",
            ),
        ]

    def clean(self):
        if self.user1_id and self.user2_id:
            if self.user1_id == self.user2_id:
                raise ValidationError("A user cannot connect with themselves.")

    def save(self, *args, **kwargs):
        if self.user1_id and self.user2_id and self.user1_id > self.user2_id:
            self.user1_id, self.user2_id = self.user2_id, self.user1_id
            if hasattr(self, "_user1_cache"):
                delattr(self, "_user1_cache")
            if hasattr(self, "_user2_cache"):
                delattr(self, "_user2_cache")

        super().save(*args, **kwargs)

    @classmethod
    def normalize_users(cls, user_a, user_b):
        if user_a.id == user_b.id:
            raise ValidationError("A user cannot connect with themselves.")

        if user_a.id < user_b.id:
            return user_a, user_b

        return user_b, user_a

    @classmethod
    def create_connection(cls, user_a, user_b):
        user1, user2 = cls.normalize_users(user_a, user_b)

        connection, created = cls.objects.get_or_create(
            user1=user1,
            user2=user2,
        )

        return connection

    @classmethod
    def are_connected(cls, user_a, user_b):
        if not user_a or not user_b:
            return False

        if not user_a.is_authenticated or not user_b.is_authenticated:
            return False

        if user_a.id == user_b.id:
            return True

        user1, user2 = cls.normalize_users(user_a, user_b)

        return cls.objects.filter(
            user1=user1,
            user2=user2,
        ).exists()

    @classmethod
    def get_connection_between(cls, user_a, user_b):
        user1, user2 = cls.normalize_users(user_a, user_b)

        return cls.objects.filter(
            user1=user1,
            user2=user2,
        ).first()

    def get_other_user(self, current_user):
        if self.user1_id == current_user.id:
            return self.user2

        return self.user1

    def __str__(self):
        return f"{self.user1} ↔ {self.user2}"


class UserBlock(models.Model):
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocked_users",
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocked_by_users",
    )
    reason = models.CharField(
        max_length=255,
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["blocker", "blocked"]),
            models.Index(fields=["blocked"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["blocker", "blocked"],
                name="unique_user_block",
            ),
            models.CheckConstraint(
                condition=~Q(blocker=F("blocked")),
                name="prevent_self_block",
            ),
        ]

    def clean(self):
        if self.blocker_id and self.blocked_id:
            if self.blocker_id == self.blocked_id:
                raise ValidationError("You cannot block yourself.")

    def __str__(self):
        return f"{self.blocker} blocked {self.blocked}"


class UserRestriction(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="restricted_users",
    )
    restricted_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="restricted_by_users",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "restricted_user"]),
            models.Index(fields=["restricted_user"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "restricted_user"],
                name="unique_user_restriction",
            ),
            models.CheckConstraint(
                condition=~Q(owner=F("restricted_user")),
                name="prevent_self_restriction",
            ),
        ]

    def clean(self):
        if self.owner_id and self.restricted_user_id:
            if self.owner_id == self.restricted_user_id:
                raise ValidationError("You cannot restrict yourself.")

    def __str__(self):
        return f"{self.owner} restricted {self.restricted_user}"