from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.connections.api.serializers import (
    ConnectionRequestReadSerializer,
    ConnectionSerializer,
    SendConnectionRequestSerializer,
    UserActionSerializer,
    UserBlockSerializer,
    UserRestrictionSerializer,
)
from apps.connections.models import Connection, ConnectionRequest

from apps.notifications.services import (
    create_connection_accepted_notification,
    create_connection_request_notification,
)

from apps.connections.models import Connection, ConnectionRequest, UserBlock, UserRestriction
from apps.connections.services import cleanup_after_block

class ConnectionRequestViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ConnectionRequestReadSerializer

    def get_queryset(self):
        return (
            ConnectionRequest.objects.select_related(
                "from_user",
                "to_user",
                "from_user__profile",
                "to_user__profile",
            )
            .filter(
                Q(from_user=self.request.user) | Q(to_user=self.request.user)
            )
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "send":
            return SendConnectionRequestSerializer

        return ConnectionRequestReadSerializer

    @action(
        detail=False,
        methods=["post"],
        url_path="send",
    )
    def send(self, request):
        serializer = self.get_serializer(
            data=request.data,
            context={
                "request": request,
            },
        )
        serializer.is_valid(raise_exception=True)

        connection_request = serializer.save()

        create_connection_request_notification(
            from_user=request.user,
            to_user=connection_request.to_user,
            connection_request=connection_request,
        )

        output_serializer = ConnectionRequestReadSerializer(
            connection_request,
            context={
                "request": request,
            },
        )

        return Response(
            {
                "message": "Connection request sent successfully.",
                "request": output_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="incoming",
    )
    def incoming(self, request):
        queryset = self.get_queryset().filter(
            to_user=request.user,
            status=ConnectionRequest.Status.PENDING,
        )

        serializer = ConnectionRequestReadSerializer(
            queryset,
            many=True,
            context={
                "request": request,
            },
        )

        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        url_path="outgoing",
    )
    def outgoing(self, request):
        queryset = self.get_queryset().filter(
            from_user=request.user,
            status=ConnectionRequest.Status.PENDING,
        )

        serializer = ConnectionRequestReadSerializer(
            queryset,
            many=True,
            context={
                "request": request,
            },
        )

        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        url_path="accept",
    )
    def accept(self, request, pk=None):
        connection_request = self.get_object()

        if connection_request.to_user_id != request.user.id:
            return Response(
                {
                    "detail": "Only the receiver can accept this request."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if connection_request.status != ConnectionRequest.Status.PENDING:
            return Response(
                {
                    "detail": "Only pending requests can be accepted."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            connection = Connection.create_connection(
                connection_request.from_user,
                connection_request.to_user,
            )

            connection_request.mark_accepted()

            create_connection_accepted_notification(
                accepted_by=request.user,
                request_sender=connection_request.from_user,
                connection_request=connection_request,
            )

            ConnectionRequest.objects.filter(
                from_user=connection_request.to_user,
                to_user=connection_request.from_user,
                status=ConnectionRequest.Status.PENDING,
            ).update(
                status=ConnectionRequest.Status.CANCELLED,
                responded_at=timezone.now(),
            )

        return Response(
            {
                "message": "Connection request accepted successfully.",
                "connection": ConnectionSerializer(
                    connection,
                    context={
                        "request": request,
                    },
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="reject",
    )
    def reject(self, request, pk=None):
        connection_request = self.get_object()

        if connection_request.to_user_id != request.user.id:
            return Response(
                {
                    "detail": "Only the receiver can reject this request."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if connection_request.status != ConnectionRequest.Status.PENDING:
            return Response(
                {
                    "detail": "Only pending requests can be rejected."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        connection_request.mark_rejected()

        return Response(
            {
                "message": "Connection request rejected successfully."
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="cancel",
    )
    def cancel(self, request, pk=None):
        connection_request = self.get_object()

        if connection_request.from_user_id != request.user.id:
            return Response(
                {
                    "detail": "Only the sender can cancel this request."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if connection_request.status != ConnectionRequest.Status.PENDING:
            return Response(
                {
                    "detail": "Only pending requests can be cancelled."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        connection_request.mark_cancelled()

        return Response(
            {
                "message": "Connection request cancelled successfully."
            },
            status=status.HTTP_200_OK,
        )


class ConnectionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    serializer_class = ConnectionSerializer

    def get_queryset(self):
        return (
            Connection.objects.select_related(
                "user1",
                "user2",
                "user1__profile",
                "user2__profile",
            )
            .filter(
                Q(user1=self.request.user) | Q(user2=self.request.user)
            )
            .order_by("-created_at")
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="unfriend",
    )
    def unfriend(self, request, pk=None):
        connection = self.get_object()
        other_user = connection.get_other_user(request.user)

        connection.delete()

        return Response(
            {
                "message": f"You are no longer connected with {other_user.username}."
            },
            status=status.HTTP_200_OK,
        )
    
class UserBlockViewSet(
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    serializer_class = UserBlockSerializer

    def get_queryset(self):
        return (
            UserBlock.objects.select_related(
                "blocked",
                "blocked__profile",
            )
            .filter(blocker=self.request.user)
            .order_by("-created_at")
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="block",
    )
    def block(self, request):
        serializer = UserActionSerializer(
            data=request.data,
            context={
                "request": request,
            },
        )
        serializer.is_valid(raise_exception=True)

        target_user = serializer.validated_data["target_user"]
        reason = serializer.validated_data.get("reason", "")

        user_block, created = UserBlock.objects.get_or_create(
            blocker=request.user,
            blocked=target_user,
            defaults={
                "reason": reason,
            },
        )

        if not created and reason:
            user_block.reason = reason
            user_block.save(update_fields=["reason"])

        cleanup_after_block(
            blocker=request.user,
            blocked=target_user,
        )

        return Response(
            {
                "message": f"{target_user.username} has been blocked.",
                "block": UserBlockSerializer(
                    user_block,
                    context={
                        "request": request,
                    },
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="unblock",
    )
    def unblock(self, request):
        serializer = UserActionSerializer(
            data=request.data,
            context={
                "request": request,
            },
        )
        serializer.is_valid(raise_exception=True)

        target_user = serializer.validated_data["target_user"]

        deleted_count, deleted_data = UserBlock.objects.filter(
            blocker=request.user,
            blocked=target_user,
        ).delete()

        if deleted_count == 0:
            return Response(
                {
                    "detail": "This user is not blocked."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": f"{target_user.username} has been unblocked."
            },
            status=status.HTTP_200_OK,
        )


class UserRestrictionViewSet(
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    serializer_class = UserRestrictionSerializer

    def get_queryset(self):
        return (
            UserRestriction.objects.select_related(
                "restricted_user",
                "restricted_user__profile",
            )
            .filter(owner=self.request.user)
            .order_by("-created_at")
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="restrict",
    )
    def restrict(self, request):
        serializer = UserActionSerializer(
            data=request.data,
            context={
                "request": request,
            },
        )
        serializer.is_valid(raise_exception=True)

        target_user = serializer.validated_data["target_user"]

        restriction, created = UserRestriction.objects.get_or_create(
            owner=request.user,
            restricted_user=target_user,
        )

        return Response(
            {
                "message": f"{target_user.username} has been restricted.",
                "restriction": UserRestrictionSerializer(
                    restriction,
                    context={
                        "request": request,
                    },
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="unrestrict",
    )
    def unrestrict(self, request):
        serializer = UserActionSerializer(
            data=request.data,
            context={
                "request": request,
            },
        )
        serializer.is_valid(raise_exception=True)

        target_user = serializer.validated_data["target_user"]

        deleted_count, deleted_data = UserRestriction.objects.filter(
            owner=request.user,
            restricted_user=target_user,
        ).delete()

        if deleted_count == 0:
            return Response(
                {
                    "detail": "This user is not restricted."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": f"{target_user.username} has been unrestricted."
            },
            status=status.HTTP_200_OK,
        )