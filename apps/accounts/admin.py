from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.forms import CustomUserChangeForm, CustomUserCreationForm
from apps.accounts.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = [
        "id",
        "email",
        "username",
        "name",
        "is_active",
        "is_staff",
        "date_joined",
    ]
    list_filter = [
        "is_active",
        "is_staff",
        "is_superuser",
        "date_joined",
    ]
    search_fields = [
        "email",
        "username",
        "name",
    ]
    ordering = ["-date_joined"]

    fieldsets = [
        (
            "Login Information",
            {
                "fields": [
                    "email",
                    "username",
                    "password",
                ]
            },
        ),
        (
            "Personal Information",
            {
                "fields": [
                    "name",
                ]
            },
        ),
        (
            "Permissions",
            {
                "fields": [
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ]
            },
        ),
        (
            "Important Dates",
            {
                "fields": [
                    "last_login",
                    "date_joined",
                ]
            },
        ),
    ]

    add_fieldsets = [
        (
            "Create User",
            {
                "classes": ["wide"],
                "fields": [
                    "email",
                    "username",
                    "name",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ],
            },
        ),
    ]

    readonly_fields = [
        "last_login",
        "date_joined",
    ]