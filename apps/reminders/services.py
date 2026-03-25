"""
Reminders service.
Sends email reminders for unsettled debts.
"""
import logging
from datetime import timedelta

from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from django.template.loader import render_to_string

from .models import ReminderLog
from apps.expenses.models import Debt

logger = logging.getLogger(__name__)

# Don't remind the same person about the same debt more than once every N days
REMINDER_COOLDOWN_DAYS = 3


class ReminderService:

    @staticmethod
    def get_debts_needing_reminders():
        """
        Return all unsettled debts that haven't been reminded recently.
        """
        cooldown_cutoff = timezone.now() - timedelta(days=REMINDER_COOLDOWN_DAYS)

        # Debts that have been reminded recently — exclude them
        recently_reminded_debt_ids = ReminderLog.objects.filter(
            sent_at__gte=cooldown_cutoff,
            is_successful=True,
        ).values_list("debt_id", flat=True)

        return Debt.objects.filter(
            is_settled=False,
        ).exclude(
            id__in=recently_reminded_debt_ids,
        ).select_related("debtor", "creditor", "group")

    @staticmethod
    def send_reminder(debt: Debt) -> ReminderLog:
        """
        Send an email reminder to the debtor.
        """
        debtor = debt.debtor
        creditor = debt.creditor
        subject = f"💸 Reminder: You owe {creditor.full_name} {debt.amount} {debt.group.name}"

        message = (
            f"Hi {debtor.first_name},\n\n"
            f"Just a friendly reminder that you owe {creditor.full_name} "
            f"₦{debt.amount:,.2f} in the group '{debt.group.name}'.\n\n"
            f"Head over to akant to settle up: {settings.FRONTEND_URL}/groups/{debt.group_id}/debts\n\n"
            f"— The akant Team"
        )

        success = True
        error_msg = ""
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[debtor.email],
                fail_silently=False,
            )
        except Exception as exc:
            logger.exception("Failed to send reminder email to %s: %s", debtor.email, exc)
            success = False
            error_msg = str(exc)

        log = ReminderLog.objects.create(
            debt=debt,
            sent_to=debtor,
            channel=ReminderLog.Channel.EMAIL,
            is_successful=success,
            error_message=error_msg,
        )
        return log

    @staticmethod
    def send_all_reminders():
        """
        Called by Celery beat. Sends reminders for all eligible debts.
        Returns (sent_count, failed_count).
        """
        debts = ReminderService.get_debts_needing_reminders()
        sent = 0
        failed = 0
        for debt in debts:
            log = ReminderService.send_reminder(debt)
            if log.is_successful:
                sent += 1
            else:
                failed += 1
        logger.info("Reminders sent: %d, failed: %d", sent, failed)
        return sent, failed
