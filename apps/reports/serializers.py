from rest_framework import serializers
from .models import MonthlyReport


class MonthlyReportSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = MonthlyReport
        fields = [
            "id", "group", "group_name", "year", "month",
            "total_spent", "total_paid", "total_owed",
            "total_received", "expense_count",
            "category_breakdown", "created_at", "updated_at",
        ]
        read_only_fields = fields


class GenerateReportSerializer(serializers.Serializer):
    group_id = serializers.UUIDField(required=False)
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    month = serializers.IntegerField(min_value=1, max_value=12)
