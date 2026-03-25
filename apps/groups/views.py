from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.shortcuts import get_object_or_404

from .models import Group, GroupMembership, GroupInvite
from .serializers import (
    GroupSerializer,
    GroupCreateSerializer,
    GroupMembershipSerializer,
    GroupInviteSerializer,
    GroupInviteCreateSerializer,
    AcceptInviteSerializer,
)
from .services import GroupService
from .filters import GroupFilter
from .permissions import IsGroupMember, IsGroupAdmin


@extend_schema_view(
    list=extend_schema(tags=["groups"], summary="List my groups"),
    create=extend_schema(tags=["groups"], summary="Create a group"),
    retrieve=extend_schema(tags=["groups"], summary="Get group detail"),
    update=extend_schema(tags=["groups"], summary="Update group"),
    partial_update=extend_schema(tags=["groups"], summary="Partial update group"),
    destroy=extend_schema(tags=["groups"], summary="Deactivate group"),
)
class GroupViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = GroupFilter
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return GroupService.get_user_groups(self.request.user).prefetch_related(
            "memberships__user"
        )

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return GroupCreateSerializer
        return GroupSerializer

    def perform_create(self, serializer):
        data = serializer.validated_data
        group = GroupService.create_group(
            name=data["name"],
            description=data.get("description", ""),
            created_by=self.request.user,
            avatar=data.get("avatar"),
        )
        self._created_group = group

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        out = GroupSerializer(self._created_group, context={"request": request})
        return Response(
            {"success": True, "message": "Group created.", "data": out.data},
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        group = self.get_object()
        self._check_membership(group)
        serializer = GroupSerializer(group, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def update(self, request, *args, **kwargs):
        group = self.get_object()
        self._assert_admin(group)
        partial = kwargs.pop("partial", False)
        serializer = GroupCreateSerializer(group, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        out = GroupSerializer(group, context={"request": request})
        return Response({"success": True, "message": "Group updated.", "data": out.data})

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        group = self.get_object()
        self._assert_admin(group)
        group.is_active = False
        group.save(update_fields=["is_active"])
        return Response({"success": True, "message": "Group deactivated."}, status=status.HTTP_200_OK)

    # ── Members ───────────────────────────────────────────────────────────────

    @extend_schema(tags=["groups"], summary="List group members")
    @action(detail=True, methods=["get"], url_path="members")
    def members(self, request, pk=None):
        group = self.get_object()
        self._check_membership(group)
        memberships = GroupService.get_active_members(group)
        serializer = GroupMembershipSerializer(memberships, many=True)
        return Response({"success": True, "data": serializer.data})

    @extend_schema(tags=["groups"], summary="Remove a member (or leave)")
    @action(detail=True, methods=["delete"], url_path="members/(?P<user_pk>[^/.]+)")
    def remove_member(self, request, pk=None, user_pk=None):
        from apps.users.models import User
        group = self.get_object()
        user_to_remove = get_object_or_404(User, pk=user_pk)
        try:
            GroupService.remove_member(group, user_to_remove, request.user)
        except (ValueError, PermissionError) as e:
            return Response({"success": False, "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"success": True, "message": "Member removed."})

    @extend_schema(tags=["groups"], summary="Promote member to admin")
    @action(detail=True, methods=["post"], url_path="members/(?P<user_pk>[^/.]+)/promote")
    def promote_member(self, request, pk=None, user_pk=None):
        from apps.users.models import User
        group = self.get_object()
        user = get_object_or_404(User, pk=user_pk)
        try:
            GroupService.promote_to_admin(group, user, request.user)
        except (ValueError, PermissionError) as e:
            return Response({"success": False, "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"success": True, "message": f"{user.full_name} promoted to admin."})

    # ── Invites ───────────────────────────────────────────────────────────────

    @extend_schema(tags=["groups"], summary="Send group invite")
    @action(detail=True, methods=["post"], url_path="invites")
    def send_invite(self, request, pk=None):
        group = self.get_object()
        self._check_membership(group)
        serializer = GroupInviteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invite = GroupService.invite_member(
                group, request.user, serializer.validated_data["invited_email"]
            )
        except ValueError as e:
            return Response({"success": False, "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        out = GroupInviteSerializer(invite, context={"request": request})
        return Response(
            {"success": True, "message": "Invite sent.", "data": out.data},
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(tags=["groups"], summary="List group invites")
    @action(detail=True, methods=["get"], url_path="invites/list")
    def list_invites(self, request, pk=None):
        group = self.get_object()
        self._check_membership(group)
        invites = GroupInvite.objects.filter(group=group).order_by("-created_at")
        serializer = GroupInviteSerializer(invites, many=True)
        return Response({"success": True, "data": serializer.data})

    @extend_schema(tags=["groups"], summary="Accept invite by token")
    @action(detail=False, methods=["post"], url_path="invites/accept", permission_classes=[permissions.IsAuthenticated])
    def accept_invite(self, request):
        serializer = AcceptInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            membership = GroupService.accept_invite(
                str(serializer.validated_data["token"]), request.user
            )
        except ValueError as e:
            return Response({"success": False, "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        out = GroupMembershipSerializer(membership)
        return Response({"success": True, "message": "Joined group successfully.", "data": out.data})

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _check_membership(self, group):
        if not GroupMembership.objects.filter(
            group=group, user=self.request.user, is_active=True
        ).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You are not a member of this group.")

    def _assert_admin(self, group):
        if not GroupMembership.objects.filter(
            group=group, user=self.request.user,
            role=GroupMembership.Role.ADMIN, is_active=True
        ).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only group admins can perform this action.")
