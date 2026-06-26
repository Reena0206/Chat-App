from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.notifications.models import Notification


def broadcast_notification(notification):
    channel_layer = get_channel_layer()

    if not channel_layer:
        return

    from apps.notifications.api.serializers import NotificationReadSerializer

    data = NotificationReadSerializer(notification).data

    async_to_sync(channel_layer.group_send)(
        f"notifications_user_{notification.recipient_id}",
        {
            "type": "notification_event",
            "notification": data,
        },
    )


def create_notification(
    *,
    recipient,
    notification_type,
    title,
    body="",
    actor=None,
    chat_room=None,
    message=None,
    connection_request=None,
):
    if actor and actor.id == recipient.id:
        return None

    notification = Notification.objects.create(
        recipient=recipient,
        actor=actor,
        notification_type=notification_type,
        title=title,
        body=body,
        chat_room=chat_room,
        message=message,
        connection_request=connection_request,
    )

    broadcast_notification(notification)

    return notification


def create_connection_request_notification(*, from_user, to_user, connection_request):
    return create_notification(
        recipient=to_user,
        actor=from_user,
        notification_type=Notification.NotificationType.CONNECTION_REQUEST,
        title="New connection request",
        body=f"{from_user.username} sent you a connection request.",
        connection_request=connection_request,
    )


def create_connection_accepted_notification(*, accepted_by, request_sender, connection_request):
    return create_notification(
        recipient=request_sender,
        actor=accepted_by,
        notification_type=Notification.NotificationType.CONNECTION_ACCEPTED,
        title="Connection request accepted",
        body=f"{accepted_by.username} accepted your connection request.",
        connection_request=connection_request,
    )


def create_new_message_notifications(*, actor, room, message):
    participants = (
        room.participants.select_related("user")
        .filter(is_active=True)
        .exclude(user=actor)
    )

    notifications = []

    for participant in participants:
        media_label = ""

        if message.message_type == "media":
            first_media = message.media_files.first()

            if first_media:
                media_label = f" sent you a {first_media.media_type} message."
            else:
                media_label = " sent you a media message."
        else:
            media_label = " sent you a message."

        body = message.text.strip() if message.text else f"{actor.username}{media_label}"

        if len(body) > 120:
            body = body[:117] + "..."

        notification = create_notification(
            recipient=participant.user,
            actor=actor,
            notification_type=Notification.NotificationType.NEW_MESSAGE,
            title="New message",
            body=body,
            chat_room=room,
            message=message,
        )

        if notification:
            notifications.append(notification)

    return notifications