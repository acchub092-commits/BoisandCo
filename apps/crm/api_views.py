"""
API DRF CRM — Bois&Co
Endpoints : /api/v1/crm/
"""
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.models import User
from .models import Lead, LeadNote, Activity, Appointment, LeadDocument, LeadActivityLog
from .permissions import IsCRMUser, IsDirector, CanViewLead, is_director
from .serializers import (
    LeadListSerializer, LeadDetailSerializer,
    LeadNoteSerializer, ActivitySerializer,
    AppointmentSerializer, LeadDocumentSerializer, LeadActivityLogSerializer,
)


# ─────────────────────────────────────────────────────────────────────────────
# Lead ViewSet
# ─────────────────────────────────────────────────────────────────────────────

class LeadViewSet(viewsets.ModelViewSet):
    """
    CRUD leads + actions : validate, reject, assign, submit.
    Filtre automatique selon le rôle :
      - Directeur : tous les leads.
      - Commercial : uniquement ses leads assignés.
    """
    permission_classes = [IsAuthenticated, IsCRMUser]
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        qs   = Lead.objects.select_related('assigned_to', 'created_by', 'validated_by') \
                           .prefetch_related('appointments', 'documents', 'activity_logs')
        if not is_director(user):
            qs = qs.filter(assigned_to=user)

        # Filtres query params
        status_f = self.request.query_params.get('status')
        if status_f:
            qs = qs.filter(status=status_f)

        workflow_f = self.request.query_params.get('workflow_status')
        if workflow_f:
            qs = qs.filter(workflow_status=workflow_f)

        assigned_f = self.request.query_params.get('assigned_to')
        if assigned_f and is_director(user):
            qs = qs.filter(assigned_to_id=assigned_f)

        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                project_name__icontains=search
            ) | qs.filter(
                contact_name__icontains=search
            ) | qs.filter(
                company__icontains=search
            )

        return qs.order_by('-updated_at')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return LeadDetailSerializer
        return LeadListSerializer

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            assigned_to=self.request.user if not is_director(self.request.user) else serializer.validated_data.get('assigned_to'),
        )

    # ── Actions ──────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsDirector])
    def validate(self, request, pk=None):
        """POST /api/v1/crm/leads/{pk}/validate/"""
        lead = self.get_object()
        if lead.workflow_status != Lead.WorkflowStatus.PENDING_VALIDATION:
            return Response({'detail': "Ce lead n'est pas en attente de validation."},
                            status=status.HTTP_400_BAD_REQUEST)
        lead.workflow_status = Lead.WorkflowStatus.VALIDATED
        lead.validated_by    = request.user
        lead.validated_at    = timezone.now()
        lead.save(update_fields=['workflow_status', 'validated_by', 'validated_at', 'updated_at'])
        LeadActivityLog.objects.create(
            lead=lead, log_type=LeadActivityLog.LogType.VALIDATION,
            content=f'Validé via API par {request.user.get_full_name()}.',
            performed_by=request.user,
        )
        return Response(LeadDetailSerializer(lead, context={'request': request}).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsDirector])
    def reject(self, request, pk=None):
        """POST /api/v1/crm/leads/{pk}/reject/"""
        lead    = self.get_object()
        comment = request.data.get('comment', '')
        lead.workflow_status = Lead.WorkflowStatus.DRAFT
        lead.save(update_fields=['workflow_status', 'updated_at'])
        LeadActivityLog.objects.create(
            lead=lead, log_type=LeadActivityLog.LogType.STATUS_CHANGE,
            content=f'Rejeté par {request.user.get_full_name()}. {comment}'.strip(),
            performed_by=request.user,
        )
        return Response(LeadListSerializer(lead, context={'request': request}).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsDirector])
    def assign(self, request, pk=None):
        """POST /api/v1/crm/leads/{pk}/assign/ — body: {assigned_to: user_id}"""
        lead    = self.get_object()
        user_id = request.data.get('assigned_to')
        commercial = User.objects.filter(pk=user_id).first() if user_id else None
        old = lead.assigned_to
        lead.assigned_to = commercial
        lead.save(update_fields=['assigned_to', 'updated_at'])
        LeadActivityLog.objects.create(
            lead=lead, log_type=LeadActivityLog.LogType.ASSIGNMENT,
            content=f'Assigné à {commercial.get_full_name() if commercial else "—"} (était : {old.get_full_name() if old else "—"}).',
            performed_by=request.user,
        )
        return Response(LeadListSerializer(lead, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """POST /api/v1/crm/leads/{pk}/submit/ — commercial soumet à validation"""
        lead = self.get_object()
        if lead.workflow_status != Lead.WorkflowStatus.DRAFT:
            return Response({'detail': "Ce lead n'est pas en brouillon."},
                            status=status.HTTP_400_BAD_REQUEST)
        lead.workflow_status = Lead.WorkflowStatus.PENDING_VALIDATION
        lead.source          = Lead.Source.COMMERCIAL_CREATED
        lead.save(update_fields=['workflow_status', 'source', 'updated_at'])
        LeadActivityLog.objects.create(
            lead=lead, log_type=LeadActivityLog.LogType.STATUS_CHANGE,
            content=f'Soumis à validation par {request.user.get_full_name()}.',
            performed_by=request.user,
        )
        return Response(LeadListSerializer(lead, context={'request': request}).data)


# ─────────────────────────────────────────────────────────────────────────────
# Appointment ViewSet
# ─────────────────────────────────────────────────────────────────────────────

class AppointmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsCRMUser]
    serializer_class   = AppointmentSerializer
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        qs   = Appointment.objects.select_related('lead', 'created_by') \
                                  .prefetch_related('attendees', 'documents')
        if not is_director(user):
            qs = qs.filter(lead__assigned_to=user)

        lead_id = self.request.query_params.get('lead')
        if lead_id:
            qs = qs.filter(lead_id=lead_id)
        return qs.order_by('-scheduled_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['patch'])
    def report(self, request, pk=None):
        """PATCH /api/v1/crm/appointments/{pk}/report/ — ajoute compte rendu"""
        apt    = self.get_object()
        report = request.data.get('report', '').strip()
        apt.report  = report
        apt.status  = Appointment.Status.REALISE
        if not apt.report_written_at:
            apt.report_written_at = timezone.now()
        apt.save(update_fields=['report', 'status', 'report_written_at', 'updated_at'])
        return Response(AppointmentSerializer(apt, context={'request': request}).data)


# ─────────────────────────────────────────────────────────────────────────────
# LeadDocument ViewSet
# ─────────────────────────────────────────────────────────────────────────────

class LeadDocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsCRMUser]
    serializer_class   = LeadDocumentSerializer
    http_method_names  = ['get', 'post', 'delete', 'head', 'options']  # pas d'update (immuable)

    def get_queryset(self):
        user = self.request.user
        qs   = LeadDocument.objects.select_related('lead', 'uploaded_by', 'appointment')
        if not is_director(user):
            qs = qs.filter(lead__assigned_to=user)
        lead_id = self.request.query_params.get('lead')
        if lead_id:
            qs = qs.filter(lead_id=lead_id)
        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


# ─────────────────────────────────────────────────────────────────────────────
# LeadActivityLog ViewSet (read-only + create note)
# ─────────────────────────────────────────────────────────────────────────────

class LeadActivityLogViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsCRMUser]
    serializer_class   = LeadActivityLogSerializer
    http_method_names  = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        qs   = LeadActivityLog.objects.select_related('lead', 'performed_by')
        if not is_director(user):
            qs = qs.filter(lead__assigned_to=user)
        lead_id = self.request.query_params.get('lead')
        if lead_id:
            qs = qs.filter(lead_id=lead_id)
        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(
            performed_by=self.request.user,
            log_type=serializer.validated_data.get('log_type', LeadActivityLog.LogType.NOTE),
        )
