from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, AccountDetails


class AccountDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountDetails
        fields = ["id", "account_name", "account_number", "bank_name"]
        read_only_fields = ["id"]


class AccountDetailsWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountDetails
        fields = ["id", "account_name", "account_number", "bank_name"]
        read_only_fields = ["id"]


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "username", "first_name", "last_name", "phone", "password", "password_confirm"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ["id", "email", "username", "first_name", "last_name", "full_name", "phone", "avatar", "date_joined"]
        read_only_fields = ["id", "email", "date_joined"]


class UserPublicSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ["id", "username", "full_name", "avatar"]


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "Passwords do not match."})
        return attrs