from rest_framework import serializers
from .models import Expense, ExpenseSplit, Debt
from apps.users.serializers import UserPublicSerializer


class ExpenseSplitSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)

    class Meta:
        model = ExpenseSplit
        fields = ["id", "user", "amount_owed", "is_paid", "paid_at", "created_at"]
        read_only_fields = ["id", "created_at"]


class SplitInputSerializer(serializers.Serializer):
    """Used for EXACT or PERCENTAGE split creation."""
    user_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    percentage = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)


class ExpenseSerializer(serializers.ModelSerializer):
    paid_by = UserPublicSerializer(read_only=True)
    created_by = UserPublicSerializer(read_only=True)
    splits = ExpenseSplitSerializer(many=True, read_only=True)

    class Meta:
        model = Expense
        fields = [
            "id", "group", "title", "description", "amount", "currency",
            "category", "split_type", "paid_by", "created_by",
            "receipt", "date", "is_settled", "splits",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "is_settled", "created_at", "updated_at"]


class ExpenseCreateSerializer(serializers.ModelSerializer):
    paid_by_id = serializers.UUIDField()
    split_data = SplitInputSerializer(many=True, required=False)

    class Meta:
        model = Expense
        fields = [
            "title", "description", "amount", "currency",
            "category", "split_type", "paid_by_id",
            "receipt", "date", "split_data",
        ]

    def validate(self, attrs):
        split_type = attrs.get("split_type", Expense.SplitType.EQUAL)
        split_data = attrs.get("split_data")
        if split_type != Expense.SplitType.EQUAL and not split_data:
            raise serializers.ValidationError(
                {"split_data": "split_data is required for non-equal splits."}
            )
        return attrs


class DebtSerializer(serializers.ModelSerializer):
    debtor = UserPublicSerializer(read_only=True)
    creditor = UserPublicSerializer(read_only=True)

    class Meta:
        model = Debt
        fields = [
            "id", "group", "debtor", "creditor",
            "amount", "is_settled", "settled_at",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class BalanceDetailSerializer(serializers.Serializer):
    user = UserPublicSerializer()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    direction = serializers.ChoiceField(choices=["owes_you", "you_owe"])
    debt_id = serializers.UUIDField()


class GroupBalanceSummarySerializer(serializers.Serializer):
    total_owed_to_you = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_you_owe = serializers.DecimalField(max_digits=12, decimal_places=2)
    net = serializers.DecimalField(max_digits=12, decimal_places=2)
    details = BalanceDetailSerializer(many=True)
