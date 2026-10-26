from django.urls import path

from . import mobile_views as views

app_name = 'chiffrage_mobile'

urlpatterns = [
    path('', views.ShellView.as_view(), name='shell'),
    path('service-worker.js', views.ServiceWorkerView.as_view(), name='service_worker'),
]
