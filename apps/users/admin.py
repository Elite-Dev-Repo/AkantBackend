from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, AccountDetails


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["email", "username", "full_name", "is_active", "is_staff", "date_joined"]
    list_filter = ["is_active", "is_staff", "date_joined"]
    search_fields = ["email", "username", "first_name", "last_name"]
    ordering = ["-date_joined"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("username", "first_name", "last_name", "phone", "avatar")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "first_name", "last_name", "password1", "password2"),
        }),
    )
    readonly_fields = ["date_joined", "last_login"]


admin.site.register(AccountDetails)