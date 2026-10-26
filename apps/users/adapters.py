from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse

from .models import ROLES_POSE_ONLY


class AccountAdapter(DefaultAccountAdapter):
    """Redirection post-connexion : les rôles confinés au module Gestion de la pose
    (ROLES_POSE_ONLY) n'ont aucun accès utile au module Projets classique (LOGIN_REDIRECT_URL),
    qui leur affiche une liste vide — direction Pipeline pose à la place."""

    def get_login_redirect_url(self, request):
        if getattr(request.user, 'role', None) in ROLES_POSE_ONLY:
            return reverse('projects:pose_gestion_pipeline')
        return super().get_login_redirect_url(request)
