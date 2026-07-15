from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.connections.models import Connection
from apps.connections.services import are_users_blocked, get_blocked_user_ids
from apps.profiles.api.serializers import (
    PrivateProfilePreviewSerializer,
    ProfilePublicSerializer,
    ProfileUpdateSerializer,
)
from apps.profiles.models import Profile


class ProfileViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    lookup_field = "user__username"
    lookup_url_kwarg = "username"

    def get_queryset(self):
        queryset = (
            Profile.objects.select_related("user")
            .filter(user__is_active=True)
            .order_by("-created_at")
        )

        blocked_user_ids = get_blocked_user_ids(self.request.user)

        if blocked_user_ids:
            queryset = queryset.exclude(user_id__in=blocked_user_ids)

        if self.action == "list":
            return queryset.filter(
                account_visibility=Profile.AccountVisibility.PUBLIC
            )

        return queryset

    def get_serializer_class(self):
        if self.action == "me" and self.request.method in ["PATCH", "PUT"]:
            return ProfileUpdateSerializer

        return ProfilePublicSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = ProfilePublicSerializer(
                page,
                many=True,
                context={
                    "request": request,
                },
            )
            return self.get_paginated_response(serializer.data)

        serializer = ProfilePublicSerializer(
            queryset,
            many=True,
            context={
                "request": request,
            },
        )
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        profile = get_object_or_404(
            Profile.objects.select_related("user").filter(user__is_active=True),
            user__username=kwargs.get("username"),
        )

        if are_users_blocked(request.user, profile.user):
            return Response(
                {
                    "detail": "This profile is not available."
                },
                status=403,
            )

        is_owner = profile.user_id == request.user.id
        is_connected = Connection.are_connected(request.user, profile.user)

        if profile.is_private and not is_owner and not is_connected:
            serializer = PrivateProfilePreviewSerializer(
                profile,
                context={
                    "request": request,
                },
            )
            return Response(serializer.data)

        serializer = ProfilePublicSerializer(
            profile,
            context={
                "request": request,
            },
        )
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get", "patch"],
        url_path="me",
    )
    def me(self, request):
        profile, created = Profile.objects.get_or_create(user=request.user)

        if request.method == "GET":
            serializer = ProfilePublicSerializer(
                profile,
                context={
                    "request": request,
                },
            )
            return Response(serializer.data)

        serializer = ProfileUpdateSerializer(
            profile,
            data=request.data,
            partial=True,
            context={
                "request": request,
            },
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        output_serializer = ProfilePublicSerializer(
            profile,
            context={
                "request": request,
            },
        )

        return Response(
            output_serializer.data,
            status=status.HTTP_200_OK,
        )
