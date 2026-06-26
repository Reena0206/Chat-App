from django.contrib.auth import get_user_model
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.api.serializers import (
    LoginSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserReadSerializer,
    UserUpdateSerializer,
)


User = get_user_model()


class AuthViewSet(viewsets.GenericViewSet):
    serializer_class = RegisterSerializer

    def get_permissions(self):
        if self.action == "logout":
            return [IsAuthenticated()]

        return [AllowAny()]

    def get_serializer_class(self):
        serializer_map = {
            "register": RegisterSerializer,
            "login": LoginSerializer,
            "logout": LogoutSerializer,
            "password_reset_request": PasswordResetRequestSerializer,
            "password_reset_confirm": PasswordResetConfirmSerializer,
        }

        return serializer_map.get(self.action, self.serializer_class)

    @action(
        detail=False,
        methods=["post"],
        url_path="register",
    )
    def register(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        return Response(
            {
                "message": "Account registered successfully.",
                "user": UserReadSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="login",
    )
    def login(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response(
            serializer.validated_data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="logout",
    )
    def logout(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Logged out successfully."
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="password-reset/request",
    )
    def password_reset_request(self, request):
        serializer = self.get_serializer(
            data=request.data,
            context={
                "request": request,
            },
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "If the email exists, a password reset message has been sent."
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="password-reset/confirm",
    )
    def password_reset_confirm(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Password has been reset successfully."
            },
            status=status.HTTP_200_OK,
        )


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserReadSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "username"

    def get_queryset(self):
        return User.objects.filter(is_active=True).order_by("-date_joined")

    @action(
        detail=False,
        methods=["get", "patch"],
        url_path="me",
    )
    def me(self, request):
        if request.method == "GET":
            serializer = UserReadSerializer(request.user)
            return Response(serializer.data)

        serializer = UserUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={
                "request": request,
            },
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            UserReadSerializer(request.user).data,
            status=status.HTTP_200_OK,
        )