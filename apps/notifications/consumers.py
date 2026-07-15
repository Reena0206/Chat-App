from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

from apps.notifications.api.serializers import NotificationReadSerializer
from apps.notifications.models import Notification


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = f"notifications_user_{self.user.id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        await self.accept()

        await self.send_json(
            {
                "type": "notifications.connected",
                "unread_count": await self.get_unread_count(),
            }
        )

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

    async def receive_json(self, content, **kwargs):
        event_type = content.get("type")

        if event_type == "notifications.mark_read":
            notification_id = content.get("notification_id")
            data = await self.mark_notification_read(notification_id)

            await self.send_json(data)
            return

        if event_type == "notifications.mark_all_read":
            data = await self.mark_all_read()
            await self.send_json(data)
            return

        await self.send_json(
            {
                "type": "error",
                "detail": "Invalid notification event type.",
            }
        )

    async def notification_event(self, event):
        await self.send_json(
            {
                "type": "notification.new",
                "notification": event["notification"],
            }
        )

    @database_sync_to_async
    def get_unread_count(self):
        return Notification.objects.filter(
            recipient=self.user,
            is_read=False,
        ).exclude(
            notification_type=Notification.NotificationType.NEW_MESSAGE,
        ).count()

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        notification = Notification.objects.filter(
            id=notification_id,
            recipient=self.user,
        ).exclude(
            notification_type=Notification.NotificationType.NEW_MESSAGE,
        ).first()

        if not notification:
            return {
                "type": "error",
                "detail": "Notification not found.",
            }

        notification.mark_as_read()

        return {
            "type": "notification.read",
            "notification": NotificationReadSerializer(notification).data,
            "unread_count": Notification.objects.filter(
                recipient=self.user,
                is_read=False,
            ).exclude(
                notification_type=Notification.NotificationType.NEW_MESSAGE,
            ).count(),
        }

    @database_sync_to_async
    def mark_all_read(self):
        updated_count = Notification.objects.filter(
            recipient=self.user,
            is_read=False,
        ).exclude(
            notification_type=Notification.NotificationType.NEW_MESSAGE,
        ).update(
            is_read=True,
            read_at=timezone.now(),
        )

        return {
            "type": "notifications.all_read",
            "updated_count": updated_count,
            "unread_count": 0,
        }
