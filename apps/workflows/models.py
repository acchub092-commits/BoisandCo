from django.db import models
from django.conf import settings
from django.utils import timezone


class WorkflowTemplate(models.Model):
    name = models.CharField(max_length=100, verbose_name='Nom')
    description = models.TextField(blank=True, verbose_name='Description')
    is_active = models.BooleanField(default=True, verbose_name='Actif')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_workflows',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Gabarit de workflow'
        verbose_name_plural = 'Gabarits de workflow'
        ordering = ['name']

    def __str__(self):
        return self.name


class WorkflowStep(models.Model):
    class ApprovalMode(models.TextChoices):
        ANY = 'ANY', 'Un validateur suffit'
        ALL = 'ALL', 'Tous doivent valider'

    template = models.ForeignKey(
        WorkflowTemplate,
        on_delete=models.CASCADE,
        related_name='steps',
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    approval_mode = models.CharField(
        max_length=3,
        choices=ApprovalMode.choices,
        default='ANY',
    )

    class Meta:
        ordering = ['order']
        unique_together = [['template', 'order']]

    def __str__(self):
        return f'{self.template.name} › Étape {self.order + 1}: {self.name}'


class PhaseWorkflowConfig(models.Model):
    phase = models.OneToOneField(
        'projects.Phase',
        on_delete=models.CASCADE,
        related_name='workflow_config',
    )
    template = models.ForeignKey(
        WorkflowTemplate,
        on_delete=models.PROTECT,
        related_name='phase_configs',
    )
    configured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='phase_wf_configs',
    )
    configured_at = models.DateTimeField(auto_now_add=True)
    require_validation = models.BooleanField(
        default=True,
        verbose_name='Bloquer sans validation',
    )

    class Meta:
        verbose_name = 'Config workflow phase'

    def __str__(self):
        return f'Workflow phase: {self.phase}'


class TaskWorkflowConfig(models.Model):
    task = models.OneToOneField(
        'projects.Task',
        on_delete=models.CASCADE,
        related_name='workflow_config',
    )
    template = models.ForeignKey(
        WorkflowTemplate,
        on_delete=models.PROTECT,
        related_name='task_configs',
    )
    configured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='task_wf_configs',
    )
    configured_at = models.DateTimeField(auto_now_add=True)
    require_validation = models.BooleanField(
        default=True,
        verbose_name='Bloquer sans validation',
    )

    class Meta:
        verbose_name = 'Config workflow tâche'

    def __str__(self):
        return f'Workflow tâche: {self.task}'


class StepValidator(models.Model):
    """Validateur assigné à une étape pour une config phase OU tâche spécifique."""

    step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.CASCADE,
        related_name='validators',
    )
    phase_config = models.ForeignKey(
        PhaseWorkflowConfig,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='validators',
    )
    task_config = models.ForeignKey(
        TaskWorkflowConfig,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='validators',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='step_validations',
    )

    class Meta:
        verbose_name = "Validateur d'étape"


class ApprovalRequest(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = 'IN_PROGRESS', 'En cours'
        APPROVED = 'APPROVED', 'Approuvé'
        REJECTED = 'REJECTED', 'Rejeté'
        CANCELLED = 'CANCELLED', 'Annulé'

    phase = models.ForeignKey(
        'projects.Phase',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='approval_requests',
    )
    task = models.ForeignKey(
        'projects.Task',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='approval_requests',
    )
    template = models.ForeignKey(
        WorkflowTemplate,
        on_delete=models.PROTECT,
    )
    current_step_order = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='initiated_approvals',
    )
    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Demande de validation'
        ordering = ['-initiated_at']

    def __str__(self):
        obj = self.phase or self.task
        return f'Validation {obj} — {self.get_status_display()}'

    @property
    def current_step(self):
        return self.template.steps.filter(order=self.current_step_order).first()

    @property
    def is_active(self):
        return self.status == self.Status.IN_PROGRESS

    def get_validators_for_step(self, step):
        """Returns QuerySet of users assigned to validate this step."""
        from apps.users.models import User
        if self.phase_id:
            cfg = getattr(self.phase, 'workflow_config', None)
            if cfg:
                ids = StepValidator.objects.filter(
                    step=step, phase_config=cfg
                ).values_list('user_id', flat=True)
                return User.objects.filter(pk__in=ids)
        elif self.task_id:
            cfg = getattr(self.task, 'workflow_config', None)
            if cfg:
                ids = StepValidator.objects.filter(
                    step=step, task_config=cfg
                ).values_list('user_id', flat=True)
                return User.objects.filter(pk__in=ids)
        return User.objects.none()

    def get_pending_validators(self, step):
        decided_ids = self.decisions.filter(step=step).values_list(
            'decided_by_id', flat=True
        )
        return self.get_validators_for_step(step).exclude(pk__in=decided_ids)

    def can_step_advance(self, step):
        approvals = self.decisions.filter(
            step=step, decision=ApprovalDecision.Decision.APPROVED
        )
        if step.approval_mode == WorkflowStep.ApprovalMode.ANY:
            return approvals.exists()
        else:
            return approvals.exists() and not self.get_pending_validators(step).exists()

    def advance_or_complete(self):
        """Move to next step or complete request. Returns ('advanced', next_step) or ('completed', None)."""
        next_step = (
            self.template.steps
            .filter(order__gt=self.current_step_order)
            .order_by('order')
            .first()
        )
        if next_step:
            self.current_step_order = next_step.order
            self.save(update_fields=['current_step_order'])
            return 'advanced', next_step
        else:
            self.status = self.Status.APPROVED
            self.completed_at = timezone.now()
            self.save(update_fields=['status', 'completed_at'])
            return 'completed', None

    def reject_request(self):
        self.status = self.Status.REJECTED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])


class ApprovalDecision(models.Model):
    class Decision(models.TextChoices):
        APPROVED = 'APPROVED', 'Approuvé'
        REJECTED = 'REJECTED', 'Rejeté'

    request = models.ForeignKey(
        ApprovalRequest,
        on_delete=models.CASCADE,
        related_name='decisions',
    )
    step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.PROTECT,
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='approval_decisions',
    )
    decision = models.CharField(max_length=10, choices=Decision.choices)
    comment = models.TextField(blank=True)
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Décision'
        unique_together = [['request', 'step', 'decided_by']]
        ordering = ['decided_at']

    def __str__(self):
        return f'{self.decided_by} → {self.get_decision_display()}'
