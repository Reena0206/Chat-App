from django.contrib import admin

from apps.chats.models import (
    ChatRoom,
    ChatRoomParticipant,
    Message,
    MessageMedia,
    MessageReadReceipt,
    UserChannelSession,
    UserPresence,
)


class ChatRoomParticipantInline(admin.TabularInline):
    model = ChatRoomParticipant
    extra = 0
    readonly_fields = [
        "joined_at",
        "last_seen_at",
    ]


class MessageMediaInline(admin.TabularInline):
    model = MessageMedia
    extra = 0
    readonly_fields = [
        "created_at",
    ]


class MessageReadReceiptInline(admin.TabularInline):
    model = MessageReadReceipt
    extra = 0
    readonly_fields = [
        "read_at",
    ]


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "room_type",
        "room_key",
        "created_by",
        "last_message_at",
        "created_at",
    ]
    list_filter = [
        "room_type",
        "created_at",
        "last_message_at",
    ]
    search_fields = [
        "room_key",
        "created_by__email",
        "created_by__username",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "last_message_at",
    ]
    inlines = [
        ChatRoomParticipantInline,
    ]


@admin.register(ChatRoomParticipant)
class ChatRoomParticipantAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "room",
        "user",
        "is_active",
        "joined_at",
        "last_seen_at",
    ]
    list_filter = [
        "is_active",
        "joined_at",
    ]
    search_fields = [
        "room__room_key",
        "user__email",
        "user__username",
    ]
    readonly_fields = [
        "joined_at",
    ]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "room",
        "sender",
        "message_type",
        "short_text",
        "is_edited",
        "is_deleted",
        "created_at",
    ]
    list_filter = [
        "message_type",
        "is_edited",
        "is_deleted",
        "created_at",
    ]
    search_fields = [
        "text",
        "sender__email",
        "sender__username",
        "room__room_key",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]
    inlines = [
        MessageMediaInline,
        MessageReadReceiptInline,
    ]

    def short_text(self, obj):
        if not obj.text:
            return "-"

        return obj.text[:50]


@admin.register(MessageMedia)
class MessageMediaAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "message",
        "media_type",
        "original_name",
        "file_size",
        "duration_seconds",
        "created_at",
    ]
    list_filter = [
        "media_type",
        "created_at",
    ]
    search_fields = [
        "original_name",
        "message__text",
    ]
    readonly_fields = [
        "created_at",
    ]


@admin.register(MessageReadReceipt)
class MessageReadReceiptAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "message",
        "user",
        "read_at",
    ]
    search_fields = [
        "message__text",
        "user__email",
        "user__username",
    ]
    readonly_fields = [
        "read_at",
    ]


@admin.register(UserPresence)
class UserPresenceAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "is_online",
        "last_seen_at",
        "updated_at",
    ]
    list_filter = [
        "is_online",
        "last_seen_at",
    ]
    search_fields = [
        "user__email",
        "user__username",
        "user__name",
    ]
    readonly_fields = [
        "updated_at",
    ]


@admin.register(UserChannelSession)
class UserChannelSessionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "room",
        "channel_name",
        "connected_at",
        "last_seen_at",
    ]
    search_fields = [
        "user__email",
        "user__username",
        "room__room_key",
        "channel_name",
    ]
    readonly_fields = [
        "connected_at",
        "last_seen_at",
    ]