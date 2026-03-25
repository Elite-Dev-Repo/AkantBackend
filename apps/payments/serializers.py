from rest_framework import serializers
from .models import Payment
from apps.users.serializers import UserPublicSerializer


class PaymentSerializer(serializers.ModelSerializer):
    payer = UserPublicSerializer(read_only=True)
    recipient = UserPublicSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "debt", "payer", "recipient",
            "amount", "currency", "reference",
            "authorization_url", "access_code",
            "channel", "status", "paid_at",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class InitiatePaymentSerializer(serializers.Serializer):
    debt_id = serializers.UUIDField()


class VerifyPaymentSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=100)
