from rest_framework import viewsets, generics, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import User, AccountDetails
from .serializers import (
    UserRegistrationSerializer,
    UserProfileSerializer,
    UserPublicSerializer,
    ChangePasswordSerializer,
    AccountDetailsSerializer,
)


@extend_schema(tags=["auth"])
class RegisterView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "success": True,
                "message": "Account created successfully.",
                "data": UserProfileSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    list=extend_schema(tags=["users"]),
    retrieve=extend_schema(tags=["users"]),
    partial_update=extend_schema(tags=["users"]),
    me=extend_schema(tags=["users"]),
    change_password=extend_schema(tags=["users"]),
)
class UserViewSet(viewsets.GenericViewSet):
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserProfileSerializer
    search_fields = ["email", "username", "first_name", "last_name"]
    ordering_fields = ["username", "date_joined"]
    ordering = ["-date_joined"]

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=["get", "patch"])
    def me(self, request):
        if request.method == "GET":
            serializer = UserProfileSerializer(request.user)
            return Response({"success": True, "data": serializer.data})

        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"success": True, "message": "Profile updated.", "data": serializer.data})

    @action(detail=False, methods=["post"], url_path="change-password")
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response(
                {"success": False, "message": "Old password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response({"success": True, "message": "Password changed successfully."})

    def retrieve(self, request, pk=None):
        user = self.get_object()
        serializer = UserPublicSerializer(user)
        return Response({"success": True, "data": serializer.data})


class AccountDetailsView(generics.CreateAPIView):
    queryset = AccountDetails.objects.all()
    serializer_class = AccountDetailsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)
    
class getAccountDetailsView(generics.RetrieveUpdateDestroyAPIView):
    queryset = AccountDetails.objects.all()
    serializer_class = AccountDetailsSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "user"