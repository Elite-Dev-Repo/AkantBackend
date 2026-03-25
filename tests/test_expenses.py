"""
Tests: Expenses, Splits, Debts, and Balance calculation.
"""
import pytest
from decimal import Decimal
from rest_framework import status

from apps.expenses.models import Expense, ExpenseSplit, Debt
from apps.expenses.services import ExpenseService
from apps.expenses.balance import BalanceService, _simplify_debts
from apps.groups.services import GroupService
from tests.factories import (
    UserFactory, GroupFactory, GroupMembershipFactory,
    ExpenseFactory, ExpenseSplitFactory, DebtFactory,
)
from apps.groups.models import GroupMembership

pytestmark = pytest.mark.django_db


# ── Balance Algorithm Unit Tests ──────────────────────────────────────────────

class TestSimplifyDebts:
    def test_simple_two_person(self):
        balances = {"A": Decimal("100"), "B": Decimal("-100")}
        result = _simplify_debts(balances)
        assert len(result) == 1
        assert result[0] == ("B", "A", Decimal("100"))

    def test_three_person_simplification(self):
        # A paid 300, B owes 100, C owes 100, A owes 100 to himself → net: A+200, B-100, C-100
        balances = {
            "A": Decimal("200"),
            "B": Decimal("-100"),
            "C": Decimal("-100"),
        }
        result = _simplify_debts(balances)
        total_debt = sum(r[2] for r in result)
        assert total_debt == Decimal("200")
        assert len(result) <= 2  # simplified

    def test_zero_balance_ignored(self):
        balances = {"A": Decimal("0"), "B": Decimal("0")}
        result = _simplify_debts(balances)
        assert result == []

    def test_chain_simplification(self):
        # A owes B 50, B owes C 50 → simplify to A owes C 50
        balances = {"A": Decimal("-50"), "B": Decimal("0"), "C": Decimal("50")}
        result = _simplify_debts(balances)
        assert len(result) == 1
        assert result[0][0] == "A"
        assert result[0][1] == "C"
        assert result[0][2] == Decimal("50")


# ── Signal: Equal Split Auto-Creation ────────────────────────────────────────

class TestEqualSplitSignal:
    def test_equal_splits_created_on_expense_creation(self, group_with_members, user):
        expense = ExpenseFactory(
            group=group_with_members,
            paid_by=user,
            amount=Decimal("300.00"),
            split_type=Expense.SplitType.EQUAL,
        )
        splits = ExpenseSplit.objects.filter(expense=expense)
        assert splits.count() == 3  # 3 members in group_with_members

    def test_equal_split_amounts_sum_to_total(self, group_with_members, user):
        expense = ExpenseFactory(
            group=group_with_members,
            paid_by=user,
            amount=Decimal("100.00"),
            split_type=Expense.SplitType.EQUAL,
        )
        total = sum(s.amount_owed for s in expense.splits.all())
        assert total == Decimal("100.00")

    def test_odd_amount_rounding(self, group_with_members, user):
        expense = ExpenseFactory(
            group=group_with_members,
            paid_by=user,
            amount=Decimal("100.01"),  # indivisible by 3
            split_type=Expense.SplitType.EQUAL,
        )
        total = sum(s.amount_owed for s in expense.splits.all())
        assert total == Decimal("100.01")


# ── Expense Service ───────────────────────────────────────────────────────────

class TestExpenseService:
    def test_create_expense_equal_split(self, group_with_members, user):
        expense = ExpenseService.create_expense(
            group=group_with_members,
            title="Dinner",
            amount=Decimal("300.00"),
            paid_by=user,
            date="2024-03-01",
        )
        assert expense.pk is not None
        assert expense.splits.count() == 3

    def test_create_expense_exact_split(self, group_with_members, user, user2, user3):
        split_data = [
            {"user_id": str(user.id), "amount": "100.00"},
            {"user_id": str(user2.id), "amount": "120.00"},
            {"user_id": str(user3.id), "amount": "80.00"},
        ]
        expense = ExpenseService.create_expense(
            group=group_with_members,
            title="Hotel",
            amount=Decimal("300.00"),
            paid_by=user,
            date="2024-03-01",
            split_type=Expense.SplitType.EXACT,
            split_data=split_data,
        )
        assert expense.splits.count() == 3
        split_user2 = expense.splits.get(user=user2)
        assert split_user2.amount_owed == Decimal("120.00")

    def test_exact_split_wrong_total_raises(self, group_with_members, user, user2):
        split_data = [
            {"user_id": str(user.id), "amount": "50.00"},
            {"user_id": str(user2.id), "amount": "40.00"},
        ]
        with pytest.raises(ValueError, match="must equal total"):
            ExpenseService.create_expense(
                group=group_with_members,
                title="Bad Split",
                amount=Decimal("200.00"),
                paid_by=user,
                date="2024-03-01",
                split_type=Expense.SplitType.EXACT,
                split_data=split_data,
            )

    def test_create_expense_percentage_split(self, group_with_members, user, user2, user3):
        split_data = [
            {"user_id": str(user.id), "percentage": "50"},
            {"user_id": str(user2.id), "percentage": "30"},
            {"user_id": str(user3.id), "percentage": "20"},
        ]
        expense = ExpenseService.create_expense(
            group=group_with_members,
            title="Trip",
            amount=Decimal("200.00"),
            paid_by=user,
            date="2024-03-01",
            split_type=Expense.SplitType.PERCENTAGE,
            split_data=split_data,
        )
        split_user = expense.splits.get(user=user)
        assert split_user.amount_owed == Decimal("100.00")

    def test_mark_split_paid(self, group_with_members, user, user2):
        expense = ExpenseService.create_expense(
            group=group_with_members,
            title="Lunch",
            amount=Decimal("200.00"),
            paid_by=user,
            date="2024-03-01",
        )
        split = expense.splits.get(user=user2)
        updated = ExpenseService.mark_split_paid(str(split.id), user)
        assert updated.is_paid is True

    def test_settle_debt(self, group_with_members, user, user2):
        debt = DebtFactory(
            group=group_with_members, debtor=user2, creditor=user, amount=Decimal("100.00")
        )
        updated = ExpenseService.settle_debt(str(debt.id), user2)
        assert updated.is_settled is True

    def test_non_party_cannot_settle_debt(self, group_with_members, user, user2, user3):
        debt = DebtFactory(
            group=group_with_members, debtor=user2, creditor=user, amount=Decimal("100.00")
        )
        with pytest.raises(PermissionError):
            ExpenseService.settle_debt(str(debt.id), user3)

    def test_delete_expense_by_creator(self, group_with_members, user):
        expense = ExpenseService.create_expense(
            group=group_with_members,
            title="Test",
            amount=Decimal("100.00"),
            paid_by=user,
            date="2024-03-01",
        )
        expense_id = str(expense.id)
        ExpenseService.delete_expense(expense_id, user)
        assert not Expense.objects.filter(id=expense_id).exists()


# ── Balance Service ───────────────────────────────────────────────────────────

class TestBalanceService:
    def test_compute_group_balances(self, group_with_members, user, user2, user3):
        ExpenseService.create_expense(
            group=group_with_members,
            title="Groceries",
            amount=Decimal("300.00"),
            paid_by=user,
            date="2024-03-01",
        )
        balances = BalanceService.compute_group_balances(group_with_members)
        # user paid 300, split 3 ways → 100 each
        # user owes themselves 100 (excluded), user2 owes user 100, user3 owes user 100
        assert balances[str(user.id)] == Decimal("200.00")  # owed by user2 + user3
        assert balances[str(user2.id)] == Decimal("-100.00")
        assert balances[str(user3.id)] == Decimal("-100.00")

    def test_sync_debts_creates_debt_records(self, group_with_members, user, user2, user3):
        ExpenseService.create_expense(
            group=group_with_members,
            title="Fuel",
            amount=Decimal("300.00"),
            paid_by=user,
            date="2024-03-01",
        )
        debts = Debt.objects.filter(group=group_with_members, is_settled=False)
        assert debts.count() >= 1

    def test_user_balance_summary(self, group_with_members, user, user2, user3):
        ExpenseService.create_expense(
            group=group_with_members,
            title="Airbnb",
            amount=Decimal("300.00"),
            paid_by=user,
            date="2024-03-01",
        )
        BalanceService.sync_debts(group_with_members)
        summary = BalanceService.user_balance_in_group(group_with_members, user)
        assert summary["total_owed_to_you"] > Decimal("0")
        assert summary["net"] > Decimal("0")


# ── Expense API Tests ─────────────────────────────────────────────────────────

class TestExpenseAPI:
    def expenses_url(self, group_id):
        return f"/api/v1/groups/{group_id}/expenses/"

    def test_create_expense_as_member(self, auth_client, group_with_members, user):
        resp = auth_client.post(
            self.expenses_url(group_with_members.id),
            {
                "title": "Dinner",
                "amount": "150.00",
                "paid_by_id": str(user.id),
                "date": "2024-03-01",
                "split_type": "equal",
            },
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["data"]["title"] == "Dinner"

    def test_create_expense_as_non_member(self, auth_client2, group, user2):
        resp = auth_client2.post(
            self.expenses_url(group.id),
            {
                "title": "Sneak",
                "amount": "50.00",
                "paid_by_id": str(user2.id),
                "date": "2024-03-01",
                "split_type": "equal",
            },
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_list_expenses(self, auth_client, group_with_members, expense):
        resp = auth_client.get(self.expenses_url(group_with_members.id))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] >= 1

    def test_filter_expenses_by_category(self, auth_client, group_with_members):
        ExpenseFactory(group=group_with_members, paid_by=group_with_members.created_by,
                       category=Expense.Category.FOOD)
        ExpenseFactory(group=group_with_members, paid_by=group_with_members.created_by,
                       category=Expense.Category.TRANSPORT)
        resp = auth_client.get(self.expenses_url(group_with_members.id) + "?category=food")
        assert resp.status_code == status.HTTP_200_OK
        for item in resp.data["results"]:
            assert item["category"] == "food"

    def test_debts_endpoint(self, auth_client, group_with_members, expense):
        BalanceService.sync_debts(group_with_members)
        resp = auth_client.get(f"/api/v1/groups/{group_with_members.id}/debts/")
        assert resp.status_code == status.HTTP_200_OK

    def test_my_balance_endpoint(self, auth_client, group_with_members, expense):
        BalanceService.sync_debts(group_with_members)
        resp = auth_client.get(
            f"/api/v1/groups/{group_with_members.id}/debts/my-balance/"
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "total_owed_to_you" in resp.data["data"]
