from django.contrib import admin
from django.utils.html import format_html
from .models import ClientToken


@admin.register(ClientToken)
class ClientTokenAdmin(admin.ModelAdmin):
    list_display = (
        'project', 'token_short', 'is_active', 'is_valid',
        'access_count', 'last_accessed', 'expires_at',
    )
    list_filter = ('is_active',)
    search_fields = ('project__reference', 'project__name')
    readonly_fields = (
        'token', 'created_at', 'last_accessed', 'access_count', 'portal_link',
    )
    fieldsets = (
        ('Projet', {'fields': ('project', 'portal_link')}),
        ('Accès', {'fields': ('token', 'is_active', 'expires_at')}),
        ('Visibilité client', {'fields': ('show_phases', 'show_tasks', 'show_documents')}),
        ('Statistiques', {'fields': ('access_count', 'last_accessed', 'created_at')}),
    )

    @admin.display(description='Token')
    def token_short(self, obj):
        return str(obj.token)[:8] + '…'

    @admin.display(description='Lien portail')
    def portal_link(self, obj):
        url = obj.get_absolute_url()
        return format_html('<a href="{}" target="_blank">{}</a>', url, url)
