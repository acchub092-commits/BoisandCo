from django.urls import path

from .views import (
    WorkflowTemplateListView,
    WorkflowTemplateCreateView,
    WorkflowTemplateEditView,
    WorkflowTemplateDeleteView,
    ProjectWorkflowsView,
    PhaseWorkflowConfigView,
    TaskWorkflowConfigView,
    ApprovalRequestCreateView,
    ApprovalDecisionView,
    ProjectApprovalsView,
)

app_name = 'workflows'

urlpatterns = [
    # -----------------------------------------------------------------------
    # Workflow template management
    # -----------------------------------------------------------------------
    path('workflows/', WorkflowTemplateListView.as_view(), name='template_list'),
    path('workflows/nouveau/', WorkflowTemplateCreateView.as_view(), name='template_create'),
    path('workflows/<int:pk>/modifier/', WorkflowTemplateEditView.as_view(), name='template_edit'),
    path('workflows/<int:pk>/supprimer/', WorkflowTemplateDeleteView.as_view(), name='template_delete'),

    # -----------------------------------------------------------------------
    # Project-scoped workflow configuration & approvals
    # -----------------------------------------------------------------------
    path(
        'projets/<int:project_pk>/workflows/',
        ProjectWorkflowsView.as_view(),
        name='project_workflows',
    ),
    path(
        'projets/<int:project_pk>/phases/<int:phase_pk>/workflow/',
        PhaseWorkflowConfigView.as_view(),
        name='phase_workflow_config',
    ),
    path(
        'projets/<int:project_pk>/tasks/<int:task_pk>/workflow/',
        TaskWorkflowConfigView.as_view(),
        name='task_workflow_config',
    ),
    path(
        'projets/<int:project_pk>/valider/phase/<int:phase_pk>/',
        ApprovalRequestCreateView.as_view(),
        name='approval_create_phase',
    ),
    path(
        'projets/<int:project_pk>/valider/task/<int:task_pk>/',
        ApprovalRequestCreateView.as_view(),
        name='approval_create_task',
    ),
    path(
        'projets/<int:project_pk>/approbations/',
        ProjectApprovalsView.as_view(),
        name='project_approvals',
    ),

    # -----------------------------------------------------------------------
    # Approval decision (global — not project-scoped)
    # -----------------------------------------------------------------------
    path(
        'approbations/<int:request_pk>/decider/',
        ApprovalDecisionView.as_view(),
        name='approval_decision',
    ),
]
