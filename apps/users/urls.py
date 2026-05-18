from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('', views.UserListView.as_view(), name='list'),
    path('nouveau/', views.UserCreateView.as_view(), name='create'),
    path('<int:pk>/', views.UserDetailView.as_view(), name='detail'),
    path('<int:pk>/modifier/', views.UserUpdateView.as_view(), name='update'),
    path('<int:pk>/toggle-actif/', views.UserToggleActiveView.as_view(), name='toggle_active'),
]
