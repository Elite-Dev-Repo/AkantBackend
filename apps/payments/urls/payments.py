from django.urls import path
from rest_framework.routers import DefaultRouter
from apps.payments.views import PaymentViewSet, PaystackWebhookView, BankTransferViewSet

router = DefaultRouter()

# 1. Register the specific sub-path FIRST
router.register(r"bank-transfers", BankTransferViewSet, basename="bank-transfers")

# 2. Register the empty prefix LAST
router.register(r"", PaymentViewSet, basename="payments")

urlpatterns = [
    path("webhook/paystack/", PaystackWebhookView.as_view(), name="paystack-webhook"),
] + router.urls