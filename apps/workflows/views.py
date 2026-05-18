from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import TemplateView, View

from apps.users.models import User
from apps.projects.models import Project, Phase, Task

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
# Helper — notification
# ---------------------------------------------------------------------------

def _notify(recipient, sender, title, message, notif_type, linked_obj=None):
    from apps.notifications.models import Notification
    from django.contrib.contenttypes.models import ContentType
    n = Notification(
        recipient=recipient,
        sender=sender,
        notification_type=notif_type,
        title=title,
        message=message,
    )
    if linked_obj:
        n.content_type = ContentType.objects.get_for_model(linked_obj)
        n.object_id = linked_obj.pk
    n.save()


# ---------------------------------------------------------------------------
# 1. WorkflowTemplateListView
# ---------------------------------------------------------------------------

class WorkflowTemplateListView(LoginRequiredMixin, TemplateView):
    template_name = 'workflows/template_list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['templates'] = (
            WorkflowTemplate.objects
            .prefetch_related('steps')
            .annotate(
                steps_count=Count('steps', distinct=True),
                phase_count=Count('phase_configs', distinct=True),
                task_count=Count('task_configs', distinct=True),
            )
        )
        return ctx


# ---------------------------------------------------------------------------
# 2. WorkflowTemplateCreateView
# ---------------------------------------------------------------------------

class WorkflowTemplateCreateView(LoginRequiredMixin, View):
    template_name = 'workflows/template_form.html'

    def get(self, request):
        return render(request, self.template_name, {'template': None, 'steps_json': '[]'})

    def post(self, request):
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()

        if not name:
            messages.error(request, 'Le nom du workflow est obligatoire.')
            return render(request, self.template_name, {'template': None, 'steps_json': '[]'})

        wf = WorkflowTemplate.objects.create(
            name=name,
            description=description,
            created_by=request.user,
        )
        _create_steps_from_post(request.POST, wf)
        messages.success(request, f'Workflow « {wf.name} » créé.')
        return redirect('workflows:template_list')


# ---------------------------------------------------------------------------
# 3. WorkflowTemplateEditView
# ---------------------------------------------------------------------------

class WorkflowTemplateEditView(LoginRequiredMixin, View):
    template_name = 'workflows/template_form.html'

    def _get_wf(self, pk):
        return get_object_or_404(WorkflowTemplate, pk=pk)

    def _steps_json(self, wf):
        import json
        steps = [
            {
                'name': s.name,
                'description': s.description,
                'order': s.order,
                'mode': s.approval_mode,
            }
            for s in wf.steps.order_by('order')
        ]
        return json.dumps(steps)

    def get(self, request, pk):
        wf = self._get_wf(pk)
        return render(request, self.template_name, {
            'template': wf,
            'steps_json': self._steps_json(wf),
        })

    def post(self, request, pk):
        wf = self._get_wf(pk)
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()

        if not name:
            messages.error(request, 'Le nom du workflow est obligatoire.')
            return render(request, self.template_name, {
                'template': wf,
                'steps_json': self._steps_json(wf),
            })

        wf.name = name
        wf.description = description
        wf.save(update_fields=['name', 'description', 'updated_at'])

        # Delete all existing steps and recreate from POST data
        wf.steps.all().delete()
        _create_steps_from_post(request.POST, wf)

        messages.success(request, f'Workflow « {wf.name} » mis à jour.')
        return redirect('workflows:template_list')


# ---------------------------------------------------------------------------
# 4. WorkflowTemplateDeleteView
# ---------------------------------------------------------------------------

class WorkflowTemplateDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        wf = get_object_or_404(WorkflowTemplate, pk=pk)
        in_use = (
            wf.phase_configs.exists()
            or wf.task_configs.exists()
            or ApprovalRequest.objects.filter(template=wf).exists()
        )
        if in_use:
            messages.error(
                request,
                f'Le workflow « {wf.name} » est en cours d\'utilisation et ne peut pas être supprimé.',
            )
        else:
            wf.delete()
            messages.success(request, 'Workflow supprimé.')
        return redirect('workflows:template_list')


# ---------------------------------------------------------------------------
# 5. ProjectWorkflowsView
# ---------------------------------------------------------------------------

class ProjectWorkflowsView(LoginRequiredMixin, View):
    template_name = 'workflows/project_workflows.html'

    def get(self, request, project_pk):
        project = get_object_or_404(Project, pk=project_pk)

        if not _can_manage_project(request.user, project):
            messages.error(request, 'Accès refusé.')
            return redirect('projects:detail', pk=project_pk)

        phases = project.phases.prefetch_related(
            'workflow_config__template__steps',
            'workflow_config__validators',
            'approval_requests',
        ).order_by('order')

        tasks = Task.objects.filter(phase__project=project).prefetch_related(
            'workflow_config__template__steps',
            'workflow_config__validators',
            'approval_requests',
        ).order_by('phase__order', 'order')

        templates = WorkflowTemplate.objects.filter(is_active=True).prefetch_related('steps')
        all_users = User.objects.filter(is_active_employee=True).order_by('last_name')

        return render(request, self.template_name, {
            'project': project,
            'phases': phases,
            'tasks': tasks,
            'templates': templates,
            'all_users': all_users,
        })


# ---------------------------------------------------------------------------
# 6. PhaseWorkflowConfigView
# ---------------------------------------------------------------------------

class PhaseWorkflowConfigView(LoginRequiredMixin, View):
    def post(self, request, project_pk, phase_pk):
        project = get_object_or_404(Project, pk=project_pk)
        phase = get_object_or_404(Phase, pk=phase_pk, project=project)

        if not _can_manage_project(request.user, project):
            messages.error(request, 'Accès refusé.')
            return redirect('projects:detail', pk=project_pk)

        template_id = request.POST.get('template_id')
        if not template_id:
            messages.error(request, 'Veuillez sélectionner un template de workflow.')
            return redirect('workflows:project_workflows', project_pk=project_pk)

        wf_template = get_object_or_404(WorkflowTemplate, pk=template_id)

        # Create or update the phase workflow config
        config, created = PhaseWorkflowConfig.objects.update_or_create(
            phase=phase,
            defaults={
                'template': wf_template,
                'configured_by': request.user,
                'require_validation': request.POST.get('require_validation', 'on') == 'on',
            },
        )

        # Remove old validators for this config then recreate
        config.validators.all().delete()

        for step in wf_template.steps.all():
            user_ids = request.POST.getlist(f'step_{step.pk}_validators')
            for uid in user_ids:
                try:
                    user = User.objects.get(pk=uid)
                    StepValidator.objects.create(
                        step=step,
                        phase_config=config,
                        user=user,
                    )
                except User.DoesNotExist:
                    pass

        messages.success(request, f'Workflow configuré pour la phase « {phase.name} ».')
        return redirect('workflows:project_workflows', project_pk=project_pk)


# ---------------------------------------------------------------------------
# 7. TaskWorkflowConfigView
# ---------------------------------------------------------------------------

class TaskWorkflowConfigView(LoginRequiredMixin, View):
    def post(self, request, project_pk, task_pk):
        project = get_object_or_404(Project, pk=project_pk)
        task = get_object_or_404(Task, pk=task_pk, phase__project=project)

        if not _can_manage_project(request.user, project):
            messages.error(request, 'Accès refusé.')
            return redirect('projects:detail', pk=project_pk)

        template_id = request.POST.get('template_id')
        if not template_id:
            messages.error(request, 'Veuillez sélectionner un template de workflow.')
            return redirect('workflows:project_workflows', project_pk=project_pk)

        wf_template = get_object_or_404(WorkflowTemplate, pk=template_id)

        config, created = TaskWorkflowConfig.objects.update_or_create(
            task=task,
            defaults={
                'template': wf_template,
                'configured_by': request.user,
                'require_validation': request.POST.get('require_validation', 'on') == 'on',
            },
        )

        config.validators.all().delete()

        for step in wf_template.steps.all():
            user_ids = request.POST.getlist(f'step_{step.pk}_validators')
            for uid in user_ids:
                try:
                    user = User.objects.get(pk=uid)
                    StepValidator.objects.create(
                        step=step,
                        task_config=config,
                        user=user,
                    )
                except User.DoesNotExist:
                    pass

        messages.success(request, f'Workflow configuré pour la tâche « {task.name} ».')
        return redirect('workflows:project_workflows', project_pk=project_pk)


# ---------------------------------------------------------------------------
# 8. ApprovalRequestCreateView
# ---------------------------------------------------------------------------

class ApprovalRequestCreateView(LoginRequiredMixin, View):
    def post(self, request, project_pk, phase_pk=None, task_pk=None):
        project = get_object_or_404(Project, pk=project_pk)

        phase = None
        task = None
        config = None

        if phase_pk:
            phase = get_object_or_404(Phase, pk=phase_pk, project=project)
            config = getattr(phase, 'workflow_config', None)
            if not config:
                messages.error(request, 'Aucun workflow configuré pour cette phase.')
                return redirect('workflows:project_workflows', project_pk=project_pk)
        elif task_pk:
            task = get_object_or_404(Task, pk=task_pk, phase__project=project)
            config = getattr(task, 'workflow_config', None)
            if not config:
                messages.error(request, 'Aucun workflow configuré pour cette tâche.')
                return redirect('workflows:project_workflows', project_pk=project_pk)
        else:
            messages.error(request, 'Cible de validation invalide.')
            return redirect('workflows:project_workflows', project_pk=project_pk)

        wf_template = config.template
        first_step = wf_template.steps.order_by('order').first()
        if not first_step:
            messages.error(request, 'Ce workflow ne contient aucune étape.')
            return redirect('workflows:project_workflows', project_pk=project_pk)

        approval = ApprovalRequest.objects.create(
            phase=phase,
            task=task,
            template=wf_template,
            current_step_order=first_step.order,
            initiated_by=request.user,
        )

        # Notify validators of first step
        validators = approval.get_validators_for_step(first_step)
        obj_label = str(phase or task)
        for validator in validators:
            _notify(
                recipient=validator,
                sender=request.user,
                title='Validation requise',
                message=(
                    f'Votre validation est requise pour : {obj_label} '
                    f'(étape : {first_step.name}).'
                ),
                notif_type='APPROVAL_REQUESTED',
                linked_obj=approval,
            )

        messages.success(request, 'Demande de validation lancée.')
        return redirect('workflows:project_workflows', project_pk=project_pk)


# ---------------------------------------------------------------------------
# 9. ApprovalDecisionView
# ---------------------------------------------------------------------------

class ApprovalDecisionView(LoginRequiredMixin, View):
    def post(self, request, request_pk):
        approval = get_object_or_404(ApprovalRequest, pk=request_pk)

        if not approval.is_active:
            messages.error(request, 'Cette demande de validation n\'est plus active.')
            return _redirect_to_project(approval)

        current_step = approval.current_step
        if current_step is None:
            messages.error(request, 'Étape courante introuvable.')
            return _redirect_to_project(approval)

        # Check that the user is a validator for current step
        validators = approval.get_validators_for_step(current_step)
        if request.user not in validators:
            messages.error(request, 'Vous n\'êtes pas autorisé à valider cette étape.')
            return _redirect_to_project(approval)

        # Check that user hasn't already decided
        already_decided = approval.decisions.filter(
            step=current_step, decided_by=request.user
        ).exists()
        if already_decided:
            messages.warning(request, 'Vous avez déjà soumis une décision pour cette étape.')
            return _redirect_to_project(approval)

        decision_value = request.POST.get('decision', '')
        comment = request.POST.get('comment', '').strip()

        if decision_value not in (ApprovalDecision.Decision.APPROVED, ApprovalDecision.Decision.REJECTED):
            messages.error(request, 'Décision invalide.')
            return _redirect_to_project(approval)

        ApprovalDecision.objects.create(
            request=approval,
            step=current_step,
            decided_by=request.user,
            decision=decision_value,
            comment=comment,
        )

        obj_label = str(approval.phase or approval.task)

        if decision_value == ApprovalDecision.Decision.REJECTED:
            approval.reject_request()
            # Notify initiator of rejection
            _notify(
                recipient=approval.initiated_by,
                sender=request.user,
                title='Validation rejetée',
                message=(
                    f'La demande de validation pour « {obj_label} » a été rejetée '
                    f'à l\'étape « {current_step.name} » par {request.user}.'
                    + (f'\nCommentaire : {comment}' if comment else '')
                ),
                notif_type='APPROVAL_REJECTED',
                linked_obj=approval,
            )
            messages.warning(request, 'Demande rejetée.')

        else:  # APPROVED
            if approval.can_step_advance(current_step):
                result, next_step = approval.advance_or_complete()

                if result == 'completed':
                    # Notify initiator of full approval
                    _notify(
                        recipient=approval.initiated_by,
                        sender=request.user,
                        title='Validation complète',
                        message=f'La demande de validation pour « {obj_label} » a été approuvée.',
                        notif_type='APPROVAL_COMPLETED',
                        linked_obj=approval,
                    )
                    messages.success(request, 'Validation complète — toutes les étapes sont approuvées.')

                else:  # advanced to next step
                    next_validators = approval.get_validators_for_step(next_step)
                    for validator in next_validators:
                        _notify(
                            recipient=validator,
                            sender=request.user,
                            title='Validation requise',
                            message=(
                                f'Votre validation est requise pour : {obj_label} '
                                f'(étape : {next_step.name}).'
                            ),
                            notif_type='APPROVAL_REQUESTED',
                            linked_obj=approval,
                        )
                    messages.success(
                        request,
                        f'Étape approuvée. Passage à l\'étape suivante : {next_step.name}.',
                    )
            else:
                # Step approved but more validators needed (ALL mode)
                _notify(
                    recipient=approval.initiated_by,
                    sender=request.user,
                    title='Approbation partielle',
                    message=(
                        f'{request.user} a approuvé l\'étape « {current_step.name} » '
                        f'pour « {obj_label} ». En attente d\'autres validateurs.'
                    ),
                    notif_type='APPROVAL_APPROVED',
                    linked_obj=approval,
                )
                messages.success(request, 'Approbation enregistrée. En attente des autres validateurs.')

        return _redirect_to_project(approval)


# ---------------------------------------------------------------------------
# 10. ProjectApprovalsView
# ---------------------------------------------------------------------------

class ProjectApprovalsView(LoginRequiredMixin, TemplateView):
    template_name = 'workflows/project_approvals.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        project = get_object_or_404(Project, pk=self.kwargs['project_pk'])

        phase_requests = ApprovalRequest.objects.filter(
            phase__project=project
        ).prefetch_related('decisions', 'decisions__decided_by', 'decisions__step')

        task_requests = ApprovalRequest.objects.filter(
            task__phase__project=project
        ).prefetch_related('decisions', 'decisions__decided_by', 'decisions__step')

        # Merge and sort by initiated_at descending
        from itertools import chain
        from operator import attrgetter
        approval_requests = sorted(
            chain(phase_requests, task_requests),
            key=attrgetter('initiated_at'),
            reverse=True,
        )

        ctx['project'] = project
        ctx['approval_requests'] = approval_requests
        return ctx


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _can_manage_project(user, project):
    """Returns True if the user is MANAGER/DIRECTEUR or is the project manager."""
    if user.is_superuser:
        return True
    if user.role in ('DIRECTEUR', 'MANAGER'):
        return True
    if project.manager_id == user.pk:
        return True
    return False


def _create_steps_from_post(post_data, wf_template):
    """Parse steps_X_name / steps_X_mode / steps_X_order from POST and create WorkflowStep objects."""
    index = 0
    while True:
        name = post_data.get(f'steps_{index}_name', '').strip()
        if not name:
            break
        order = post_data.get(f'steps_{index}_order', str(index)).strip()
        mode = post_data.get(f'steps_{index}_mode', WorkflowStep.ApprovalMode.ANY).strip()
        description = post_data.get(f'steps_{index}_description', '').strip()
        try:
            order_int = int(order)
        except ValueError:
            order_int = index
        WorkflowStep.objects.create(
            template=wf_template,
            name=name,
            description=description,
            order=order_int,
            approval_mode=mode if mode in WorkflowStep.ApprovalMode.values else WorkflowStep.ApprovalMode.ANY,
        )
        index += 1


def _redirect_to_project(approval):
    """Redirect to the project detail page related to the approval."""
    if approval.phase_id:
        project_pk = approval.phase.project_id
    elif approval.task_id:
        project_pk = approval.task.phase.project_id
    else:
        return redirect('projects:list')
    return redirect('projects:detail', pk=project_pk)
