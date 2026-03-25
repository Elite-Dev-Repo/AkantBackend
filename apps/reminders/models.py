import uuid
from django.db import models
from django.conf import settings


class ReminderLog(models.Model):
    """
    Tracks every reminder sent so we don't spam users.
    """
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        PUSH = "push", "Push Notification"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    debt = models.ForeignKey(
        "expenses.Debt",
        on_delete=models.CASCADE,
        related_name="reminder_logs",
    )
    sent_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reminders_received",
    )
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.EMAIL)
    sent_at = models.DateTimeField(auto_now_add=True)
    is_successful = models.BooleanField(default=True)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        db_table = "reminder_logs"
        ordering = ["-sent_at"]

    def __str__(self):
        return f"Reminder to {self.sent_to} for debt {self.debt_id} at {self.sent_at}"
