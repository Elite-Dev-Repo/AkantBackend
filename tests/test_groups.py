"""
Tests: Groups — models, service, and API endpoints.
"""
import pytest
from django.utils import timezone
from datetime import timedelta  # noqa: F401 — used in fixtures
from rest_framework import status

from apps.groups.models import Group, GroupMembership, GroupInvite
from apps.groups.services import GroupService
from tests.factories import UserFactory, GroupFactory, GroupMembershipFactory, GroupInviteFactory

pytestmark = pytest.mark.django_db


# ── Model Tests ───────────────────────────────────────────────────────────────

class TestGroupModel:
    def test_create_group(self, group):
        assert group.pk is not None
        assert group.is_active is True

    def test_member_count(self, group_with_members):
        assert group_with_members.member_count == 3

    def test_str_representation(self):
        group = GroupFactory(name="Test Group")
        assert str(group) == "Test Group"

    def test_uuid_primary_key(self, group):
        import uuid
        assert isinstance(group.id, uuid.UUID)


# ── Service Tests ─────────────────────────────────────────────────────────────

class TestGroupService:
    def test_create_group_makes_creator_admin(self, db):
        user = UserFactory()
        group = GroupService.create_group("My Group", "desc", user)
        membership = GroupMembership.objects.get(group=group, user=user)
        assert membership.role == GroupMembership.Role.ADMIN

    def test_get_user_groups_only_active(self, db):
        user = UserFactory()
        active_group = GroupFactory(is_active=True)
        inactive_group = GroupFactory(is_active=False)
        GroupMembershipFactory(group=active_group, user=user, is_active=True)
        GroupMembershipFactory(group=inactive_group, user=user, is_active=True)
        groups = GroupService.get_user_groups(user)
        assert active_group in groups
        assert inactive_group not in groups

    def test_invite_creates_invite_record(self, db, group, user):
        invitee_email = "invitee@akant.test"
        invite = GroupService.invite_member(group, user, invitee_email)
        assert invite.invited_email == invitee_email
        assert invite.status == GroupInvite.Status.PENDING

    def test_invite_already_member_raises(self, db, group_with_members, user, user2):
        with pytest.raises(ValueError, match="already a member"):
            GroupService.invite_member(group_with_members, user, user2.email)

    def test_accept_invite_creates_membership(self, db, user2):
        inviter = UserFactory()
        group = GroupService.create_group("Group", "", inviter)
        invite = GroupInviteFactory(
            group=group,
            invited_by=inviter,
            invited_email=user2.email,
            expires_at=timezone.now() + timedelta(days=7),
        )
        membership = GroupService.accept_invite(str(invite.token), user2)
        assert membership.user == user2
        assert membership.group == group

    def test_accept_expired_invite_raises(self, db, user2):
        inviter = UserFactory()
        group = GroupService.create_group("Group", "", inviter)
        invite = GroupInviteFactory(
            group=group,
            invited_by=inviter,
            invited_email=user2.email,
            expires_at=timezone.now() - timedelta(days=1),
        )
        with pytest.raises(ValueError, match="expired"):
            GroupService.accept_invite(str(invite.token), user2)

    def test_accept_invite_wrong_email_raises(self, db):
        inviter = UserFactory()
        group = GroupService.create_group("Group", "", inviter)
        other_user = UserFactory()
        invite = GroupInviteFactory(
            group=group,
            invited_by=inviter,
            invited_email="someone_else@akant.test",
            expires_at=timezone.now() + timedelta(days=7),
        )
        with pytest.raises(ValueError, match="not sent to your email"):
            GroupService.accept_invite(str(invite.token), other_user)

    def test_remove_member_by_admin(self, db, group_with_members, user, user2):
        GroupService.remove_member(group_with_members, user2, user)
        membership = GroupMembership.objects.get(group=group_with_members, user=user2)
        assert membership.is_active is False

    def test_non_admin_cannot_remove_member(self, db, group_with_members, user2, user3):
        with pytest.raises(PermissionError):
            GroupService.remove_member(group_with_members, user3, user2)

    def test_user_can_leave_group(self, db, group_with_members, user2):
        GroupService.remove_member(group_with_members, user2, user2)
        membership = GroupMembership.objects.get(group=group_with_members, user=user2)
        assert membership.is_active is False


# ── API Tests ─────────────────────────────────────────────────────────────────

class TestGroupAPI:
    list_url = "/api/v1/groups/"

    def detail_url(self, pk):
        return f"/api/v1/groups/{pk}/"

    def test_list_groups_authenticated(self, auth_client, group):
        resp = auth_client.get(self.list_url)
        assert resp.status_code == status.HTTP_200_OK
        ids = [r["id"] for r in resp.data["results"]]
        assert str(group.id) in ids

    def test_list_groups_unauthenticated(self, api_client):
        resp = api_client.get(self.list_url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_group(self, auth_client):
        resp = auth_client.post(self.list_url, {"name": "New Group", "description": "desc"})
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["data"]["name"] == "New Group"

    def test_retrieve_group_as_member(self, auth_client, group):
        resp = auth_client.get(self.detail_url(group.id))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"]["id"] == str(group.id)

    def test_retrieve_group_as_non_member(self, auth_client2, group):
        resp = auth_client2.get(self.detail_url(group.id))
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_update_group_as_admin(self, auth_client, group):
        resp = auth_client.patch(self.detail_url(group.id), {"name": "Renamed"})
        assert resp.status_code == status.HTTP_200_OK
        group.refresh_from_db()
        assert group.name == "Renamed"

    def test_update_group_as_non_admin(self, auth_client2, group_with_members, user2):
        # auth_client2 is user2, who is a MEMBER not ADMIN
        client2 = auth_client2
        resp = client2.patch(f"/api/v1/groups/{group_with_members.id}/", {"name": "Hack"})
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_deactivate_group(self, auth_client, group):
        resp = auth_client.delete(self.detail_url(group.id))
        assert resp.status_code == status.HTTP_200_OK
        group.refresh_from_db()
        assert group.is_active is False

    def test_list_members(self, auth_client, group_with_members):
        resp = auth_client.get(f"/api/v1/groups/{group_with_members.id}/members/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["data"]) == 3

    def test_send_invite(self, auth_client, group):
        resp = auth_client.post(
            f"/api/v1/groups/{group.id}/invites/",
            {"invited_email": "newperson@akant.test"},
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert GroupInvite.objects.filter(
            group=group, invited_email="newperson@akant.test"
        ).exists()

    def test_accept_invite(self, auth_client2, group, user2):
        from django.utils import timezone
        invite = GroupInviteFactory(
            group=group,
            invited_by=group.created_by,
            invited_email=user2.email,
            expires_at=timezone.now() + timedelta(days=7),
        )
        resp = auth_client2.post(
            "/api/v1/groups/invites/accept/",
            {"token": str(invite.token)},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert GroupMembership.objects.filter(group=group, user=user2, is_active=True).exists()

    def test_search_groups(self, auth_client, group):
        resp = auth_client.get(self.list_url + f"?search={group.name[:5]}")
        assert resp.status_code == status.HTTP_200_OK


# ── Prevent cross-group data leakage ─────────────────────────────────────────

class TestGroupIsolation:
    def test_user_cannot_see_other_group(self, auth_client, db):
        other_user = UserFactory()
        other_group = GroupService.create_group("Secret Group", "", other_user)
        resp = auth_client.get(f"/api/v1/groups/{other_group.id}/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_group_not_in_list_if_not_member(self, auth_client, db):
        other_user = UserFactory()
        other_group = GroupService.create_group("Other Group", "", other_user)
        resp = auth_client.get("/api/v1/groups/")
        ids = [r["id"] for r in resp.data["results"]]
        assert str(other_group.id) not in ids
