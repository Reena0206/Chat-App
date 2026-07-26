import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from apps.chats.api.serializers import MessageReadSerializer
from apps.chats.models import (
    ChatRoom,
    ChatRoomParticipant,
    Message,
    MessageReadReceipt,
    UserChannelSession,
    UserPresence,
)
from apps.connections.models import Connection
from apps.connections.services import are_users_blocked, restricts_user
from apps.notifications.services import create_new_message_notifications
from apps.profiles.models import Profile
from apps.chats.services import (
    get_room_unread_count_for_user,
    get_total_unread_count_for_user,
)

User = get_user_model()


class ChatRoomConsumer(AsyncJsonWebsocketConsumer):
    @classmethod
    async def encode_json(cls, content):
        return json.dumps(content, cls=DjangoJSONEncoder)

    async def connect(self):
        self.user = self.scope["user"]
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.room_group_name = f"chat_room_{self.room_id}"

        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        is_participant = await self.is_room_participant(
            room_id=self.room_id,
            user_id=self.user.id,
        )

        if not is_participant:
            await self.close(code=4003)
            return

        is_blocked = await self.room_has_blocked_participant()

        if is_blocked:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()

        await self.mark_user_online()
        await self.create_channel_session()

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "presence_event",
                "event": "user_online",
                "user": await self.get_user_payload(),
            },
        )

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            try:
                await self.channel_layer.group_discard(
                    self.room_group_name,
                    self.channel_name,
                )
            except Exception:
                pass

        if hasattr(self, "user") and self.user.is_authenticated:
            try:
                await self.delete_channel_session()
                is_still_online = await self.user_has_active_sessions()

                if not is_still_online:
                    await self.mark_user_offline()

                    if hasattr(self, "room_group_name"):
                        await self.channel_layer.group_send(
                            self.room_group_name,
                            {
                                "type": "presence_event",
                                "event": "user_offline",
                                "user": await self.get_user_payload(),
                            },
                        )
            except Exception:
                pass

    async def receive_json(self, content, **kwargs):
        event_type = content.get("type")

        if event_type == "message.send":
            await self.handle_message_send(content)
            return

        if event_type == "typing.start":
            await self.handle_typing(is_typing=True)
            return

        if event_type == "typing.stop":
            await self.handle_typing(is_typing=False)
            return

        if event_type == "message.read":
            await self.handle_message_read()
            return

        await self.send_json(
            {
                "type": "error",
                "detail": "Invalid WebSocket event type.",
            }
        )

    async def handle_message_send(self, content):
        is_blocked = await self.room_has_blocked_participant()

        if is_blocked:
            await self.send_json(
                {
                    "type": "error",
                    "detail": "You cannot send messages in this chat.",
                }
            )
            return

        text = content.get("text", "")
        reply_to_id = content.get("reply_to")

        if not isinstance(text, str) or not text.strip():
            await self.send_json(
                {
                    "type": "error",
                    "detail": "Message text is required.",
                }
            )
            return

        if len(text.strip()) > 5000:
            await self.send_json(
                {
                    "type": "error",
                    "detail": "Message cannot exceed 5000 characters.",
                }
            )
            return

        try:
            message_data = await self.create_message(
                room_id=self.room_id,
                user_id=self.user.id,
                text=text.strip(),
                reply_to_id=reply_to_id,
            )
            await self.create_message_notifications(message_data["id"])
            await self.broadcast_chat_room_update()
        except ValueError as error:
            await self.send_json(
                {
                    "type": "error",
                    "detail": str(error),
                }
            )
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message_event",
                "message": message_data,
            },
        )

    async def handle_typing(self, is_typing):
        is_blocked = await self.room_has_blocked_participant()

        if is_blocked:
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "typing_event",
                "user": await self.get_user_payload(),
                "is_typing": is_typing,
            },
        )

    async def handle_message_read(self):
        can_send_receipt = await self.user_allows_read_receipts()

        if not can_send_receipt:
            await self.update_participant_last_seen()

            await self.send_json(
                {
                    "type": "messages.read_private",
                    "detail": "Messages marked as read privately.",
                }
            )
            return

        await self.mark_messages_as_read()

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "read_receipt_event",
                "user": await self.get_user_payload(),
                "room_id": int(self.room_id),
                "read_at": timezone.now().isoformat(),
            },
        )

    async def chat_message_event(self, event):
        await self.send_json(
            {
                "type": "message.new",
                "message": event["message"],
            }
        )

    async def typing_event(self, event):
        user = event["user"]

        if user["id"] == self.user.id:
            return

        await self.send_json(
            {
                "type": "typing",
                "user": user,
                "is_typing": event["is_typing"],
            }
        )

    async def presence_event(self, event):
        user = event["user"]

        if user["id"] == self.user.id:
            return

        can_view = await self.can_view_user_presence(user["id"])

        if not can_view:
            return

        await self.send_json(
            {
                "type": event["event"],
                "user": user,
            }
        )

    async def read_receipt_event(self, event):
        read_at = event["read_at"]

        if hasattr(read_at, "isoformat"):
            read_at = read_at.isoformat()

        await self.send_json(
            {
                "type": "messages.read",
                "user": event["user"],
                "room_id": event["room_id"],
                "read_at": read_at,
            }
        )

    @database_sync_to_async
    def is_room_participant(self, room_id, user_id):
        return ChatRoomParticipant.objects.filter(
            room_id=room_id,
            user_id=user_id,
            is_active=True,
        ).exists()

    @database_sync_to_async
    def room_has_blocked_participant(self):
        room = (
            ChatRoom.objects.prefetch_related(
                "participants",
                "participants__user",
            )
            .filter(id=self.room_id)
            .first()
        )

        if not room:
            return True

        other_users = [
            participant.user
            for participant in room.participants.all()
            if participant.user_id != self.user.id and participant.is_active
        ]

        for other_user in other_users:
            if are_users_blocked(self.user, other_user):
                return True

        return False

    @database_sync_to_async
    def create_message(self, room_id, user_id, text, reply_to_id=None):
        room = ChatRoom.objects.get(id=room_id)

        reply_to = None

        if reply_to_id:
            reply_to = Message.objects.filter(
                id=reply_to_id,
                room=room,
                is_deleted=False,
            ).first()

            if not reply_to:
                raise ValueError("Reply message not found in this room.")

        message = Message.objects.create(
            room=room,
            sender_id=user_id,
            message_type=Message.MessageType.TEXT,
            text=text,
            reply_to=reply_to,
        )

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

        return MessageReadSerializer(message).data

    @database_sync_to_async
    def mark_messages_as_read(self):
        messages = Message.objects.filter(
            room_id=self.room_id,
            is_deleted=False,
        ).exclude(
            sender_id=self.user.id,
        ).exclude(
            read_receipts__user=self.user,
        )

        receipts = [
            MessageReadReceipt(
                message=message,
                user=self.user,
            )
            for message in messages
        ]

        if receipts:
            MessageReadReceipt.objects.bulk_create(
                receipts,
                ignore_conflicts=True,
            )

        ChatRoomParticipant.objects.filter(
            room_id=self.room_id,
            user=self.user,
        ).update(
            last_seen_at=timezone.now(),
        )

    @database_sync_to_async
    def user_allows_read_receipts(self):
        profile = getattr(self.user, "profile", None)

        if not profile:
            return True

        return profile.read_receipts_enabled

    @database_sync_to_async
    def update_participant_last_seen(self):
        ChatRoomParticipant.objects.filter(
            room_id=self.room_id,
            user=self.user,
        ).update(
            last_seen_at=timezone.now(),
        )

    @database_sync_to_async
    def can_view_user_presence(self, target_user_id):
        target_user = (
            User.objects.select_related("profile")
            .filter(id=target_user_id, is_active=True)
            .first()
        )

        if not target_user:
            return False

        if are_users_blocked(self.user, target_user):
            return False

        if restricts_user(owner=target_user, restricted_user=self.user):
            return False

        profile = getattr(target_user, "profile", None)

        if not profile:
            return False

        if profile.last_seen_visibility == Profile.LastSeenVisibility.NOBODY:
            return False

        if profile.last_seen_visibility == Profile.LastSeenVisibility.CONNECTIONS:
            return Connection.are_connected(self.user, target_user)

        return True

    @database_sync_to_async
    def mark_user_online(self):
        UserPresence.objects.update_or_create(
            user=self.user,
            defaults={
                "is_online": True,
                "last_seen_at": timezone.now(),
            },
        )

    @database_sync_to_async
    def mark_user_offline(self):
        UserPresence.objects.update_or_create(
            user=self.user,
            defaults={
                "is_online": False,
                "last_seen_at": timezone.now(),
            },
        )

    @database_sync_to_async
    def create_channel_session(self):
        UserChannelSession.objects.update_or_create(
            channel_name=self.channel_name,
            defaults={
                "user": self.user,
                "room_id": self.room_id,
            },
        )

    @database_sync_to_async
    def delete_channel_session(self):
        UserChannelSession.objects.filter(
            channel_name=self.channel_name,
        ).delete()

    @database_sync_to_async
    def user_has_active_sessions(self):
        return UserChannelSession.objects.filter(
            user=self.user,
        ).exists()

    @database_sync_to_async
    def create_message_notifications(self, message_id):
        message = (
            Message.objects.select_related("room", "sender")
            .prefetch_related("media_files")
            .get(id=message_id)
        )

        create_new_message_notifications(
            actor=message.sender,
            room=message.room,
            message=message,
        )

    @database_sync_to_async
    def get_user_payload(self):
        profile = getattr(self.user, "profile", None)

        profile_picture_url = None

        if profile and profile.profile_picture:
            profile_picture_url = profile.profile_picture.url

        return {
            "id": self.user.id,
            "username": self.user.username,
            "name": self.user.name,
            "profile_picture_url": profile_picture_url,
        }


    async def broadcast_chat_room_update(self):
        participant_ids = await self.get_room_participant_ids()

        for user_id in participant_ids:
            unread_count = await self.get_room_unread_count(
                room_id=self.room_id,
                user_id=user_id,
            )
            total_unread_count = await self.get_total_unread_count(
                user_id=user_id,
            )

            await self.channel_layer.group_send(
                f"chat_updates_user_{user_id}",
                {
                    "type": "chat_room_event",
                    "room_id": int(self.room_id),
                    "unread_count": unread_count,
                    "total_unread_count": total_unread_count,
                },
            )

    @database_sync_to_async
    def get_room_participant_ids(self):
        return list(
            ChatRoomParticipant.objects.filter(
                room_id=self.room_id,
                is_active=True,
            ).values_list("user_id", flat=True)
        )

    @database_sync_to_async
    def get_room_unread_count(self, room_id, user_id):
        return get_room_unread_count_for_user(
            room_id=room_id,
            user_id=user_id,
        )

    @database_sync_to_async
    def get_total_unread_count(self, user_id):
        return get_total_unread_count_for_user(
            user_id=user_id,
        )


class ChatUpdatesConsumer(AsyncJsonWebsocketConsumer):
    @classmethod
    async def encode_json(cls, content):
        return json.dumps(content, cls=DjangoJSONEncoder)

    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = f"chat_updates_user_{self.user.id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        await self.accept()

        await self.send_json(
            {
                "type": "chat.updates.connected",
                "total_unread_count": await self.get_total_unread_count(),
            }
        )

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

    async def receive_json(self, content, **kwargs):
        return

    async def chat_room_event(self, event):
        await self.send_json(
            {
                "type": "chat.room.updated",
                "room_id": event["room_id"],
                "unread_count": event.get("unread_count", 0),
                "total_unread_count": event.get("total_unread_count", 0),
            }
        )

    @database_sync_to_async
    def get_total_unread_count(self):
        return get_total_unread_count_for_user(
            user_id=self.user.id,
        )
