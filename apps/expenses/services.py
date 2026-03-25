"""
Expenses service layer.
Handles split creation, validation, and expense lifecycle.
"""
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone

from .models import Expense, ExpenseSplit, Debt
from .balance import BalanceService
from apps.groups.models import GroupMembership


class ExpenseService:

    @staticmethod
    @transaction.atomic
    def create_expense(
        group,
        title: str,
        amount: Decimal,
        paid_by,
        date,
        split_type: str = Expense.SplitType.EQUAL,
        description: str = "",
        category: str = Expense.Category.OTHER,
        currency: str = "NGN",
        receipt=None,
        split_data: list = None,
        created_by=None,
    ) -> Expense:
        """
        Create an expense and its splits.
        split_data: list of {user_id, amount|percentage} for non-equal splits.
        Signal will trigger split creation for EQUAL type if split_data is None.
        """
        # Resolve paid_by to a User instance if a UUID was passed
        if not hasattr(paid_by, 'pk'):
            from apps.users.models import User
            paid_by = User.objects.get(id=paid_by)

        # Resolve created_by to a User instance if a UUID was passed
        if created_by is not None and not hasattr(created_by, 'pk'):
            from apps.users.models import User
            created_by = User.objects.get(id=created_by)

        expense = Expense.objects.create(
            group=group,
            title=title,
            amount=amount,
            paid_by=paid_by,
            date=date,
            split_type=split_type,
            description=description,
            category=category,
            currency=currency,
            receipt=receipt,
            created_by=created_by or paid_by,
        )

        if split_data:
            ExpenseService._create_custom_splits(expense, split_data, split_type)
        # Equal splits are handled by signal (apps/expenses/signals.py)

        # Recalculate group debts
        BalanceService.sync_debts(group)
        return expense

    @staticmethod
    def _create_custom_splits(expense: Expense, split_data: list, split_type: str):
        total = expense.amount
        splits = []

        if split_type == Expense.SplitType.EXACT:
            split_sum = sum(Decimal(str(d["amount"])) for d in split_data)
            if abs(split_sum - total) > Decimal("0.01"):
                raise ValueError(
                    f"Split amounts ({split_sum}) must equal total ({total})."
                )
            for d in split_data:
                splits.append(
                    ExpenseSplit(
                        expense=expense,
                        user_id=d["user_id"],
                        amount_owed=Decimal(str(d["amount"])).quantize(
                            Decimal("0.01"), rounding=ROUND_HALF_UP
                        ),
                    )
                )

        elif split_type == Expense.SplitType.PERCENTAGE:
            pct_sum = sum(Decimal(str(d["percentage"])) for d in split_data)
            if abs(pct_sum - Decimal("100")) > Decimal("0.01"):
                raise ValueError("Percentages must sum to 100.")
            for d in split_data:
                pct = Decimal(str(d["percentage"])) / Decimal("100")
                splits.append(
                    ExpenseSplit(
                        expense=expense,
                        user_id=d["user_id"],
                        amount_owed=(total * pct).quantize(
                            Decimal("0.01"), rounding=ROUND_HALF_UP
                        ),
                    )
                )

        ExpenseSplit.objects.bulk_create(splits, ignore_conflicts=True)

    @staticmethod
    @transaction.atomic
    def mark_split_paid(split_id: str, requesting_user) -> ExpenseSplit:
        split = ExpenseSplit.objects.select_related("expense__group").get(id=split_id)

        expense = split.expense
        if requesting_user not in (split.user, expense.paid_by):
            raise PermissionError("You cannot mark this split as paid.")

        split.is_paid = True
        split.paid_at = timezone.now()
        split.save(update_fields=["is_paid", "paid_at"])

        if not expense.splits.filter(is_paid=False).exists():
            expense.is_settled = True
            expense.save(update_fields=["is_settled"])

        BalanceService.sync_debts(expense.group)
        return split

    @staticmethod
    @transaction.atomic
    def settle_debt(debt_id: str, requesting_user) -> Debt:
        debt = Debt.objects.select_related("group").get(id=debt_id)

        if requesting_user not in (debt.debtor, debt.creditor):
            raise PermissionError("You are not party to this debt.")

        splits = ExpenseSplit.objects.filter(
            expense__group=debt.group,
            user=debt.debtor,
            expense__paid_by=debt.creditor,
            is_paid=False,
        )
        now = timezone.now()
        splits.update(is_paid=True, paid_at=now)

        debt.is_settled = True
        debt.settled_at = now
        debt.save(update_fields=["is_settled", "settled_at"])

        BalanceService.sync_debts(debt.group)
        return debt

    @staticmethod
    def delete_expense(expense_id: str, requesting_user):
        expense = Expense.objects.select_related("group").get(id=expense_id)
        if requesting_user not in (expense.created_by, expense.paid_by):
            from apps.groups.models import GroupMembership
            is_admin = GroupMembership.objects.filter(
                group=expense.group,
                user=requesting_user,
                role=GroupMembership.Role.ADMIN,
                is_active=True,
            ).exists()
            if not is_admin:
                raise PermissionError("You cannot delete this expense.")

        group = expense.group
        expense.delete()
        BalanceService.sync_debts(group)