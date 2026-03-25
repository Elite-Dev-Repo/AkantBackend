import django_filters
from .models import Expense, Debt


class ExpenseFilter(django_filters.FilterSet):
    title = django_filters.CharFilter(lookup_expr="icontains")
    category = django_filters.ChoiceFilter(choices=Expense.Category.choices)
    split_type = django_filters.ChoiceFilter(choices=Expense.SplitType.choices)
    is_settled = django_filters.BooleanFilter()
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    min_amount = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    max_amount = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")
    paid_by = django_filters.UUIDFilter(field_name="paid_by__id")

    class Meta:
        model = Expense
        fields = [
            "title", "category", "split_type", "is_settled",
            "date_from", "date_to", "min_amount", "max_amount", "paid_by",
        ]


class DebtFilter(django_filters.FilterSet):
    is_settled = django_filters.BooleanFilter()
    debtor = django_filters.UUIDFilter(field_name="debtor__id")
    creditor = django_filters.UUIDFilter(field_name="creditor__id")

    class Meta:
        model = Debt
        fields = ["is_settled", "debtor", "creditor"]
