"""
Shared pytest fixtures available to all tests.
"""
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from tests.factories import (
    UserFactory,
    GroupFactory,
    GroupMembershipFactory,
    ExpenseFactory,
    ExpenseSplitFactory,
    DebtFactory,
)
from apps.groups.models import GroupMembership


# ── Users ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def user2(db):
    return UserFactory()


@pytest.fixture
def user3(db):
    return UserFactory()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    """Authenticated API client for `user`."""
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    api_client._user = user
    return api_client


@pytest.fixture
def auth_client2(api_client, user2):
    client = APIClient()
    refresh = RefreshToken.for_user(user2)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    client._user = user2
    return client


# ── Groups ────────────────────────────────────────────────────────────────────

@pytest.fixture
def group(db, user):
    """Group where `user` is the admin."""
    g = GroupFactory(created_by=user)
    GroupMembershipFactory(group=g, user=user, role=GroupMembership.Role.ADMIN)
    return g


@pytest.fixture
def group_with_members(db, user, user2, user3):
    """Group with three members; user is admin."""
    g = GroupFactory(created_by=user)
    GroupMembershipFactory(group=g, user=user, role=GroupMembership.Role.ADMIN)
    GroupMembershipFactory(group=g, user=user2, role=GroupMembership.Role.MEMBER)
    GroupMembershipFactory(group=g, user=user3, role=GroupMembership.Role.MEMBER)
    return g


# ── Expenses ──────────────────────────────────────────────────────────────────

@pytest.fixture
def expense(db, group_with_members, user):
    """An equal-split expense paid by user, in group_with_members."""
    return ExpenseFactory(group=group_with_members, paid_by=user, amount="300.00")


@pytest.fixture
def debt(db, group_with_members, user, user2):
    return DebtFactory(group=group_with_members, debtor=user2, creditor=user, amount="100.00")
