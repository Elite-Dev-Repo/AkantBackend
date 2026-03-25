"""
Tests: Payments and Paystack webhook.
"""
import hashlib
import hmac
import json
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from rest_framework import status

from apps.payments.models import Payment
from apps.payments.services import PaymentService
from tests.factories import UserFactory, DebtFactory, PaymentFactory, GroupFactory, GroupMembershipFactory
from apps.groups.models import GroupMembership

pytestmark = pytest.mark.django_db


MOCK_PAYSTACK_INIT = {
    "authorization_url": "https://checkout.paystack.com/test",
    "access_code": "abc123",
    "reference": "Akant_test_ref_000001",
}

MOCK_PAYSTACK_VERIFY = {
    "status": "success",
    "id": 12345,
    "channel": "card",
    "reference": "Akant_test_ref_000001",
    "amount": 10000,
}


class TestPaymentService:
    def test_initiate_payment_creates_record(self, db, group_with_members, user, user2):
        debt = DebtFactory(
            group=group_with_members, debtor=user2, creditor=user, amount=Decimal("100.00")
        )
        with patch(
            "apps.payments.services.PaystackClient.initialize_transaction",
            return_value=MOCK_PAYSTACK_INIT,
        ):
            payment = PaymentService.initiate_payment(payer=user2, debt_id=str(debt.id))

        assert payment.pk is not None
        assert payment.status == Payment.Status.PENDING
        assert payment.payer == user2

    def test_only_debtor_can_initiate(self, db, group_with_members, user, user2):
        debt = DebtFactory(
            group=group_with_members, debtor=user2, creditor=user, amount=Decimal("100.00")
        )
        with patch(
            "apps.payments.services.PaystackClient.initialize_transaction",
            return_value=MOCK_PAYSTACK_INIT,
        ):
            with pytest.raises(PermissionError):
                PaymentService.initiate_payment(payer=user, debt_id=str(debt.id))

    def test_verify_and_settle_marks_success(self, db, group_with_members, user, user2):
        debt = DebtFactory(
            group=group_with_members, debtor=user2, creditor=user, amount=Decimal("100.00")
        )
        payment = PaymentFactory(
            debt=debt, payer=user2, recipient=user,
            reference="Akant_verify_test", status=Payment.Status.PENDING
        )
        verify_data = {**MOCK_PAYSTACK_VERIFY, "reference": "Akant_verify_test"}
        with patch(
            "apps.payments.services.PaystackClient.verify_transaction",
            return_value=verify_data,
        ):
            updated = PaymentService.verify_and_settle("Akant_verify_test")

        assert updated.status == Payment.Status.SUCCESS

    def test_verify_idempotent_for_success(self, db, group_with_members, user, user2):
        debt = DebtFactory(
            group=group_with_members, debtor=user2, creditor=user, amount=Decimal("100.00")
        )
        payment = PaymentFactory(
            debt=debt, payer=user2, recipient=user,
            reference="Akant_idempotent_ref", status=Payment.Status.SUCCESS
        )
        # Should return early without calling Paystack again
        with patch(
            "apps.payments.services.PaystackClient.verify_transaction"
        ) as mock_verify:
            result = PaymentService.verify_and_settle("Akant_idempotent_ref")
            mock_verify.assert_not_called()

        assert result.status == Payment.Status.SUCCESS


class TestPaymentAPI:
    def test_initiate_payment_endpoint(self, auth_client2, group_with_members, user, user2):
        from tests.conftest import *  # noqa
        debt = DebtFactory(
            group=group_with_members, debtor=user2, creditor=user, amount=Decimal("100.00")
        )
        with patch(
            "apps.payments.services.PaystackClient.initialize_transaction",
            return_value=MOCK_PAYSTACK_INIT,
        ):
            resp = auth_client2.post(
                "/api/v1/payments/initiate/",
                {"debt_id": str(debt.id)},
            )
        assert resp.status_code == status.HTTP_201_CREATED
        assert "authorization_url" in resp.data

    def test_verify_payment_endpoint(self, auth_client2, group_with_members, user, user2):
        debt = DebtFactory(
            group=group_with_members, debtor=user2, creditor=user, amount=Decimal("100.00")
        )
        payment = PaymentFactory(
            debt=debt, payer=user2, recipient=user,
            reference="verify_endpoint_ref", status=Payment.Status.PENDING
        )
        verify_data = {**MOCK_PAYSTACK_VERIFY, "reference": "verify_endpoint_ref"}
        with patch(
            "apps.payments.services.PaystackClient.verify_transaction",
            return_value=verify_data,
        ):
            resp = auth_client2.post(
                "/api/v1/payments/verify/",
                {"reference": "verify_endpoint_ref"},
            )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"]["status"] == "success"

    def test_list_payments(self, auth_client2, user2):
        PaymentFactory.create_batch(3, payer=user2)
        resp = auth_client2.get("/api/v1/payments/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] >= 3


class TestPaystackWebhook:
    url = "/api/v1/payments/webhook/paystack/"

    def _make_signature(self, payload: bytes, secret: str = "") -> str:
        from django.conf import settings
        key = secret or settings.PAYSTACK_SECRET_KEY or "test_secret"
        return hmac.new(key.encode(), payload, hashlib.sha512).hexdigest()

    def test_valid_webhook_charge_success(self, api_client, db, group_with_members, user, user2):
        debt = DebtFactory(
            group=group_with_members, debtor=user2, creditor=user, amount=Decimal("100.00")
        )
        payment = PaymentFactory(
            debt=debt, payer=user2, recipient=user,
            reference="webhook_ref_001", status=Payment.Status.PENDING
        )
        payload = json.dumps({
            "event": "charge.success",
            "data": {"reference": "webhook_ref_001", "status": "success"},
        }).encode()

        verify_data = {**MOCK_PAYSTACK_VERIFY, "reference": "webhook_ref_001"}
        with patch("apps.payments.views.PaystackClient.verify_webhook_signature", return_value=True):
            with patch("apps.payments.services.PaystackClient.verify_transaction", return_value=verify_data):
                resp = api_client.post(
                    self.url,
                    data=payload,
                    content_type="application/json",
                    HTTP_X_PAYSTACK_SIGNATURE="validsig",
                )
        assert resp.status_code == status.HTTP_200_OK

    def test_invalid_signature_rejected(self, api_client):
        payload = json.dumps({"event": "charge.success", "data": {}}).encode()
        with patch("apps.payments.views.PaystackClient.verify_webhook_signature", return_value=False):
            resp = api_client.post(
                self.url,
                data=payload,
                content_type="application/json",
                HTTP_X_PAYSTACK_SIGNATURE="badsig",
            )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_unknown_event_returns_200(self, api_client):
        payload = json.dumps({"event": "transfer.success", "data": {}}).encode()
        with patch("apps.payments.views.PaystackClient.verify_webhook_signature", return_value=True):
            resp = api_client.post(
                self.url,
                data=payload,
                content_type="application/json",
                HTTP_X_PAYSTACK_SIGNATURE="validsig",
            )
        assert resp.status_code == status.HTTP_200_OK
