from django.contrib import admin

from .models import (
    WorkflowTemplate,
    WorkflowStep,
    PhaseWorkflowConfig,
    TaskWorkflowConfig,
    StepValidator,
    ApprovalRequest,
    ApprovalDecision,
)


# ---------------------------------------------------------------------------
# WorkflowTemplate + WorkflowStep inline
# ---------------------------------------------------------------------------

class WorkflowStepInline(admin.TabularInline):
    model = WorkflowStep
    extra = 1
    fields = ('order', 'name', 'description', 'approval_mode')
    ordering = ('order',)


@admin.register(WorkflowTemplate)
class WorkflowTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_by', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [WorkflowStepInline]


# ---------------------------------------------------------------------------
# PhaseWorkflowConfig + StepValidator inline
# ---------------------------------------------------------------------------

class PhaseStepValidatorInline(admin.TabularInline):
    model = StepValidator
    extra = 1
    fields = ('step', 'user')
    fk_name = 'phase_config'

    def get_queryset(self, request):
        return super().get_queryset(request).filter(phase_config__isnull=False)


@admin.register(PhaseWorkflowConfig)
class PhaseWorkflowConfigAdmin(admin.ModelAdmin):
    list_display = ('phase', 'template', 'configured_by', 'require_validation', 'configured_at')
    list_filter = ('require_validation', 'template')
    search_fields = ('phase__name',)
    readonly_fields = ('configured_at',)
    inlines = [PhaseStepValidatorInline]


# ---------------------------------------------------------------------------
# TaskWorkflowConfig + StepValidator inline
# ---------------------------------------------------------------------------

class TaskStepValidatorInline(admin.TabularInline):
    model = StepValidator
    extra = 1
    fields = ('step', 'user')
    fk_name = 'task_config'

    def get_queryset(self, request):
        return super().get_queryset(request).filter(task_config__isnull=False)


@admin.register(TaskWorkflowConfig)
class TaskWorkflowConfigAdmin(admin.ModelAdmin):
    list_display = ('task', 'template', 'configured_by', 'require_validation', 'configured_at')
    list_filter = ('require_validation', 'template')
    search_fields = ('task__name',)
    readonly_fields = ('configured_at',)
    inlines = [TaskStepValidatorInline]


# ---------------------------------------------------------------------------
# ApprovalRequest + ApprovalDecision inline (readonly)
# ---------------------------------------------------------------------------

class ApprovalDecisionInline(admin.TabularInline):
    model = ApprovalDecision
    extra = 0
    readonly_fields = ('step', 'decided_by', 'decision', 'comment', 'decided_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = (
        '__str__', 'status', 'template', 'current_step_order',
        'initiated_by', 'initiated_at', 'completed_at',
    )
    list_filter = ('status', 'template')
    search_fields = ('phase__name', 'task__name', 'initiated_by__username')
    readonly_fields = ('initiated_at', 'completed_at')
    inlines = [ApprovalDecisionInline]
