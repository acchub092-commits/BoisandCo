from rest_framework.routers import DefaultRouter

from .api_views import DemandeChiffrageViewSet

router = DefaultRouter()
router.register(r'demandes', DemandeChiffrageViewSet, basename='demande-chiffrage')

urlpatterns = router.urls
