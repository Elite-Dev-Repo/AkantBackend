import django_filters
from .models import Payment


class PaymentFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=Payment.Status.choices)
    created_after = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    min_amount = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    max_amount = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")
    recipient = django_filters.UUIDFilter(field_name="recipient__id")

    class Meta:
        model = Payment
        fields = ["status", "created_after", "created_before", "min_amount", "max_amount", "recipient"]
