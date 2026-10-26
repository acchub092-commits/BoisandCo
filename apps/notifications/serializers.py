from rest_framework import serializers

from .models import Notification
from .push import mobile_url_for


class NotificationSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    mobile_url = serializers.SerializerMethodField()
    type_display = serializers.CharField(source='get_notification_type_display', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'title', 'message', 'notification_type', 'type_display',
            'is_read', 'created_at', 'sender_name', 'mobile_url',
        ]

    def get_sender_name(self, obj):
        if not obj.sender:
            return None
        return obj.sender.get_full_name() or obj.sender.username

    def get_mobile_url(self, obj):
        return mobile_url_for(obj)
