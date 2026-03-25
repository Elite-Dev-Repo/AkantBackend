import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator


class Expense(models.Model):
    class SplitType(models.TextChoices):
        EQUAL = "equal", "Equal"
        EXACT = "exact", "Exact Amounts"
        PERCENTAGE = "percentage", "Percentage"

    class Category(models.TextChoices):
        FOOD = "food", "Food & Drinks"
        TRANSPORT = "transport", "Transport"
        ACCOMMODATION = "accommodation", "Accommodation"
        ENTERTAINMENT = "entertainment", "Entertainment"
        UTILITIES = "utilities", "Utilities"
        SHOPPING = "shopping", "Shopping"
        HEALTH = "health", "Health"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        "groups.Group", on_delete=models.CASCADE, related_name="expenses"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    currency = models.CharField(max_length=3, default="NGN")
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    split_type = models.CharField(max_length=15, choices=SplitType.choices, default=SplitType.EQUAL)
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="paid_expenses",
    )
    receipt = models.FileField(upload_to="receipts/", null=True, blank=True)
    date = models.DateField()
    is_settled = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_expenses",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "expenses"
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.title} — {self.amount} {self.currency}"


class ExpenseSplit(models.Model):
    """Represents one user's share of an expense."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="splits")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="expense_splits",
    )
    amount_owed = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "expense_splits"
        unique_together = [("expense", "user")]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user} owes {self.amount_owed} for '{self.expense.title}'"


class Debt(models.Model):
    """
    Aggregated simplified debt between two users in a group.
    Recalculated whenever expenses change.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        "groups.Group", on_delete=models.CASCADE, related_name="debts"
    )
    debtor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="debts_owed",
    )
    creditor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="debts_receivable",
    )
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    is_settled = models.BooleanField(default=False)
    settled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "debts"
        unique_together = [("group", "debtor", "creditor")]
        ordering = ["-amount"]

    def __str__(self):
        return f"{self.debtor} owes {self.creditor} {self.amount}"
