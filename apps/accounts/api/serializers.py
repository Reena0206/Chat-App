from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db.models import Q
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken


User = get_user_model()


class UserReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "name",
            "date_joined",
        ]
        read_only_fields = fields


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "username",
            "name",
        ]

    def validate_username(self, value):
        value = value.strip().lower()
        user = self.context["request"].user

        username_exists = User.objects.filter(username=value).exclude(id=user.id).exists()

        if username_exists:
            raise serializers.ValidationError("This username is already taken.")

        return value


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8,
    )
    password2 = serializers.CharField(
        write_only=True,
        min_length=8,
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "name",
            "password",
            "password2",
        ]
        read_only_fields = ["id"]

    def validate_email(self, value):
        value = value.strip().lower()

        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered.")

        return value

    def validate_username(self, value):
        value = value.strip().lower()

        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")

        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError(
                {
                    "password": "Passwords do not match."
                }
            )

        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        password = validated_data.pop("password")

        return User.objects.create_user(
            password=password,
            **validated_data,
        )


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )

    def validate(self, attrs):
        identifier = attrs.get("identifier", "").strip().lower()
        password = attrs.get("password")

        if not identifier or not password:
            raise serializers.ValidationError("Username/email and password are required.")

        user = User.objects.filter(
            Q(email__iexact=identifier) | Q(username__iexact=identifier)
        ).first()

        if not user or not user.check_password(password):
            raise serializers.ValidationError("Invalid login credentials.")

        if not user.is_active:
            raise serializers.ValidationError("This account is inactive.")

        refresh = RefreshToken.for_user(user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserReadSerializer(user).data,
        }


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate_refresh(self, value):
        if not value:
            raise serializers.ValidationError("Refresh token is required.")

        return value

    def save(self, **kwargs):
        refresh_token = self.validated_data["refresh"]

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            raise serializers.ValidationError(
                {
                    "refresh": "Invalid or expired refresh token."
                }
            )


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()

    def save(self, **kwargs):
        request = self.context.get("request")
        email = self.validated_data["email"]

        user = User.objects.filter(
            email__iexact=email,
            is_active=True,
        ).first()

        if not user:
            return

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        reset_path = f"/reset-password/{uid}/{token}/"

        if request:
            reset_url = request.build_absolute_uri(reset_path)
        else:
            reset_url = reset_path

        message = (
            "You requested a password reset.\n\n"
            f"Reset URL: {reset_url}\n\n"
            f"UID: {uid}\n"
            f"Token: {token}\n\n"
            "If you did not request this, please ignore this email."
        )

        send_mail(
            subject="Password Reset Request",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
    )
    re_password = serializers.CharField(
        write_only=True,
        min_length=8,
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["re_password"]:
            raise serializers.ValidationError(
                {
                    "new_password": "Passwords do not match."
                }
            )

        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(
                pk=user_id,
                is_active=True,
            )
        except Exception:
            raise serializers.ValidationError(
                {
                    "uid": "Invalid password reset UID."
                }
            )

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError(
                {
                    "token": "Invalid or expired password reset token."
                }
            )

        validate_password(attrs["new_password"], user=user)

        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user