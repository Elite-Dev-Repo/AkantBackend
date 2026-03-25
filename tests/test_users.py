"""
Tests: Users — model + auth endpoints.
"""
import pytest
from django.urls import reverse
from rest_framework import status

from apps.users.models import User
from tests.factories import UserFactory


pytestmark = pytest.mark.django_db


# ── Model Tests ───────────────────────────────────────────────────────────────

class TestUserModel:
    def test_create_user(self):
        user = UserFactory()
        assert user.pk is not None
        assert user.is_active is True
        assert user.is_staff is False

    def test_full_name(self):
        user = UserFactory(first_name="Ada", last_name="Lovelace")
        assert user.full_name == "Ada Lovelace"

    def test_str_representation(self):
        user = UserFactory(first_name="Ada", last_name="Lovelace", email="ada@test.com")
        assert "Ada Lovelace" in str(user)
        assert "ada@test.com" in str(user)

    def test_create_superuser(self):
        su = User.objects.create_superuser(
            email="admin@bills.test",
            username="admin",
            first_name="Super",
            last_name="User",
            password="AdminPass123!",
        )
        assert su.is_staff is True
        assert su.is_superuser is True

    def test_password_is_hashed(self):
        user = UserFactory(password="plainpassword")
        assert user.password != "plainpassword"
        assert user.check_password("plainpassword") is False  # wrong — factory sets TestPass123!
        assert user.check_password("TestPass123!") is True

    def test_uuid_primary_key(self):
        user = UserFactory()
        import uuid
        assert isinstance(user.id, uuid.UUID)


# ── Registration ──────────────────────────────────────────────────────────────

class TestRegistration:
    url = "/api/v1/auth/register/"

    def test_register_success(self, api_client):
        payload = {
            "email": "newuser@bills.test",
            "username": "newuser",
            "first_name": "New",
            "last_name": "User",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
        }
        resp = api_client.post(self.url, payload)
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["success"] is True
        assert User.objects.filter(email="newuser@bills.test").exists()

    def test_register_password_mismatch(self, api_client):
        payload = {
            "email": "x@bills.test",
            "username": "xuser",
            "first_name": "X",
            "last_name": "User",
            "password": "StrongPass123!",
            "password_confirm": "WrongPass456!",
        }
        resp = api_client.post(self.url, payload)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_duplicate_email(self, api_client, user):
        payload = {
            "email": user.email,
            "username": "otherusername",
            "first_name": "Dup",
            "last_name": "User",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
        }
        resp = api_client.post(self.url, payload)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_weak_password(self, api_client):
        payload = {
            "email": "weak@bills.test",
            "username": "weakuser",
            "first_name": "Weak",
            "last_name": "User",
            "password": "123",
            "password_confirm": "123",
        }
        resp = api_client.post(self.url, payload)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ── Login ─────────────────────────────────────────────────────────────────────

class TestLogin:
    url = "/api/v1/auth/login/"

    def test_login_success(self, api_client, user):
        resp = api_client.post(self.url, {"email": user.email, "password": "TestPass123!"})
        assert resp.status_code == status.HTTP_200_OK
        assert "access" in resp.data
        assert "refresh" in resp.data

    def test_login_wrong_password(self, api_client, user):
        resp = api_client.post(self.url, {"email": user.email, "password": "wrongpassword"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_unknown_email(self, api_client):
        resp = api_client.post(self.url, {"email": "ghost@bills.test", "password": "any"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ── Profile ───────────────────────────────────────────────────────────────────

class TestUserProfile:
    url = "/api/v1/users/me/"

    def test_get_profile(self, auth_client, user):
        resp = auth_client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"]["email"] == user.email

    def test_update_profile(self, auth_client, user):
        resp = auth_client.patch(self.url, {"first_name": "Updated"})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"]["first_name"] == "Updated"

    def test_unauthenticated_profile(self, api_client):
        resp = api_client.get(self.url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestChangePassword:
    url = "/api/v1/users/change-password/"

    def test_change_password_success(self, auth_client, user):
        resp = auth_client.post(
            self.url,
            {
                "old_password": "TestPass123!",
                "new_password": "NewStrongPass456!",
                "new_password_confirm": "NewStrongPass456!",
            },
        )
        assert resp.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.check_password("NewStrongPass456!") is True

    def test_change_password_wrong_old(self, auth_client):
        resp = auth_client.post(
            self.url,
            {
                "old_password": "wrongold",
                "new_password": "NewStrongPass456!",
                "new_password_confirm": "NewStrongPass456!",
            },
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_change_password_mismatch(self, auth_client):
        resp = auth_client.post(
            self.url,
            {
                "old_password": "TestPass123!",
                "new_password": "NewPass456!",
                "new_password_confirm": "DifferentPass789!",
            },
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
