from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.shortcuts import get_object_or_404

from .models import Expense, ExpenseSplit, Debt
from .serializers import (
    ExpenseSerializer,
    ExpenseCreateSerializer,
    ExpenseSplitSerializer,
    DebtSerializer,
    GroupBalanceSummarySerializer,
)
from .services import ExpenseService
from .balance import BalanceService
from .filters import ExpenseFilter, DebtFilter
from apps.groups.models import Group, GroupMembership


def _assert_group_member(group, user):
    if not GroupMembership.objects.filter(group=group, user=user, is_active=True).exists():
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied("You are not a member of this group.")


@extend_schema_view(
    list=extend_schema(tags=["expenses"], summary="List group expenses"),
    create=extend_schema(tags=["expenses"], summary="Create expense"),
    retrieve=extend_schema(tags=["expenses"], summary="Get expense"),
    update=extend_schema(tags=["expenses"], summary="Update expense"),
    partial_update=extend_schema(tags=["expenses"], summary="Partial update expense"),
    destroy=extend_schema(tags=["expenses"], summary="Delete expense"),
)
class ExpenseViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = ExpenseFilter
    search_fields = ["title", "description"]
    ordering_fields = ["date", "amount", "created_at"]
    ordering = ["-date"]

    def get_queryset(self):
        group_pk = self.kwargs.get("group_pk")
        if group_pk:
            group = get_object_or_404(Group, pk=group_pk, is_active=True)
            _assert_group_member(group, self.request.user)
            return Expense.objects.filter(group=group).select_related(
                "paid_by", "created_by"
            ).prefetch_related("splits__user")
        # Fallback: all expenses in groups the user belongs to
        return Expense.objects.filter(
            group__memberships__user=self.request.user,
            group__memberships__is_active=True,
        ).select_related("paid_by", "created_by").prefetch_related("splits__user").distinct()

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return ExpenseCreateSerializer
        return ExpenseSerializer

    def create(self, request, *args, **kwargs):
        group_pk = self.kwargs.get("group_pk")
        group = get_object_or_404(Group, pk=group_pk, is_active=True)
        _assert_group_member(group, request.user)

        serializer = ExpenseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            expense = ExpenseService.create_expense(
    group=group,
    title=data["title"],
    amount=data["amount"],
    paid_by=data["paid_by_id"],
    date=data["date"],
    split_type=data.get("split_type", Expense.SplitType.EQUAL),
    description=data.get("description", ""),
    category=data.get("category", Expense.Category.OTHER),
    currency=data.get("currency", "NGN"),
    receipt=data.get("receipt"),
    split_data=data.get("split_data"),
    created_by=request.user,
)
        except ValueError as e:
            return Response({"success": False, "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        out = ExpenseSerializer(expense, context={"request": request})
        return Response(
            {"success": True, "message": "Expense created.", "data": out.data},
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        expense = self.get_object()
        try:
            ExpenseService.delete_expense(str(expense.id), request.user)
        except PermissionError as e:
            return Response({"success": False, "message": str(e)}, status=status.HTTP_403_FORBIDDEN)
        return Response({"success": True, "message": "Expense deleted."})

    @extend_schema(tags=["expenses"], summary="Mark a split as paid")
    @action(detail=True, methods=["post"], url_path="splits/(?P<split_pk>[^/.]+)/pay")
    def mark_split_paid(self, request, pk=None, split_pk=None, **kwargs):
        try:
            split = ExpenseService.mark_split_paid(split_pk, request.user)
        except (ExpenseSplit.DoesNotExist, ValueError) as e:
            return Response({"success": False, "message": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except PermissionError as e:
            return Response({"success": False, "message": str(e)}, status=status.HTTP_403_FORBIDDEN)
        return Response({"success": True, "message": "Split marked as paid.", "data": ExpenseSplitSerializer(split).data})


@extend_schema_view(
    list=extend_schema(tags=["expenses"], summary="List group debts"),
    retrieve=extend_schema(tags=["expenses"], summary="Get debt detail"),
)
class DebtViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DebtSerializer
    filterset_class = DebtFilter
    ordering_fields = ["amount", "created_at"]
    ordering = ["-amount"]

    def get_queryset(self):
        group_pk = self.kwargs.get("group_pk")
        if group_pk:
            group = get_object_or_404(Group, pk=group_pk, is_active=True)
            _assert_group_member(group, self.request.user)
            return Debt.objects.filter(group=group).select_related("debtor", "creditor")
        return Debt.objects.filter(
            group__memberships__user=self.request.user,
            group__memberships__is_active=True,
        ).select_related("debtor", "creditor").distinct()

    @extend_schema(tags=["expenses"], summary="Settle a debt manually")
    @action(detail=True, methods=["post"], url_path="settle")
    def settle(self, request, pk=None, **kwargs):
        try:
            debt = ExpenseService.settle_debt(pk, request.user)
        except Debt.DoesNotExist:
            return Response({"success": False, "message": "Debt not found."}, status=status.HTTP_404_NOT_FOUND)
        except PermissionError as e:
            return Response({"success": False, "message": str(e)}, status=status.HTTP_403_FORBIDDEN)
        return Response({"success": True, "message": "Debt settled.", "data": DebtSerializer(debt).data})

    @extend_schema(tags=["expenses"], summary="My balance summary in a group")
    @action(detail=False, methods=["get"], url_path="my-balance")
    def my_balance(self, request, group_pk=None, **kwargs):
        group = get_object_or_404(Group, pk=group_pk, is_active=True)
        _assert_group_member(group, request.user)
        summary = BalanceService.user_balance_in_group(group, request.user)
        serializer = GroupBalanceSummarySerializer(summary)
        return Response({"success": True, "data": serializer.data})
