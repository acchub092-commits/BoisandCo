from django.http import HttpResponseForbidden

SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')

# Chemins exemptés même pour le rôle Consultation : gestion de son propre
# compte (connexion/déconnexion/mot de passe/e-mail), pas une "action métier".
EXEMPT_PATH_PREFIXES = ('/accounts/',)


class ConsultationReadOnlyMiddleware:
    """Bloque toute requête d'écriture (POST/PUT/PATCH/DELETE) pour le rôle
    Consultation, quel que soit le module — garde-fou global qui ne dépend pas
    de ce que chaque vue vérifie individuellement."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if (
            user is not None and user.is_authenticated
            and getattr(user, 'role', None) == 'CONSULTATION'
            and not user.is_superuser
            and request.method not in SAFE_METHODS
            and not request.path.startswith(EXEMPT_PATH_PREFIXES)
        ):
            return HttpResponseForbidden(
                "Votre profil est en consultation seule — aucune action n'est autorisée."
            )
        return self.get_response(request)
