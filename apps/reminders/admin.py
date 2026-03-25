from django.contrib import admin
from .models import ReminderLog


@admin.register(ReminderLog)
class ReminderLogAdmin(admin.ModelAdmin):
    list_display = ["sent_to", "debt", "channel", "is_successful", "sent_at"]
    list_filter = ["channel", "is_successful"]
    search_fields = ["sent_to__email"]
    readonly_fields = ["sent_at"]
