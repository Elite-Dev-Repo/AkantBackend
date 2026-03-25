"""
Reports service — generates and stores monthly expense reports.
"""
from decimal import Decimal
from collections import defaultdict
from django.db.models import Sum
from django.utils import timezone

from .models import MonthlyReport
from apps.expenses.models import Expense, ExpenseSplit
from apps.groups.models import Group, GroupMembership


class ReportService:

    @staticmethod
    def generate_for_user_group(user, group: Group, year: int, month: int) -> MonthlyReport:
        """
        Build (or refresh) the monthly report for one user in one group.
        """
        expenses = Expense.objects.filter(
            group=group,
            date__year=year,
            date__month=month,
        ).prefetch_related("splits")

        total_spent = Decimal("0.00")
        total_paid = Decimal("0.00")
        total_owed = Decimal("0.00")
        total_received = Decimal("0.00")
        category_breakdown: dict = defaultdict(Decimal)
        expense_count = 0

        for expense in expenses:
            expense_count += 1

            # What this user paid out
            if expense.paid_by_id == user.id:
                total_paid += expense.amount
                total_received += expense.amount  # they're owed back by others

            # What this user owes
            for split in expense.splits.all():
                if split.user_id == user.id:
                    total_owed += split.amount_owed
                    total_spent += split.amount_owed
                    category_breakdown[expense.category] += split.amount_owed

        report, _ = MonthlyReport.objects.update_or_create(
            user=user,
            group=group,
            year=year,
            month=month,
            defaults={
                "total_spent": total_spent,
                "total_paid": total_paid,
                "total_owed": total_owed,
                "total_received": total_received,
                "expense_count": expense_count,
                "category_breakdown": {k: str(v) for k, v in category_breakdown.items()},
            },
        )
        return report

    @staticmethod
    def generate_for_all_groups(user, year: int, month: int):
        """Generate reports for all groups the user belongs to."""
        groups = Group.objects.filter(
            memberships__user=user,
            memberships__is_active=True,
            is_active=True,
        )
        reports = []
        for group in groups:
            reports.append(
                ReportService.generate_for_user_group(user, group, year, month)
            )
        return reports

    @staticmethod
    def get_user_reports(user, group=None, year=None, month=None):
        qs = MonthlyReport.objects.filter(user=user).select_related("group")
        if group:
            qs = qs.filter(group=group)
        if year:
            qs = qs.filter(year=year)
        if month:
            qs = qs.filter(month=month)
        return qs
