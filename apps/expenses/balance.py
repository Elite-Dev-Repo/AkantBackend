"""
Balance calculation engine.

Algorithm:
1. For every expense in a group, each split member "owes" the payer
   their share (minus what they personally paid, which is 0 if they
   didn't pay the expense).
2. We accumulate net balances: positive = owed money, negative = owes money.
3. We simplify the debt graph (greedy min-cash-flow) to minimise transactions.
"""
from collections import defaultdict
from decimal import Decimal
from typing import List, Dict, Tuple

from django.db import transaction
from django.utils import timezone

from apps.expenses.models import Expense, ExpenseSplit, Debt
from apps.groups.models import Group


def _simplify_debts(balances: Dict) -> List[Tuple]:
    """
    Greedy debt-simplification.
    Returns list of (debtor_id, creditor_id, amount).
    """
    pos = {uid: amt for uid, amt in balances.items() if amt > 0}   # creditors
    neg = {uid: -amt for uid, amt in balances.items() if amt < 0}  # debtors (positive amounts)

    transactions = []
    pos_list = sorted(pos.items(), key=lambda x: x[1], reverse=True)
    neg_list = sorted(neg.items(), key=lambda x: x[1], reverse=True)

    i, j = 0, 0
    pos_list = list(pos_list)
    neg_list = list(neg_list)

    while i < len(pos_list) and j < len(neg_list):
        creditor_id, credit = pos_list[i]
        debtor_id, debt = neg_list[j]
        settle = min(credit, debt)
        if settle > Decimal("0.00"):
            transactions.append((debtor_id, creditor_id, settle))
        credit -= settle
        debt -= settle
        pos_list[i] = (creditor_id, credit)
        neg_list[j] = (debtor_id, debt)
        if credit == 0:
            i += 1
        if debt == 0:
            j += 1

    return transactions


class BalanceService:

    @staticmethod
    def compute_group_balances(group: Group) -> Dict:
        """
        Returns {user_id: net_balance} for all members.
        Positive = is owed money. Negative = owes money.
        """
        balances: Dict = defaultdict(Decimal)

        expenses = (
            Expense.objects
            .filter(group=group, is_settled=False)
            .prefetch_related("splits")
        )

        for expense in expenses:
            payer_id = str(expense.paid_by_id)
            for split in expense.splits.filter(is_paid=False):
                debtor_id = str(split.user_id)
                if debtor_id == payer_id:
                    continue  # payer doesn't owe themselves
                balances[debtor_id] -= split.amount_owed
                balances[payer_id] += split.amount_owed

        return dict(balances)

    @staticmethod
    def get_simplified_debts(group: Group) -> List[Tuple]:
        """Returns simplified debt list: [(debtor_id, creditor_id, amount)]"""
        balances = BalanceService.compute_group_balances(group)
        return _simplify_debts(
            {uid: Decimal(str(amt)) for uid, amt in balances.items()}
        )

    @staticmethod
    @transaction.atomic
    def sync_debts(group: Group):
        """Recalculate and persist simplified debts for a group."""
        simplified = BalanceService.get_simplified_debts(group)

        # Mark all existing debts settled (we'll recreate from scratch)
        Debt.objects.filter(group=group).delete()

        debts_to_create = []
        for debtor_id, creditor_id, amount in simplified:
            debts_to_create.append(
                Debt(
                    group=group,
                    debtor_id=debtor_id,
                    creditor_id=creditor_id,
                    amount=amount,
                )
            )
        Debt.objects.bulk_create(debts_to_create)

    @staticmethod
    def user_balance_in_group(group: Group, user) -> Dict:
        """
        Returns a detailed balance summary for one user in a group.
        {
            "total_owed_to_you": Decimal,
            "total_you_owe": Decimal,
            "net": Decimal,
            "details": [{"user": ..., "amount": ..., "direction": "owes_you"|"you_owe"}]
        }
        """
        debts = Debt.objects.filter(
            group=group, is_settled=False
        ).filter(
            debtor=user
        ) | Debt.objects.filter(
            group=group, is_settled=False
        ).filter(
            creditor=user
        )

        owed_to_you = Decimal("0.00")
        you_owe = Decimal("0.00")
        details = []

        for debt in debts.select_related("debtor", "creditor"):
            if str(debt.creditor_id) == str(user.id):
                owed_to_you += debt.amount
                details.append({
                    "user": debt.debtor,
                    "amount": debt.amount,
                    "direction": "owes_you",
                    "debt_id": str(debt.id),
                })
            else:
                you_owe += debt.amount
                details.append({
                    "user": debt.creditor,
                    "amount": debt.amount,
                    "direction": "you_owe",
                    "debt_id": str(debt.id),
                })

        return {
            "total_owed_to_you": owed_to_you,
            "total_you_owe": you_owe,
            "net": owed_to_you - you_owe,
            "details": details,
        }
