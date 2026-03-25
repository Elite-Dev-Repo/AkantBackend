"""
Paystack API client.
All HTTP calls to Paystack are isolated here.
"""
import hashlib
import hmac
import uuid
import requests
from django.conf import settings


class PaystackClient:
    BASE_URL = settings.PAYSTACK_BASE_URL
    SECRET_KEY = settings.PAYSTACK_SECRET_KEY

    @classmethod
    def _headers(cls):
        return {
            "Authorization": f"Bearer {cls.SECRET_KEY}",
            "Content-Type": "application/json",
        }

    @classmethod
    def initialize_transaction(
        cls,
        email: str,
        amount_kobo: int,
        reference: str,
        callback_url: str = None,
        metadata: dict = None,
    ) -> dict:
        payload = {
            "email": email,
            "amount": amount_kobo,
            "reference": reference,
            "metadata": metadata or {},
        }
        if callback_url:
            payload["callback_url"] = callback_url

        response = requests.post(
            f"{cls.BASE_URL}/transaction/initialize",
            json=payload,
            headers=cls._headers(),
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("status"):
            raise ValueError(data.get("message", "Paystack initialization failed."))
        return data["data"]

    @classmethod
    def verify_transaction(cls, reference: str) -> dict:
        response = requests.get(
            f"{cls.BASE_URL}/transaction/verify/{reference}",
            headers=cls._headers(),
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("status"):
            raise ValueError(data.get("message", "Paystack verification failed."))
        return data["data"]

    @classmethod
    def verify_webhook_signature(cls, payload: bytes, signature: str) -> bool:
        """Verify that webhook payload came from Paystack."""
        expected = hmac.new(
            cls.SECRET_KEY.encode("utf-8"),
            payload,
            hashlib.sha512,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def generate_reference(prefix: str = "akant") -> str:
        return f"{prefix}_{uuid.uuid4().hex[:16]}"
