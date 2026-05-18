"""URLs principales du projet Bois&Co."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('__reload__/', include('django_browser_reload.urls')),

    # Apps locales — seront complétées aux étapes suivantes
    path('', include('apps.projects.urls', namespace='projects')),
    path('users/', include('apps.users.urls', namespace='users')),
    path('documents/', include('apps.documents.urls', namespace='documents')),
    path('notifications/', include('apps.notifications.urls', namespace='notifications')),
    path('suivi/', include('apps.client_portal.urls', namespace='client_portal')),
    path('crm/', include('apps.crm.urls', namespace='crm')),
    path('api/v1/crm/', include('apps.crm.api_urls')),
    path('', include('apps.workflows.urls', namespace='workflows')),
    path('chiffrage/', include('apps.chiffrage.urls', namespace='chiffrage')),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
