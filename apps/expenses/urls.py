from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ExpenseViewSet, DebtViewSet

# Standalone (cross-group) routes
router = DefaultRouter()
router.register(r"", ExpenseViewSet, basename="expenses")

# Nested under /api/v1/groups/{group_pk}/
nested_router = DefaultRouter()
nested_router.register(r"expenses", ExpenseViewSet, basename="group-expenses")
nested_router.register(r"debts", DebtViewSet, basename="group-debts")

urlpatterns = router.urls
