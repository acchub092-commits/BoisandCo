from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'get_full_name', 'role', 'is_active_employee', 'is_staff')
    list_filter = ('role', 'is_active_employee', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('last_name',)

    fieldsets = UserAdmin.fieldsets + (
        ('Bois&Co', {'fields': ('role', 'phone', 'avatar', 'is_active_employee')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Bois&Co', {'fields': ('role', 'phone')}),
    )
