from django.contrib import admin

from apps.profiles.models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "account_visibility",
        "created_at",
        "updated_at",
    ]
    list_filter = [
        "account_visibility",
        "created_at",
        "updated_at",
    ]
    search_fields = [
        "user__email",
        "user__username",
        "user__name",
        "bio",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]