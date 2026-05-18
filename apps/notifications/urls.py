from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='list'),
    path('tout-lire/', views.NotificationMarkReadView.as_view(), name='mark_all_read'),
    path('<int:pk>/lire/', views.NotificationMarkReadView.as_view(), name='mark_read'),
    path('<int:pk>/voir/', views.NotificationGoView.as_view(), name='go'),
]
