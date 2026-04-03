from rest_framework.routers import DefaultRouter
from apps.users.views import UserViewSet, AccountDetailsViewSet

router = DefaultRouter()
# Change r"" to r"profiles" or r"manage"
router.register(r"account-details", AccountDetailsViewSet, basename="account-details")
router.register(r"", UserViewSet, basename="users")

urlpatterns = router.urls