from rest_framework import serializers
from .models import Payment, BankTransferPayment
from apps.users.serializers import UserPublicSerializer, AccountDetailsSerializer


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


class BankTransferPaymentSerializer(serializers.ModelSerializer):
    payer = UserPublicSerializer(read_only=True)
    creditor = UserPublicSerializer(read_only=True)
    account_details = AccountDetailsSerializer(read_only=True)

    class Meta:
        model = BankTransferPayment
        fields = [
            "id", "debt", "payer", "creditor", "account_details",
            "amount", "status", "note", "confirmed_at", "created_at",
        ]
        read_only_fields = fields


class InitiateBankTransferSerializer(serializers.Serializer):
    debt_id = serializers.UUIDField()
    note = serializers.CharField(required=False, allow_blank=True, default="")