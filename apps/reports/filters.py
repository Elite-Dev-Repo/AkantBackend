import django_filters
from .models import MonthlyReport


class ReportFilter(django_filters.FilterSet):
    year = django_filters.NumberFilter()
    month = django_filters.NumberFilter()
    group = django_filters.UUIDFilter(field_name="group__id")

    class Meta:
        model = MonthlyReport
        fields = ["year", "month", "group"]
