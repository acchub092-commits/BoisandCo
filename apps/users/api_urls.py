from django.urls import path

from . import api_views

urlpatterns = [
    path('login/', api_views.LoginView.as_view(), name='api_login'),
    path('me/', api_views.MeView.as_view(), name='api_me'),
    path('logout/', api_views.LogoutView.as_view(), name='api_logout'),
]
