"""
Tests: Reports and Reminders.
"""
import pytest
from decimal import Decimal
from unittest.mock import patch
from rest_framework import status

from apps.reports.models import MonthlyReport
from apps.reports.services import ReportService
from apps.reminders.models import ReminderLog
from apps.reminders.services import ReminderService
from apps.expenses.services import ExpenseService
from apps.expenses.balance import BalanceService
from tests.factories import (
    UserFactory, GroupFactory, GroupMembershipFactory,
    DebtFactory, MonthlyReportFactory, ReminderLogFactory,
)
from apps.groups.models import GroupMembership

pytestmark = pytest.mark.django_db


# ── Reports ───────────────────────────────────────────────────────────────────

class TestReportService:
    def test_generate_report_for_user_group(self, group_with_members, user):
        ExpenseService.create_expense(
            group=group_with_members,
            title="March Dinner",
            amount=Decimal("300.00"),
            paid_by=user,
            date="2024-03-15",
        )
        report = ReportService.generate_for_user_group(user, group_with_members, 2024, 3)
        assert report.year == 2024
        assert report.month == 3
        assert report.expense_count == 1
        assert report.total_paid == Decimal("300.00")

    def test_report_is_idempotent(self, group_with_members, user):
        ReportService.generate_for_user_group(user, group_with_members, 2024, 1)
        ReportService.generate_for_user_group(user, group_with_members, 2024, 1)
        count = MonthlyReport.objects.filter(
            user=user, group=group_with_members, year=2024, month=1
        ).count()
        assert count == 1

    def test_generate_for_all_groups(self, user, group_with_members):
        reports = ReportService.generate_for_all_groups(user, 2024, 2)
        assert len(reports) >= 1

    def test_category_breakdown(self, group_with_members, user):
        ExpenseService.create_expense(
            group=group_with_members, title="Food",
            amount=Decimal("120.00"), paid_by=user,
            date="2024-04-01", category="food",
        )
        ExpenseService.create_expense(
            group=group_with_members, title="Taxi",
            amount=Decimal("60.00"), paid_by=user,
            date="2024-04-10", category="transport",
        )
        report = ReportService.generate_for_user_group(user, group_with_members, 2024, 4)
        assert "food" in report.category_breakdown
        assert "transport" in report.category_breakdown


class TestReportAPI:
    def test_list_reports(self, auth_client):
        resp = auth_client.get("/api/v1/reports/")
        assert resp.status_code == status.HTTP_200_OK

    def test_generate_report_via_api(self, auth_client, group_with_members):
        resp = auth_client.post(
            "/api/v1/reports/generate/",
            {
                "group_id": str(group_with_members.id),
                "year": 2024,
                "month": 3,
            },
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["success"] is True
        assert len(resp.data["data"]) >= 1

    def test_generate_all_groups_report(self, auth_client):
        resp = auth_client.post(
            "/api/v1/reports/generate/",
            {"year": 2024, "month": 6},
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_filter_reports_by_year(self, auth_client, user):
        MonthlyReportFactory(user=user, year=2023, month=12)
        MonthlyReportFactory(user=user, year=2024, month=1)
        resp = auth_client.get("/api/v1/reports/?year=2023")
        assert resp.status_code == status.HTTP_200_OK
        for item in resp.data["results"]:
            assert item["year"] == 2023

    def test_unauthenticated_cannot_access_reports(self, api_client):
        resp = api_client.get("/api/v1/reports/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ── Reminders ─────────────────────────────────────────────────────────────────

class TestReminderService:
    def test_send_reminder_creates_log(self, db, group_with_members, user, user2):
        debt = DebtFactory(
            group=group_with_members, debtor=user2, creditor=user, amount=Decimal("100.00")
        )
        with patch("apps.reminders.services.send_mail") as mock_mail:
            log = ReminderService.send_reminder(debt)

        assert log.pk is not None
        assert log.sent_to == user2
        mock_mail.assert_called_once()

    def test_failed_email_logs_error(self, db, group_with_members, user, user2):
        debt = DebtFactory(
            group=group_with_members, debtor=user2, creditor=user, amount=Decimal("100.00")
        )
        with patch(
            "apps.reminders.services.send_mail",
            side_effect=Exception("SMTP failure"),
        ):
            log = ReminderService.send_reminder(debt)

        assert log.is_successful is False
        assert "SMTP failure" in log.error_message

    def test_get_debts_needing_reminders_excludes_recently_reminded(
        self, db, group_with_members, user, user2
    ):
        debt = DebtFactory(
            group=group_with_members, debtor=user2, creditor=user, amount=Decimal("100.00")
        )
        ReminderLogFactory(debt=debt, sent_to=user2, is_successful=True)
        debts = ReminderService.get_debts_needing_reminders()
        assert debt not in debts

    def test_get_debts_needing_reminders_includes_old_reminders(
        self, db, group_with_members, user, user2
    ):
        from django.utils import timezone
        from datetime import timedelta
        debt = DebtFactory(
            group=group_with_members, debtor=user2, creditor=user, amount=Decimal("200.00")
        )
        # Create an old log (beyond cooldown window)
        log = ReminderLogFactory(debt=debt, sent_to=user2, is_successful=True)
        ReminderLog.objects.filter(pk=log.pk).update(
            sent_at=timezone.now() - timedelta(days=10)
        )
        debts = ReminderService.get_debts_needing_reminders()
        assert debt in debts

    def test_send_all_reminders_returns_counts(self, db, group_with_members, user, user2, user3):
        DebtFactory(group=group_with_members, debtor=user2, creditor=user, amount=Decimal("100.00"))
        DebtFactory(group=group_with_members, debtor=user3, creditor=user, amount=Decimal("50.00"))
        with patch("apps.reminders.services.send_mail"):
            sent, failed = ReminderService.send_all_reminders()
        assert sent == 2
        assert failed == 0


class TestReminderAPI:
    def test_list_reminders(self, auth_client, user):
        resp = auth_client.get("/api/v1/reminders/")
        assert resp.status_code == status.HTTP_200_OK

    def test_send_reminder_as_creditor(self, auth_client, group_with_members, user, user2):
        debt = DebtFactory(
            group=group_with_members, debtor=user2, creditor=user, amount=Decimal("100.00")
        )
        with patch("apps.reminders.views.send_single_reminder.delay") as mock_task:
            resp = auth_client.post(
                "/api/v1/reminders/send/",
                {"debt_id": str(debt.id)},
            )
        assert resp.status_code == status.HTTP_202_ACCEPTED
        mock_task.assert_called_once_with(str(debt.id))

    def test_debtor_cannot_send_reminder(self, auth_client2, group_with_members, user, user2):
        debt = DebtFactory(
            group=group_with_members, debtor=user2, creditor=user, amount=Decimal("100.00")
        )
        resp = auth_client2.post(
            "/api/v1/reminders/send/",
            {"debt_id": str(debt.id)},
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_send_reminders(self, api_client, db, group_with_members, user, user2):
        debt = DebtFactory(
            group=group_with_members, debtor=user2, creditor=user, amount=Decimal("100.00")
        )
        resp = api_client.post("/api/v1/reminders/send/", {"debt_id": str(debt.id)})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
