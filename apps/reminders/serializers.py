from rest_framework import serializers
from .models import ReminderLog
from apps.users.serializers import UserPublicSerializer


class ReminderLogSerializer(serializers.ModelSerializer):
    sent_to = UserPublicSerializer(read_only=True)

    class Meta:
        model = ReminderLog
        fields = ["id", "debt", "sent_to", "channel", "sent_at", "is_successful", "error_message"]
        read_only_fields = fields


class SendReminderSerializer(serializers.Serializer):
    debt_id = serializers.UUIDField()
