from rest_framework.routers import DefaultRouter
from apps.expenses.views import ExpenseViewSet

router = DefaultRouter()
router.register(r"", ExpenseViewSet, basename="expenses")

urlpatterns = router.urls