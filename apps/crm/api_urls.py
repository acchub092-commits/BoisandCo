from rest_framework.routers import DefaultRouter
from . import api_views

router = DefaultRouter()
router.register(r'leads',         api_views.LeadViewSet,            basename='lead')
router.register(r'appointments',  api_views.AppointmentViewSet,     basename='appointment')
router.register(r'documents',     api_views.LeadDocumentViewSet,    basename='lead-document')
router.register(r'logs',          api_views.LeadActivityLogViewSet, basename='lead-log')

urlpatterns = router.urls
