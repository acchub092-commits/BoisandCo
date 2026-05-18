from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from .models import Notification


class NotificationListView(LoginRequiredMixin, ListView):
    template_name = 'notifications/notification_list.html'
    context_object_name = 'notifications'

    def get_queryset(self):
        qs = Notification.objects.filter(
            recipient=self.request.user
        ).select_related('sender')
        if self.request.GET.get('partial') == 'badge':
            return qs.filter(is_read=False)
        return qs

    def get_template_names(self):
        if self.request.GET.get('partial') == 'badge':
            return ['notifications/_badge.html']
        return ['notifications/notification_list.html']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['unread_count'] = Notification.unread_count(self.request.user)
        return ctx


class NotificationMarkReadView(LoginRequiredMixin, View):
    """Marque une ou toutes les notifications comme lues — via HTMX."""

    def post(self, request, pk=None):
        if pk:
            try:
                notif = Notification.objects.get(pk=pk, recipient=request.user)
                notif.mark_as_read()
            except Notification.DoesNotExist:
                pass
        else:
            Notification.objects.filter(
                recipient=request.user, is_read=False
            ).update(is_read=True)
        return JsonResponse({'status': 'ok', 'unread': Notification.unread_count(request.user)})


class NotificationGoView(LoginRequiredMixin, View):
    """Marque la notification comme lue et redirige vers la page concernée."""

    def get(self, request, pk):
        notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notif.mark_as_read()
        url = notif.target_url
        return redirect(url if url else 'notifications:list')
