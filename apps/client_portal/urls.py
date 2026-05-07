from django.urls import path
from . import views

app_name = 'client_portal'

urlpatterns = [
    path('<str:token>/', views.ClientPortalView.as_view(), name='portal'),
]
