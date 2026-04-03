from rest_framework import viewsets, generics, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import User, AccountDetails
from .serializers import (
    UserRegistrationSerializer, UserProfileSerializer,
    UserPublicSerializer, ChangePasswordSerializer,
    AccountDetailsSerializer, AccountDetailsWriteSerializer,
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
            {"success": True, "message": "Account created successfully.", "data": UserProfileSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    me=extend_schema(tags=["users"]),
    change_password=extend_schema(tags=["users"]),
    retrieve=extend_schema(tags=["users"]),
)
class UserViewSet(viewsets.GenericViewSet):
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserProfileSerializer
    search_fields = ["email", "username", "first_name", "last_name"]

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=["get", "patch"])
    def me(self, request):
        if request.method == "GET":
            return Response({"success": True, "data": UserProfileSerializer(request.user).data})
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
            return Response({"success": False, "message": "Old password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response({"success": True, "message": "Password changed successfully."})

    def retrieve(self, request, pk=None):
        user = self.get_object()
        return Response({"success": True, "data": UserPublicSerializer(user).data})


class AccountDetailsViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return AccountDetails.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return AccountDetailsWriteSerializer
        return AccountDetailsSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        # One account per user — update existing if found
        existing = AccountDetails.objects.filter(user=request.user).first()
        if existing:
            serializer = AccountDetailsWriteSerializer(
                existing, data=request.data, partial=False
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(
                {"success": True, "message": "Account details updated.", "data": serializer.data}
            )
        serializer = AccountDetailsWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(
            {"success": True, "message": "Account details saved.", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(
            {"success": True, "message": "Account details removed."},
            status=status.HTTP_200_OK,
        )