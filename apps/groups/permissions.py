from rest_framework.permissions import BasePermission
from .models import GroupMembership


class IsGroupMember(BasePermission):
    """Allow access only to active members of the group."""

    message = "You are not a member of this group."

    def has_object_permission(self, request, view, obj):
        # obj can be a Group or any model with a .group FK
        group = getattr(obj, "group", obj)
        return GroupMembership.objects.filter(
            group=group, user=request.user, is_active=True
        ).exists()


class IsGroupAdmin(BasePermission):
    """Allow access only to admins of the group."""

    message = "You must be a group admin to perform this action."

    def has_object_permission(self, request, view, obj):
        group = getattr(obj, "group", obj)
        return GroupMembership.objects.filter(
            group=group,
            user=request.user,
            role=GroupMembership.Role.ADMIN,
            is_active=True,
        ).exists()


class IsGroupMemberByGroupId(BasePermission):
    """Check membership by group_pk kwarg (used in nested routes)."""

    message = "You are not a member of this group."

    def has_permission(self, request, view):
        group_pk = view.kwargs.get("group_pk")
        if not group_pk:
            return True  # let the view handle non-nested routes
        return GroupMembership.objects.filter(
            group_id=group_pk, user=request.user, is_active=True
        ).exists()
