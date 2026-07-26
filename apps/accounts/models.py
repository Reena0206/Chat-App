from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def _create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError("Email address is required.")

        if not username:
            raise ValueError("Username is required.")

        email = self.normalize_email(email).lower()
        username = username.strip().lower()

        user = self.model(
            email=email,
            username=username,
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_superuser", False)

        return self._create_user(
            email=email,
            username=username,
            password=password,
            **extra_fields,
        )

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(
            email=email,
            username=username,
            password=password,
            **extra_fields,
        )


class User(AbstractBaseUser, PermissionsMixin):
    username_validator = RegexValidator(
        regex=r"^[a-zA-Z0-9._]+$",
        message="Username can contain only letters, numbers, dots, and underscores.",
    )

    email = models.EmailField(
        unique=True,
        db_index=True,
    )
    username = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        validators=[username_validator],
    )
    name = models.CharField(
        max_length=150,
        blank=True,
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["date_joined"]),
        ]

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower().strip()

        if self.username:
            self.username = self.username.lower().strip()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.username