from django.urls import path

from . import api_views

urlpatterns = [
    path('push-subscribe/', api_views.PushSubscribeView.as_view(), name='api_push_subscribe'),
    path('push-unsubscribe/', api_views.PushUnsubscribeView.as_view(), name='api_push_unsubscribe'),
    path('', api_views.NotificationListView.as_view(), name='api_notification_list'),
    path('unread-count/', api_views.NotificationUnreadCountView.as_view(), name='api_notification_unread_count'),
    path('read-all/', api_views.NotificationMarkReadView.as_view(), name='api_notification_read_all'),
    path('<int:pk>/read/', api_views.NotificationMarkReadView.as_view(), name='api_notification_read'),
]
