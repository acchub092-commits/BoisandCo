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

    def render_to_response(self, context, **kwargs):
        response = super().render_to_response(context, **kwargs)
        # Les navigateurs mettent en cache le shell PWA de façon agressive — on force
        # la revalidation à chaque chargement pour que les mises à jour (JS/CSS versionnés
        # dans la manifeste static) soient détectées immédiatement.
        response['Cache-Control'] = 'no-cache'
        return response


class ServiceWorkerView(View):
    def get(self, request):
        path = finders.find('chiffrage_mobile/service-worker.js')
        if not path:
            raise Http404
        with open(path, 'rb') as f:
            content = f.read()
        response = HttpResponse(content, content_type='application/javascript')
        response['Service-Worker-Allowed'] = '/m/chiffrage/'
        # Sans ceci, les navigateurs appliquent un cache plancher de 24h sur ce fichier
        # précis — une mise à jour pourrait ne jamais être détectée avant ce délai,
        # même après une désinstallation/réinstallation de l'app.
        response['Cache-Control'] = 'no-cache'
        return response
