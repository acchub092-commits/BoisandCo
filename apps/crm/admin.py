from django.contrib import admin
from django.utils.html import format_html

from .models import Lead, LeadNote, Activity, Appointment, LeadDocument, LeadActivityLog


# ─────────────────────────────────────────────────────────────────────────────
# Inlines
# ─────────────────────────────────────────────────────────────────────────────

class LeadNoteInline(admin.TabularInline):
    model           = LeadNote
    extra           = 0
    readonly_fields = ['author', 'created_at']
    fields          = ['author', 'text', 'created_at']


class AppointmentInline(admin.TabularInline):
    model            = Appointment
    extra            = 0
    fields           = ['title', 'appointment_type', 'scheduled_at', 'duration_minutes', 'status']
    readonly_fields  = ['status']
    show_change_link = True


class LeadDocumentInline(admin.TabularInline):
    model           = LeadDocument
    extra           = 0
    fields          = ['doc_type', 'title', 'file', 'uploaded_by', 'created_at']
    readonly_fields = ['uploaded_by', 'created_at']


class LeadActivityLogInline(admin.TabularInline):
    model           = LeadActivityLog
    extra           = 0
    readonly_fields = ['log_type', 'content', 'performed_by', 'created_at']
    fields          = ['log_type', 'content', 'performed_by', 'created_at']
    can_delete      = False

    def has_add_permission(self, request, obj=None):
        return False


class AppointmentDocumentInline(admin.TabularInline):
    model               = LeadDocument
    extra               = 0
    fields              = ['doc_type', 'title', 'file', 'uploaded_by', 'created_at']
    readonly_fields     = ['uploaded_by', 'created_at']
    verbose_name        = "Document du RDV"
    verbose_name_plural = "Documents du RDV"


# ─────────────────────────────────────────────────────────────────────────────
# Lead
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display  = [
        'project_name', 'contact_name', 'company',
        'status_badge', 'workflow_badge', 'potential',
        'assigned_to', 'updated_at',
    ]
    list_filter   = [
        'status', 'workflow_status', 'potential',
        'canal_origine', 'flux_type', 'source',
    ]
    search_fields = ['project_name', 'contact_name', 'company', 'location', 'email']
    readonly_fields = ['created_at', 'updated_at', 'validated_by', 'validated_at']
    fieldsets = (
        ('Identification', {
            'fields': (
                ('contact_name', 'company', 'client_type'),
                ('email', 'phone'),
            ),
        }),
        ('Projet', {
            'fields': (
                ('project_name', 'location', 'project_type'),
                'products',
                ('detailed_needs', 'technical_notes'),
            ),
        }),
        ('Qualification commerciale', {
            'fields': (
                ('status', 'workflow_status', 'source'),
                ('potential', 'canal_origine', 'flux_type'),
                ('budget_mad', 'probability'),
                ('nb_logements', 'start_date_est', 'end_date_est'),
                'competitor', 'strategic_comment',
                'next_followup_date',
            ),
        }),
        ('Assignation & Validation', {
            'fields': (
                ('assigned_to', 'created_by'),
                ('validated_by', 'validated_at'),
            ),
        }),
        ('Offre commerciale', {
            'classes': ('collapse',),
            'fields': (('offer_amount_ht', 'offer_sent_date', 'offer_validity_days'),),
        }),
        ('Résultat', {
            'classes': ('collapse',),
            'fields': ('loss_reason', 'loss_notes', 'project'),
        }),
        ('Horodatage', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at'),
        }),
    )
    inlines        = [LeadNoteInline, AppointmentInline, LeadDocumentInline, LeadActivityLogInline]
    date_hierarchy = 'created_at'
    ordering       = ['-updated_at']

    @admin.display(description='Statut pipeline', ordering='status')
    def status_badge(self, obj):
        colors = {
            'VISITE':        '#6b7280', 'OPPORTUNITE':   '#3b82f6',
            'QUALIFICATION': '#8b5cf6', 'CHIFFRAGE':     '#f59e0b',
            'OFFRE':         '#06b6d4', 'GAGNEE':        '#10b981',
            'PERDUE':        '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;'
            'border-radius:12px;font-size:11px">{}</span>',
            color, obj.get_status_display(),
        )

    @admin.display(description='Workflow', ordering='workflow_status')
    def workflow_badge(self, obj):
        colors = {
            'DRAFT': '#9ca3af', 'PENDING_VALIDATION': '#f97316', 'VALIDATED': '#22c55e',
        }
        color = colors.get(obj.workflow_status, '#9ca3af')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;'
            'border-radius:12px;font-size:11px">{}</span>',
            color, obj.get_workflow_status_display(),
        )


# ─────────────────────────────────────────────────────────────────────────────
# LeadNote
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(LeadNote)
class LeadNoteAdmin(admin.ModelAdmin):
    list_display    = ['lead', 'author', 'created_at']
    list_filter     = ['author']
    search_fields   = ['lead__project_name', 'text']
    readonly_fields = ['created_at']


# ─────────────────────────────────────────────────────────────────────────────
# Activity (agenda)
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display    = ['subject', 'activity_type', 'planned_at', 'status', 'assigned_to', 'lead']
    list_filter     = ['activity_type', 'status', 'assigned_to']
    search_fields   = ['subject', 'lead__project_name']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    date_hierarchy  = 'planned_at'


# ─────────────────────────────────────────────────────────────────────────────
# Appointment
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display      = ['title', 'appointment_type', 'lead', 'scheduled_at', 'status_badge', 'created_by']
    list_filter       = ['appointment_type', 'status']
    search_fields     = ['title', 'lead__project_name', 'location']
    readonly_fields   = ['created_at', 'updated_at', 'created_by', 'report_written_at']
    filter_horizontal = ['attendees']
    inlines           = [AppointmentDocumentInline]
    date_hierarchy    = 'scheduled_at'
    fieldsets = (
        ('Informations', {
            'fields': (
                ('lead', 'appointment_type', 'status'),
                'title',
                ('scheduled_at', 'duration_minutes'),
                'location',
                'attendees',
            ),
        }),
        ('Compte rendu', {
            'fields': ('report', 'report_written_at'),
        }),
        ('Méta', {
            'classes': ('collapse',),
            'fields': ('created_by', 'created_at', 'updated_at'),
        }),
    )

    @admin.display(description='Statut', ordering='status')
    def status_badge(self, obj):
        colors = {
            'PLANIFIE': '#3b82f6', 'REALISE': '#10b981',
            'ANNULE':   '#9ca3af', 'REPORTE': '#f59e0b',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;'
            'border-radius:12px;font-size:11px">{}</span>',
            color, obj.get_status_display(),
        )


# ─────────────────────────────────────────────────────────────────────────────
# LeadDocument
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(LeadDocument)
class LeadDocumentAdmin(admin.ModelAdmin):
    list_display    = ['title', 'doc_type', 'lead', 'appointment', 'uploaded_by', 'created_at']
    list_filter     = ['doc_type']
    search_fields   = ['title', 'lead__project_name']
    readonly_fields = ['created_at', 'uploaded_by']


# ─────────────────────────────────────────────────────────────────────────────
# LeadActivityLog
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(LeadActivityLog)
class LeadActivityLogAdmin(admin.ModelAdmin):
    list_display    = ['log_type', 'lead', 'performed_by', 'created_at']
    list_filter     = ['log_type', 'performed_by']
    search_fields   = ['lead__project_name', 'content']
    readonly_fields = ['lead', 'log_type', 'content', 'performed_by', 'created_at']
    date_hierarchy  = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
