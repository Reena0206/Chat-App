from django.contrib import admin

from apps.connections.models import (
    Connection,
    ConnectionRequest,
    UserBlock,
    UserRestriction,
)


@admin.register(ConnectionRequest)
class ConnectionRequestAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "from_user",
        "to_user",
        "status",
        "created_at",
        "responded_at",
    ]
    list_filter = [
        "status",
        "created_at",
        "responded_at",
    ]
    search_fields = [
        "from_user__email",
        "from_user__username",
        "to_user__email",
        "to_user__username",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "responded_at",
    ]


@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user1",
        "user2",
        "created_at",
    ]
    search_fields = [
        "user1__email",
        "user1__username",
        "user2__email",
        "user2__username",
    ]
    readonly_fields = [
        "created_at",
    ]


@admin.register(UserBlock)
class UserBlockAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "blocker",
        "blocked",
        "reason",
        "created_at",
    ]
    search_fields = [
        "blocker__email",
        "blocker__username",
        "blocked__email",
        "blocked__username",
        "reason",
    ]
    readonly_fields = [
        "created_at",
    ]


@admin.register(UserRestriction)
class UserRestrictionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "owner",
        "restricted_user",
        "created_at",
    ]
    search_fields = [
        "owner__email",
        "owner__username",
        "restricted_user__email",
        "restricted_user__username",
    ]
    readonly_fields = [
        "created_at",
    ]