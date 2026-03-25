"""
Celery tasks for akant app.
Scheduled via django-celery-beat (stored in DB, configurable from admin).
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_debt_reminders(self):
    """
    Periodic task: send email reminders for all overdue debts.
    Recommended schedule: every day at 09:00 UTC.
    """
    try:
        from apps.reminders.services import ReminderService
        sent, failed = ReminderService.send_all_reminders()
        logger.info("[TASK] send_debt_reminders — sent=%d failed=%d", sent, failed)
        return {"sent": sent, "failed": failed}
    except Exception as exc:
        logger.exception("[TASK] send_debt_reminders failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_monthly_reports(self):
    """
    Periodic task: generate monthly reports for all users.
    Recommended schedule: 1st of each month at 01:00 UTC.
    """
    try:
        from apps.users.models import User
        from apps.reports.services import ReportService

        now = timezone.now()
        # Generate for the PREVIOUS month
        if now.month == 1:
            year, month = now.year - 1, 12
        else:
            year, month = now.year, now.month - 1

        users = User.objects.filter(is_active=True)
        total = 0
        for user in users:
            reports = ReportService.generate_for_all_groups(user, year, month)
            total += len(reports)

        logger.info("[TASK] generate_monthly_reports — year=%d month=%d reports=%d", year, month, total)
        return {"year": year, "month": month, "reports_generated": total}
    except Exception as exc:
        logger.exception("[TASK] generate_monthly_reports failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task
def send_single_reminder(debt_id: str):
    """
    On-demand task: send a reminder for a specific debt.
    Triggered from the API endpoint.
    """
    from apps.expenses.models import Debt
    from apps.reminders.services import ReminderService

    try:
        debt = Debt.objects.get(id=debt_id, is_settled=False)
        log = ReminderService.send_reminder(debt)
        return {"success": log.is_successful, "log_id": str(log.id)}
    except Debt.DoesNotExist:
        logger.warning("[TASK] send_single_reminder — debt %s not found or settled", debt_id)
        return {"success": False, "error": "Debt not found or already settled"}
    except Exception as exc:
        logger.exception("[TASK] send_single_reminder failed: %s", exc)
        return {"success": False, "error": str(exc)}
