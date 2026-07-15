from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.chats.api.serializers import (
    ChatRoomSerializer,
    ChatUserSerializer,
    CreateOneToOneRoomSerializer,
    MediaMessageCreateSerializer,
    MessageCreateSerializer,
    MessageReadSerializer,
)
from apps.chats.models import ChatRoom, ChatRoomParticipant, Message, MessageReadReceipt
from apps.chats.services import get_room_unread_count_for_user, get_total_unread_count_for_user
from apps.connections.services import are_users_blocked, get_blocked_user_ids
from apps.notifications.services import create_new_message_notifications


class ChatRoomViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    serializer_class = ChatRoomSerializer
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_queryset(self):
        blocked_user_ids = get_blocked_user_ids(self.request.user)

        queryset = (
            ChatRoom.objects.prefetch_related(
                "participants",
                "participants__user",
                "participants__user__profile",
                "participants__user__presence",
                "messages",
                "messages__sender",
                "messages__sender__profile",
                "messages__sender__presence",
                "messages__media_files",
                "messages__read_receipts",
            )
            .filter(
                participants__user=self.request.user,
                participants__is_active=True,
            )
            .distinct()
            .order_by("-last_message_at", "-created_at")
        )

        if blocked_user_ids:
            queryset = queryset.exclude(
                participants__user_id__in=blocked_user_ids,
            )

        return queryset

    def validate_room_access_for_message(self, request, room):
        participant_exists = ChatRoomParticipant.objects.filter(
            room=room,
            user=request.user,
            is_active=True,
        ).exists()

        if not participant_exists:
            return Response(
                {
                    "detail": "You are not a participant of this room."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        other_participants = (
            room.participants.exclude(user=request.user)
            .select_related("user")
        )

        for participant in other_participants:
            if are_users_blocked(request.user, participant.user):
                return Response(
                    {
                        "detail": "You cannot send messages in this chat."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        return None

    def broadcast_message(self, room_id, message_data):
        channel_layer = get_channel_layer()

        if not channel_layer:
            return

        async_to_sync(channel_layer.group_send)(
            f"chat_room_{room_id}",
            {
                "type": "chat_message_event",
                "message": message_data,
            },
        )

    def broadcast_chat_room_update(self, room):
        channel_layer = get_channel_layer()

        if not channel_layer:
            return

        participant_ids = list(
            room.participants.filter(is_active=True).values_list(
                "user_id",
                flat=True,
            )
        )

        for user_id in participant_ids:
            async_to_sync(channel_layer.group_send)(
                f"chat_updates_user_{user_id}",
                {
                    "type": "chat_room_event",
                    "room_id": room.id,
                    "unread_count": get_room_unread_count_for_user(
                        room_id=room.id,
                        user_id=user_id,
                    ),
                    "total_unread_count": get_total_unread_count_for_user(
                        user_id=user_id,
                    ),
                },
            )

    def broadcast_read_receipt(self, room_id, request):
        channel_layer = get_channel_layer()

        if not channel_layer:
            return

        user_data = ChatUserSerializer(
            request.user,
            context={
                "request": request,
            },
        ).data

        async_to_sync(channel_layer.group_send)(
            f"chat_room_{room_id}",
            {
                "type": "read_receipt_event",
                "user": user_data,
                "room_id": room_id,
                "read_at": timezone.now().isoformat(),
            },
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="one-to-one",
    )
    def one_to_one(self, request):
        serializer = CreateOneToOneRoomSerializer(
            data=request.data,
            context={
                "request": request,
            },
        )
        serializer.is_valid(raise_exception=True)

        room = serializer.save()

        output_serializer = ChatRoomSerializer(
            room,
            context={
                "request": request,
            },
        )

        return Response(
            {
                "message": "Chat room is ready.",
                "room": output_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="messages",
    )
    def messages(self, request, pk=None):
        room = self.get_object()

        messages = (
            Message.objects.select_related(
                "sender",
                "sender__profile",
                "sender__presence",
                "reply_to",
            )
            .prefetch_related(
                "media_files",
                "read_receipts",
                "read_receipts__user",
                "read_receipts__user__profile",
                "read_receipts__user__presence",
            )
            .filter(
                room=room,
                is_deleted=False,
            )
            .order_by("created_at")
        )

        page = self.paginate_queryset(messages)

        if page is not None:
            serializer = MessageReadSerializer(
                page,
                many=True,
                context={
                    "request": request,
                },
            )
            return self.get_paginated_response(serializer.data)

        serializer = MessageReadSerializer(
            messages,
            many=True,
            context={
                "request": request,
            },
        )

        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        url_path="messages/send",
    )
    def send_message(self, request, pk=None):
        room = self.get_object()

        access_error = self.validate_room_access_for_message(
            request=request,
            room=room,
        )

        if access_error:
            return access_error

        serializer = MessageCreateSerializer(
            data=request.data,
            context={
                "request": request,
                "room": room,
            },
        )
        serializer.is_valid(raise_exception=True)

        message = serializer.save()

        message = (
            Message.objects.select_related(
                "sender",
                "sender__profile",
                "sender__presence",
                "reply_to",
            )
            .prefetch_related(
                "media_files",
                "read_receipts",
                "read_receipts__user",
                "read_receipts__user__profile",
                "read_receipts__user__presence",
            )
            .get(id=message.id)
        )

        output_serializer = MessageReadSerializer(
            message,
            context={
                "request": request,
            },
        )

        self.broadcast_chat_room_update(room)
        create_new_message_notifications(
            actor=request.user,
            room=room,
            message=message,
        )

        self.broadcast_message(
            room_id=room.id,
            message_data=output_serializer.data,
        )

        return Response(
            {
                "message": "Message sent successfully.",
                "data": output_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="messages/media",
    )
    def send_media_message(self, request, pk=None):
        room = self.get_object()

        access_error = self.validate_room_access_for_message(
            request=request,
            room=room,
        )

        if access_error:
            return access_error

        serializer = MediaMessageCreateSerializer(
            data=request.data,
            context={
                "request": request,
                "room": room,
            },
        )
        serializer.is_valid(raise_exception=True)

        message = serializer.save()

        message = (
            Message.objects.select_related(
                "sender",
                "sender__profile",
                "sender__presence",
                "reply_to",
            )
            .prefetch_related(
                "media_files",
                "read_receipts",
                "read_receipts__user",
                "read_receipts__user__profile",
                "read_receipts__user__presence",
            )
            .get(id=message.id)
        )

        output_serializer = MessageReadSerializer(
            message,
            context={
                "request": request,
            },
        )

        self.broadcast_chat_room_update(room)
        create_new_message_notifications(
            actor=request.user,
            room=room,
            message=message,
        )

        self.broadcast_message(
            room_id=room.id,
            message_data=output_serializer.data,
        )

        return Response(
            {
                "message": "Media message sent successfully.",
                "data": output_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="messages/mark-read",
    )
    def mark_messages_read(self, request, pk=None):
        room = self.get_object()

        profile = getattr(request.user, "profile", None)

        if profile and not profile.read_receipts_enabled:
            ChatRoomParticipant.objects.filter(
                room=room,
                user=request.user,
            ).update(
                last_seen_at=timezone.now(),
            )

            return Response(
                {
                    "message": "Messages marked as read privately."
                },
                status=status.HTTP_200_OK,
            )

        messages = Message.objects.filter(
            room=room,
            is_deleted=False,
        ).exclude(
            sender=request.user,
        )

        receipts = [
            MessageReadReceipt(
                message=message,
                user=request.user,
            )
            for message in messages
        ]

        MessageReadReceipt.objects.bulk_create(
            receipts,
            ignore_conflicts=True,
        )

        ChatRoomParticipant.objects.filter(
            room=room,
            user=request.user,
        ).update(
            last_seen_at=timezone.now(),
        )

        self.broadcast_read_receipt(
            room_id=room.id,
            request=request,
        )

        return Response(
            {
                "message": "Messages marked as read."
            },
            status=status.HTTP_200_OK,
        )

