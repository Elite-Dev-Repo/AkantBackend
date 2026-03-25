"""
Signal: after an Expense is created with split_type=EQUAL,
automatically create ExpenseSplit rows for all active group members.
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Expense, ExpenseSplit
from apps.groups.models import GroupMembership


@receiver(post_save, sender=Expense)
def create_equal_splits(sender, instance: Expense, created: bool, **kwargs):
    if not created:
        return
    if instance.split_type != Expense.SplitType.EQUAL:
        return
    # If splits were already created (custom), skip
    if instance.splits.exists():
        return

    members = GroupMembership.objects.filter(
        group=instance.group, is_active=True
    ).select_related("user")

    member_count = members.count()
    if member_count == 0:
        return

    share = (instance.amount / member_count).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # Handle rounding remainder
    remainder = instance.amount - (share * member_count)

    splits = []
    for idx, membership in enumerate(members):
        amount = share + (remainder if idx == 0 else Decimal("0.00"))
        splits.append(
            ExpenseSplit(
                expense=instance,
                user=membership.user,
                amount_owed=amount,
            )
        )

    ExpenseSplit.objects.bulk_create(splits, ignore_conflicts=True)
