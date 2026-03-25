from django.contrib import admin
from .models import Group, GroupMembership, GroupInvite


class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 0
    readonly_fields = ["joined_at"]
    fields = ["user", "role", "is_active", "joined_at"]


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["name", "created_by", "member_count", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "description"]
    inlines = [GroupMembershipInline]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "group", "role", "is_active", "joined_at"]
    list_filter = ["role", "is_active"]
    search_fields = ["user__email", "group__name"]


@admin.register(GroupInvite)
class GroupInviteAdmin(admin.ModelAdmin):
    list_display = ["invited_email", "group", "invited_by", "status", "expires_at"]
    list_filter = ["status"]
    search_fields = ["invited_email", "group__name"]
    readonly_fields = ["token", "created_at"]
