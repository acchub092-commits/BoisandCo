"""
Serializers DRF — CRM Bois&Co
"""
from rest_framework import serializers
from apps.users.models import User
from .models import Lead, LeadNote, Activity, Appointment, LeadDocument, LeadActivityLog


# ─────────────────────────────────────────────────────────────────────────────
# User compact
# ─────────────────────────────────────────────────────────────────────────────

class UserCompactSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = ['id', 'full_name', 'role', 'email']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


# ─────────────────────────────────────────────────────────────────────────────
# LeadNote
# ─────────────────────────────────────────────────────────────────────────────

class LeadNoteSerializer(serializers.ModelSerializer):
    author = UserCompactSerializer(read_only=True)

    class Meta:
        model  = LeadNote
        fields = ['id', 'text', 'author', 'created_at']
        read_only_fields = ['author', 'created_at']


# ─────────────────────────────────────────────────────────────────────────────
# LeadDocument
# ─────────────────────────────────────────────────────────────────────────────

class LeadDocumentSerializer(serializers.ModelSerializer):
    uploaded_by = UserCompactSerializer(read_only=True)
    file_url    = serializers.SerializerMethodField()
    extension   = serializers.CharField(read_only=True)
    is_image    = serializers.BooleanField(read_only=True)

    class Meta:
        model  = LeadDocument
        fields = [
            'id', 'lead', 'appointment', 'doc_type', 'title', 'description',
            'file', 'file_url', 'extension', 'is_image', 'uploaded_by', 'created_at',
        ]
        read_only_fields = ['uploaded_by', 'created_at', 'file_url', 'extension', 'is_image']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# LeadActivityLog
# ─────────────────────────────────────────────────────────────────────────────

class LeadActivityLogSerializer(serializers.ModelSerializer):
    performed_by = UserCompactSerializer(read_only=True)

    class Meta:
        model  = LeadActivityLog
        fields = ['id', 'log_type', 'content', 'performed_by', 'created_at']
        read_only_fields = ['performed_by', 'created_at']


# ─────────────────────────────────────────────────────────────────────────────
# Appointment
# ─────────────────────────────────────────────────────────────────────────────

class AppointmentSerializer(serializers.ModelSerializer):
    created_by = UserCompactSerializer(read_only=True)
    attendees  = UserCompactSerializer(many=True, read_only=True)
    documents  = LeadDocumentSerializer(many=True, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    status_color = serializers.CharField(read_only=True)

    class Meta:
        model  = Appointment
        fields = [
            'id', 'lead', 'title', 'appointment_type', 'scheduled_at',
            'duration_minutes', 'location', 'attendees', 'status',
            'report', 'report_written_at', 'created_by', 'created_at',
            'updated_at', 'is_overdue', 'status_color', 'documents',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']


# ─────────────────────────────────────────────────────────────────────────────
# Lead — version liste (allégée)
# ─────────────────────────────────────────────────────────────────────────────

class LeadListSerializer(serializers.ModelSerializer):
    assigned_to     = UserCompactSerializer(read_only=True)
    created_by      = UserCompactSerializer(read_only=True)
    status_display  = serializers.CharField(source='get_status_display', read_only=True)
    workflow_display = serializers.CharField(source='get_workflow_status_display', read_only=True)
    potential_color = serializers.CharField(read_only=True)
    is_active       = serializers.BooleanField(read_only=True)
    nb_appointments = serializers.SerializerMethodField()
    nb_documents    = serializers.SerializerMethodField()

    class Meta:
        model  = Lead
        fields = [
            'id', 'project_name', 'contact_name', 'company', 'email', 'phone',
            'location', 'status', 'status_display', 'workflow_status', 'workflow_display',
            'potential', 'potential_color', 'budget_mad', 'probability',
            'assigned_to', 'created_by', 'is_active',
            'nb_appointments', 'nb_documents',
            'created_at', 'updated_at',
        ]

    def get_nb_appointments(self, obj):
        return obj.appointments.count()

    def get_nb_documents(self, obj):
        return obj.documents.count()


# ─────────────────────────────────────────────────────────────────────────────
# Lead — version détail (complète)
# ─────────────────────────────────────────────────────────────────────────────

class LeadDetailSerializer(LeadListSerializer):
    notes        = LeadNoteSerializer(many=True, read_only=True)
    appointments = AppointmentSerializer(many=True, read_only=True)
    documents    = LeadDocumentSerializer(many=True, read_only=True)
    activity_logs = LeadActivityLogSerializer(many=True, read_only=True)
    validated_by = UserCompactSerializer(read_only=True)

    class Meta(LeadListSerializer.Meta):
        fields = LeadListSerializer.Meta.fields + [
            'client_type', 'project_type', 'products',
            'canal_origine', 'flux_type', 'source',
            'detailed_needs', 'technical_notes',
            'strategic_comment', 'competitor',
            'offer_amount_ht', 'offer_sent_date', 'offer_validity_days',
            'nb_logements', 'start_date_est', 'end_date_est',
            'validated_by', 'validated_at',
            'notes', 'appointments', 'documents', 'activity_logs',
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Activity (agenda)
# ─────────────────────────────────────────────────────────────────────────────

class ActivitySerializer(serializers.ModelSerializer):
    assigned_to = UserCompactSerializer(read_only=True)
    is_overdue  = serializers.BooleanField(read_only=True)
    icon_path   = serializers.CharField(read_only=True)

    class Meta:
        model  = Activity
        fields = [
            'id', 'lead', 'activity_type', 'subject', 'planned_at',
            'duration_min', 'location', 'assigned_to', 'status',
            'compte_rendu', 'is_overdue', 'icon_path',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
