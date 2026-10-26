from .version import __version__


def app_version(request):
    return {"APP_VERSION": __version__}


def pose_validation_count(request):
    """Compteur de prix de pose en attente de validation DG (nav sidebar)."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    if not (user.is_superuser or getattr(user, 'role', None) in ('DIRECTEUR', 'ADMIN')):
        return {}
    from apps.projects.models_pose import Article
    count = Article.objects.filter(
        statut_validation=Article.StatutValidation.EN_ATTENTE,
        prix_de_pose__isnull=False,
    ).count()
    return {'POSE_VALIDATION_COUNT': count}


def pose_bon_validation_count(request):
    """Compteur de bons de règlement approuvés par le chef, en attente de validation DG (nav sidebar)."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    if not (user.is_superuser or getattr(user, 'role', None) in ('DIRECTEUR', 'ADMIN')):
        return {}
    from apps.projects.models_pose import BonReglement
    count = BonReglement.objects.filter(statut=BonReglement.Statut.APPROUVE_CHEF).count()
    return {'POSE_BON_VALIDATION_COUNT': count}


def pose_test_profile(request):
    """Profils de test dédiés au module pose — sidebar restreinte à la seule section Gestion de la pose."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {'IS_POSE_TEST_PROFILE': False}
    from apps.users.models import ROLES_POSE_ONLY

    is_test = getattr(user, 'role', None) in ROLES_POSE_ONLY
    return {'IS_POSE_TEST_PROFILE': is_test}
