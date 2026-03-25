from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import PaymentViewSet, PaystackWebhookView

router = DefaultRouter()
router.register(r"", PaymentViewSet, basename="payments")

urlpatterns = [
    path("webhook/paystack/", PaystackWebhookView.as_view(), name="paystack-webhook"),
] + router.urls
