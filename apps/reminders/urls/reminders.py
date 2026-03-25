from rest_framework.routers import DefaultRouter
from apps.reminders.views import ReminderViewSet

router = DefaultRouter()
router.register(r"", ReminderViewSet, basename="reminders")

urlpatterns = router.urls