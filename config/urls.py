from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from rest_framework.routers import DefaultRouter

from apps.expenses.views import ExpenseViewSet, DebtViewSet

from apps.users.views import AccountDetailsView, getAccountDetailsView

# Nested routes: /api/v1/groups/{group_pk}/expenses/ etc.
group_nested_router = DefaultRouter()
group_nested_router.register(r"expenses", ExpenseViewSet, basename="group-expenses")
group_nested_router.register(r"debts", DebtViewSet, basename="group-debts")

urlpatterns = [
    path("admin/", admin.site.urls),

    # Auth
    path("api/v1/auth/", include("apps.users.urls.auth")),

    # Users
    path("api/v1/users/", include("apps.users.urls.users")),

    # Accounts   
    path("api/v1/account_details/", AccountDetailsView.as_view(), name="account-details"),
        path("api/v1/account_details/<uuid:user>/", getAccountDetailsView.as_view(), name="get-account-details"),

    # Groups
    path("api/v1/groups/", include("apps.groups.urls.groups")),

    # Expenses & Debts nested under a specific group
    path("api/v1/groups/<group_pk>/", include(group_nested_router.urls)),

    # Top-level expense listing
    path("api/v1/expenses/", include("apps.expenses.urls.expenses")),

    # Payments
    path("api/v1/payments/", include("apps.payments.urls.payments")),

    # Reports
    path("api/v1/reports/", include("apps.reports.urls.reports")),

    # Reminders
    path("api/v1/reminders/", include("apps.reminders.urls.reminders")),

    # OpenAPI schema + docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]