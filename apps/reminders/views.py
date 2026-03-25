from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import ReminderLog
from .serializers import ReminderLogSerializer, SendReminderSerializer
from .tasks import send_single_reminder


@extend_schema_view(
    list=extend_schema(tags=["reminders"], summary="List reminder logs"),
    retrieve=extend_schema(tags=["reminders"], summary="Get reminder log detail"),
)
class ReminderViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ReminderLogSerializer
    ordering_fields = ["sent_at"]
    ordering = ["-sent_at"]

    def get_queryset(self):
        return ReminderLog.objects.filter(
            sent_to=self.request.user
        ).select_related("debt__group", "sent_to")

    @extend_schema(tags=["reminders"], summary="Send a reminder for a specific debt")
    @action(detail=False, methods=["post"], url_path="send")
    def send(self, request):
        serializer = SendReminderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        debt_id = str(serializer.validated_data["debt_id"])

        # Verify the requesting user is the creditor of this debt
        from apps.expenses.models import Debt
        try:
            debt = Debt.objects.get(id=debt_id, is_settled=False)
        except Debt.DoesNotExist:
            return Response(
                {"success": False, "message": "Debt not found or already settled."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if debt.creditor != request.user:
            return Response(
                {"success": False, "message": "Only the creditor can send reminders."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Dispatch async task
        send_single_reminder.delay(debt_id)

        return Response(
            {"success": True, "message": "Reminder queued successfully."},
            status=status.HTTP_202_ACCEPTED,
        )
