"""
Factory Boy factories for all models.
Used across the entire test suite.
"""
import factory
from factory.django import DjangoModelFactory
from django.utils import timezone
from decimal import Decimal
import datetime

from apps.users.models import User
from apps.groups.models import Group, GroupMembership, GroupInvite
from apps.expenses.models import Expense, ExpenseSplit, Debt
from apps.payments.models import Payment
from apps.reports.models import MonthlyReport
from apps.reminders.models import ReminderLog


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@Akant.test")
    username = factory.Sequence(lambda n: f"user{n}")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    password = factory.PostGenerationMethodCall("set_password", "TestPass123!")
    is_active = True


class GroupFactory(DjangoModelFactory):
    class Meta:
        model = Group

    name = factory.Faker("company")
    description = factory.Faker("sentence")
    created_by = factory.SubFactory(UserFactory)
    is_active = True


class GroupMembershipFactory(DjangoModelFactory):
    class Meta:
        model = GroupMembership

    group = factory.SubFactory(GroupFactory)
    user = factory.SubFactory(UserFactory)
    role = GroupMembership.Role.MEMBER
    is_active = True


class GroupInviteFactory(DjangoModelFactory):
    class Meta:
        model = GroupInvite

    group = factory.SubFactory(GroupFactory)
    invited_by = factory.SubFactory(UserFactory)
    invited_email = factory.Faker("email")
    expires_at = factory.LazyFunction(lambda: timezone.now() + datetime.timedelta(days=7))
    status = GroupInvite.Status.PENDING


class ExpenseFactory(DjangoModelFactory):
    class Meta:
        model = Expense

    group = factory.SubFactory(GroupFactory)
    title = factory.Faker("sentence", nb_words=4)
    description = factory.Faker("sentence")
    amount = factory.LazyFunction(lambda: Decimal("100.00"))
    currency = "NGN"
    category = Expense.Category.FOOD
    split_type = Expense.SplitType.EQUAL
    paid_by = factory.SubFactory(UserFactory)
    date = factory.LazyFunction(lambda: datetime.date.today())
    is_settled = False
    created_by = factory.SelfAttribute("paid_by")


class ExpenseSplitFactory(DjangoModelFactory):
    class Meta:
        model = ExpenseSplit

    expense = factory.SubFactory(ExpenseFactory)
    user = factory.SubFactory(UserFactory)
    amount_owed = factory.LazyFunction(lambda: Decimal("50.00"))
    is_paid = False


class DebtFactory(DjangoModelFactory):
    class Meta:
        model = Debt

    group = factory.SubFactory(GroupFactory)
    debtor = factory.SubFactory(UserFactory)
    creditor = factory.SubFactory(UserFactory)
    amount = factory.LazyFunction(lambda: Decimal("100.00"))
    is_settled = False


class PaymentFactory(DjangoModelFactory):
    class Meta:
        model = Payment

    debt = factory.SubFactory(DebtFactory)
    payer = factory.SubFactory(UserFactory)
    recipient = factory.SubFactory(UserFactory)
    amount = factory.LazyFunction(lambda: Decimal("100.00"))
    currency = "NGN"
    reference = factory.Sequence(lambda n: f"Akant_test_ref_{n:06d}")
    status = Payment.Status.PENDING


class MonthlyReportFactory(DjangoModelFactory):
    class Meta:
        model = MonthlyReport

    user = factory.SubFactory(UserFactory)
    group = factory.SubFactory(GroupFactory)
    year = 2024
    month = 1
    total_spent = Decimal("500.00")
    total_paid = Decimal("600.00")
    total_owed = Decimal("300.00")
    total_received = Decimal("400.00")
    expense_count = 5


class ReminderLogFactory(DjangoModelFactory):
    class Meta:
        model = ReminderLog

    debt = factory.SubFactory(DebtFactory)
    sent_to = factory.SubFactory(UserFactory)
    channel = ReminderLog.Channel.EMAIL
    is_successful = True
