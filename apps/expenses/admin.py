from django.contrib import admin
from .models import Expense, ExpenseSplit, Debt


class ExpenseSplitInline(admin.TabularInline):
    model = ExpenseSplit
    extra = 0
    readonly_fields = ["created_at", "paid_at"]
    fields = ["user", "amount_owed", "is_paid", "paid_at"]


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ["title", "group", "amount", "currency", "paid_by", "date", "is_settled", "created_at"]
    list_filter = ["category", "split_type", "is_settled", "currency"]
    search_fields = ["title", "description", "group__name"]
    inlines = [ExpenseSplitInline]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "date"


@admin.register(ExpenseSplit)
class ExpenseSplitAdmin(admin.ModelAdmin):
    list_display = ["expense", "user", "amount_owed", "is_paid", "paid_at"]
    list_filter = ["is_paid"]
    search_fields = ["expense__title", "user__email"]


@admin.register(Debt)
class DebtAdmin(admin.ModelAdmin):
    list_display = ["debtor", "creditor", "group", "amount", "is_settled", "settled_at"]
    list_filter = ["is_settled"]
    search_fields = ["debtor__email", "creditor__email", "group__name"]
    readonly_fields = ["created_at", "updated_at"]
