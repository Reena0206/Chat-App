from django.contrib import admin

from apps.notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "recipient",
        "actor",
        "notification_type",
        "title",
        "is_read",
        "created_at",
        "read_at",
    ]
    list_filter = [
        "notification_type",
        "is_read",
        "created_at",
        "read_at",
    ]
    search_fields = [
        "recipient__email",
        "recipient__username",
        "actor__email",
        "actor__username",
        "title",
        "body",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "read_at",
    ]