from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from rest_framework.routers import DefaultRouter
from apps.expenses.views import ExpenseViewSet, DebtViewSet

group_nested_router = DefaultRouter()
group_nested_router.register(r"expenses", ExpenseViewSet, basename="group-expenses")
group_nested_router.register(r"debts", DebtViewSet, basename="group-debts")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.users.urls.auth")),
    path("api/v1/users/", include("apps.users.urls.users")),
    path("api/v1/groups/", include("apps.groups.urls.groups")),
    path("api/v1/groups/<group_pk>/", include(group_nested_router.urls)),
    path("api/v1/expenses/", include("apps.expenses.urls.expenses")),
    path("api/v1/payments/", include("apps.payments.urls.payments")),
    path("api/v1/reports/", include("apps.reports.urls.reports")),
    path("api/v1/reminders/", include("apps.reminders.urls.reminders")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]