import django_filters
from .models import Group


class GroupFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    created_after = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = Group
        fields = ["name", "is_active", "created_after", "created_before"]
