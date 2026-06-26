from django.db.models import Q

from apps.connections.models import Connection, ConnectionRequest, UserBlock, UserRestriction


def has_blocked(*, blocker, blocked):
    return UserBlock.objects.filter(
        blocker=blocker,
        blocked=blocked,
    ).exists()


def are_users_blocked(user_a, user_b):
    if not user_a or not user_b:
        return False

    if user_a.id == user_b.id:
        return False

    return UserBlock.objects.filter(
        Q(blocker=user_a, blocked=user_b) | Q(blocker=user_b, blocked=user_a)
    ).exists()


def get_blocked_user_ids(user):
    blocked_ids = UserBlock.objects.filter(
        blocker=user,
    ).values_list("blocked_id", flat=True)

    blocked_by_ids = UserBlock.objects.filter(
        blocked=user,
    ).values_list("blocker_id", flat=True)

    return list(set(list(blocked_ids) + list(blocked_by_ids)))


def restricts_user(*, owner, restricted_user):
    return UserRestriction.objects.filter(
        owner=owner,
        restricted_user=restricted_user,
    ).exists()


def remove_connection_between(user_a, user_b):
    try:
        connection = Connection.get_connection_between(user_a, user_b)
    except Exception:
        connection = None

    if connection:
        connection.delete()


def cancel_pending_requests_between(user_a, user_b):
    ConnectionRequest.objects.filter(
        Q(from_user=user_a, to_user=user_b) | Q(from_user=user_b, to_user=user_a),
        status=ConnectionRequest.Status.PENDING,
    ).update(
        status=ConnectionRequest.Status.CANCELLED,
    )


def cleanup_after_block(*, blocker, blocked):
    remove_connection_between(blocker, blocked)
    cancel_pending_requests_between(blocker, blocked)