from django.views.generic import TemplateView
from django.http import Http404
from .models import ClientToken


class ClientPortalView(TemplateView):
    """
    Vue publique — aucune authentification Django requise.
    Le token UUID tient lieu de clé d'accès.
    """
    template_name = 'client_portal/portal.html'

    def get_object(self):
        try:
            ct = ClientToken.objects.select_related(
                'project',
                'project__manager',
            ).prefetch_related(
                'project__phases__tasks',
                'project__documents__category',
            ).get(token=self.kwargs['token'])
        except (ClientToken.DoesNotExist, ValueError):
            raise Http404('Lien invalide ou expiré.')

        if not ct.is_valid:
            raise Http404('Ce lien n\'est plus actif.')

        ct.record_access()
        return ct

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        client_token = self.get_object()
        context['client_token'] = client_token
        context['project'] = client_token.project
        return context
