from django.contrib import admin
from .models import MonthlyReport


@admin.register(MonthlyReport)
class MonthlyReportAdmin(admin.ModelAdmin):
    list_display = ["user", "group", "year", "month", "total_spent", "expense_count", "created_at"]
    list_filter = ["year", "month"]
    search_fields = ["user__email", "group__name"]
    readonly_fields = ["created_at", "updated_at"]
