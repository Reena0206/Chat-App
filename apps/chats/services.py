from apps.chats.models import ChatRoomParticipant, Message


def get_room_unread_count_for_user(*, room_id, user_id):
    participant = (
        ChatRoomParticipant.objects.filter(
            room_id=room_id,
            user_id=user_id,
            is_active=True,
        )
        .only("last_seen_at", "joined_at")
        .first()
    )

    if not participant:
        return 0

    seen_at = participant.last_seen_at or participant.joined_at

    queryset = Message.objects.filter(
        room_id=room_id,
        is_deleted=False,
    ).exclude(
        sender_id=user_id,
    )

    if seen_at:
        queryset = queryset.filter(created_at__gt=seen_at)

    return queryset.count()


def get_total_unread_count_for_user(*, user_id):
    participants = ChatRoomParticipant.objects.filter(
        user_id=user_id,
        is_active=True,
    ).only("room_id", "last_seen_at", "joined_at")

    total_unread = 0
    for participant in participants:
        seen_at = participant.last_seen_at or participant.joined_at
        queryset = Message.objects.filter(
            room_id=participant.room_id,
            is_deleted=False,
        ).exclude(
            sender_id=user_id,
        )
        if seen_at:
            queryset = queryset.filter(created_at__gt=seen_at)
        total_unread += queryset.count()

    return total_unread
