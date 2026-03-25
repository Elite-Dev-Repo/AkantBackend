import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        ABANDONED = "abandoned", "Abandoned"
        REVERSED = "reversed", "Reversed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    debt = models.ForeignKey(
        "expenses.Debt",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    payer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments_made",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments_received",
    )
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    currency = models.CharField(max_length=3, default="NGN")

    # Paystack
    reference = models.CharField(max_length=100, unique=True, db_index=True)
    paystack_id = models.BigIntegerField(null=True, blank=True)
    authorization_url = models.URLField(blank=True, default="")
    access_code = models.CharField(max_length=100, blank=True, default="")
    channel = models.CharField(max_length=50, blank=True, default="")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)

    metadata = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment {self.reference} — {self.amount} {self.currency} ({self.status})"

    @property
    def amount_kobo(self):
        """Paystack uses smallest currency unit (kobo for NGN)."""
        return int(self.amount * 100)
