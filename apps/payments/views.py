import json
import logging
from django.db import models as django_models
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import Payment, BankTransferPayment
from .serializers import (
    PaymentSerializer, InitiatePaymentSerializer, VerifyPaymentSerializer,
    BankTransferPaymentSerializer, InitiateBankTransferSerializer,
)
from .services import PaymentService
from .paystack import PaystackClient
from .filters import PaymentFilter
from apps.expenses.models import Debt

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(tags=["payments"], summary="List my payments"),
    retrieve=extend_schema(tags=["payments"], summary="Get payment detail"),
)
class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PaymentSerializer
    filterset_class = PaymentFilter
    ordering_fields = ["amount", "created_at", "paid_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Payment.objects.filter(
            payer=self.request.user
        ).select_related("payer", "recipient", "debt").distinct()

    @extend_schema(tags=["payments"], summary="Initiate a Paystack payment for a debt")
    @action(detail=False, methods=["post"], url_path="initiate")
    def initiate(self, request):
        serializer = InitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payment = PaymentService.initiate_payment(
                payer=request.user,
                debt_id=str(serializer.validated_data["debt_id"]),
            )
        except Payment.DoesNotExist:
            return Response(
                {"success": False, "message": "Debt not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except PermissionError as e:
            return Response({"success": False, "message": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            logger.exception("Paystack initiation failed: %s", e)
            return Response(
                {"success": False, "message": "Payment initiation failed. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        out = PaymentSerializer(payment)
        return Response(
            {
                "success": True,
                "message": "Payment initialized.",
                "data": out.data,
                "authorization_url": payment.authorization_url,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(tags=["payments"], summary="Verify a Paystack payment by reference")
    @action(detail=False, methods=["post"], url_path="verify")
    def verify(self, request):
        serializer = VerifyPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payment = PaymentService.verify_and_settle(serializer.validated_data["reference"])
        except Payment.DoesNotExist:
            return Response(
                {"success": False, "message": "Payment not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.exception("Paystack verification failed: %s", e)
            return Response(
                {"success": False, "message": "Verification failed. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        out = PaymentSerializer(payment)
        return Response({"success": True, "data": out.data})


@extend_schema(tags=["payments"], summary="Paystack webhook endpoint")
class PaystackWebhookView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        signature = request.headers.get("X-Paystack-Signature", "")
        raw_body = request.body
        if not PaystackClient.verify_webhook_signature(raw_body, signature):
            logger.warning("Invalid Paystack webhook signature received.")
            return Response({"detail": "Invalid signature."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            return Response({"detail": "Invalid JSON."}, status=status.HTTP_400_BAD_REQUEST)
        event = payload.get("event", "")
        data = payload.get("data", {})
        try:
            PaymentService.handle_webhook(event, data)
        except Exception:
            logger.exception("Webhook handler error for event: %s", event)
            return Response({"detail": "Internal error."}, status=status.HTTP_200_OK)
        return Response({"detail": "Webhook received."}, status=status.HTTP_200_OK)


class BankTransferViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = BankTransferPaymentSerializer

    def get_queryset(self):
        user = self.request.user
        # Use django_models.Q — NOT models.Q
        return BankTransferPayment.objects.filter(
            django_models.Q(payer=user) | django_models.Q(creditor=user)
        ).select_related("payer", "creditor", "account_details", "debt__group")

    @action(detail=False, methods=["post"], url_path="initiate")
    def initiate(self, request):
        serializer = InitiateBankTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            transfer = PaymentService.initiate_bank_transfer(
                payer=request.user,
                debt_id=str(serializer.validated_data["debt_id"]),
                note=serializer.validated_data.get("note", ""),
            )
        except (Debt.DoesNotExist, ValueError) as e:
            return Response({"success": False, "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as e:
            return Response({"success": False, "message": str(e)}, status=status.HTTP_403_FORBIDDEN)
        out = BankTransferPaymentSerializer(transfer)
        return Response(
            {"success": True, "message": "Payment instance created.", "data": out.data},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        try:
            transfer = PaymentService.confirm_bank_transfer(pk, request.user)
        except BankTransferPayment.DoesNotExist:
            return Response(
                {"success": False, "message": "Transfer not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except PermissionError as e:
            return Response({"success": False, "message": str(e)}, status=status.HTTP_403_FORBIDDEN)
        out = BankTransferPaymentSerializer(transfer)
        return Response(
            {"success": True, "message": "Payment confirmed. Debt settled.", "data": out.data}
        )