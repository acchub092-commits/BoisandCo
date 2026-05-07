from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'recipient', 'notification_type', 'is_read', 'created_at',
    )
    list_filter = ('notification_type', 'is_read')
    search_fields = ('title', 'recipient__email', 'message')
    readonly_fields = ('created_at', 'read_at')
    actions = ['mark_as_read']

    @admin.action(description='Marquer comme lues')
    def mark_as_read(self, request, queryset):
        for notif in queryset.filter(is_read=False):
            notif.mark_as_read()
