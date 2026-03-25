from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from .models import Group, GroupMembership, GroupInvite
from apps.users.serializers import UserPublicSerializer


class GroupMembershipSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)

    class Meta:
        model = GroupMembership
        fields = ["id", "user", "role", "is_active", "joined_at"]
        read_only_fields = ["id", "joined_at"]


class GroupSerializer(serializers.ModelSerializer):
    created_by = UserPublicSerializer(read_only=True)
    member_count = serializers.ReadOnlyField()
    is_member = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            "id", "name", "description", "avatar",
            "created_by", "member_count", "is_member",
            "user_role", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def get_is_member(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return GroupMembership.objects.filter(
            group=obj, user=request.user, is_active=True
        ).exists()

    def get_user_role(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        membership = GroupMembership.objects.filter(
            group=obj, user=request.user, is_active=True
        ).first()
        return membership.role if membership else None


class GroupCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["id", "name", "description", "avatar"]
        read_only_fields = ["id"]


class GroupInviteSerializer(serializers.ModelSerializer):
    invited_by = UserPublicSerializer(read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = GroupInvite
        fields = [
            "id", "group", "group_name", "invited_by",
            "invited_email", "status", "token", "expires_at", "created_at",
        ]
        read_only_fields = ["id", "token", "expires_at", "status", "invited_by"]

    def validate_invited_email(self, value):
        return value.lower().strip()


class GroupInviteCreateSerializer(serializers.Serializer):
    invited_email = serializers.EmailField()

    def validate_invited_email(self, value):
        return value.lower().strip()


class AcceptInviteSerializer(serializers.Serializer):
    token = serializers.UUIDField()
