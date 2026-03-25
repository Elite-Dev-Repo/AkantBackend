from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["reference", "payer", "recipient", "amount", "currency", "status", "paid_at", "created_at"]
    list_filter = ["status", "currency", "channel"]
    search_fields = ["reference", "payer__email", "recipient__email"]
    readonly_fields = ["reference", "paystack_id", "authorization_url", "access_code", "metadata", "created_at", "updated_at"]
    ordering = ["-created_at"]
