from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.shortcuts import get_object_or_404

from .models import MonthlyReport
from .serializers import MonthlyReportSerializer, GenerateReportSerializer
from .services import ReportService
from .filters import ReportFilter
from apps.groups.models import Group


@extend_schema_view(
    list=extend_schema(tags=["reports"], summary="List my monthly reports"),
    retrieve=extend_schema(tags=["reports"], summary="Get report detail"),
)
class ReportViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MonthlyReportSerializer
    filterset_class = ReportFilter
    ordering_fields = ["year", "month", "total_spent"]
    ordering = ["-year", "-month"]

    def get_queryset(self):
        return ReportService.get_user_reports(self.request.user).select_related("group")

    @extend_schema(tags=["reports"], summary="Generate / refresh a monthly report")
    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        serializer = GenerateReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        group_id = data.get("group_id")
        year = data["year"]
        month = data["month"]

        if group_id:
            group = get_object_or_404(Group, pk=group_id, is_active=True)
            report = ReportService.generate_for_user_group(request.user, group, year, month)
            reports = [report]
        else:
            reports = ReportService.generate_for_all_groups(request.user, year, month)

        out = MonthlyReportSerializer(reports, many=True)
        return Response(
            {
                "success": True,
                "message": f"Generated {len(reports)} report(s).",
                "data": out.data,
            },
            status=status.HTTP_200_OK,
        )
