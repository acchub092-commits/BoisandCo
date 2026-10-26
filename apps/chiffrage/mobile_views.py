"""Coquille de la PWA Chiffrage terrain — sert le shell HTML et le service worker
depuis /m/chiffrage/ (et non /static/…) pour que celui-ci puisse contrôler cette
portée (un service worker ne peut piloter que les pages sous son propre chemin)."""
from django.contrib.staticfiles import finders
from django.http import Http404, HttpResponse
from django.views.generic import TemplateView, View


class ShellView(TemplateView):
    template_name = 'chiffrage/mobile/index.html'

    def get_context_data(self, **kwargs):
        from django.conf import settings
        ctx = super().get_context_data(**kwargs)
        ctx['vapid_public_key'] = settings.VAPID_PUBLIC_KEY
        return ctx


class ServiceWorkerView(View):
    def get(self, request):
        path = finders.find('chiffrage_mobile/service-worker.js')
        if not path:
            raise Http404
        with open(path, 'rb') as f:
            content = f.read()
        response = HttpResponse(content, content_type='application/javascript')
        response['Service-Worker-Allowed'] = '/m/chiffrage/'
        return response
