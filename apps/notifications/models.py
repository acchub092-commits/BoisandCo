"""
Système de notifications in-app.
Utilise une FK générique pour pointer vers n'importe quel objet métier.
"""
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class Notification(models.Model):
    """Alerte in-app destinée à un utilisateur."""

    class Type(models.TextChoices):
        TASK_ASSIGNED       = 'TASK_ASSIGNED',       'Tâche affectée'
        TASK_ACTIVATED      = 'TASK_ACTIVATED',      'Tâche activée'
        TASK_COMPLETED      = 'TASK_COMPLETED',      'Tâche terminée'
        TASK_OVERDUE        = 'TASK_OVERDUE',        'Tâche en retard'
        PHASE_STARTED       = 'PHASE_STARTED',       'Phase démarrée'
        PHASE_DONE          = 'PHASE_DONE',          'Phase terminée'
        PROJECT_UPDATE      = 'PROJECT_UPDATE',      'Mise à jour projet'
        DOCUMENT_ADDED      = 'DOCUMENT_ADDED',      'Document ajouté'
        MENTION             = 'MENTION',             'Mention'
        APPROVAL_REQUESTED  = 'APPROVAL_REQUESTED',  'Validation requise'
        APPROVAL_APPROVED   = 'APPROVAL_APPROVED',   'Approbation partielle'
        APPROVAL_REJECTED   = 'APPROVAL_REJECTED',   'Validation rejetée'
        APPROVAL_COMPLETED  = 'APPROVAL_COMPLETED',  'Validation complète'

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='Destinataire',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sent_notifications',
        verbose_name='Émetteur',
    )
    notification_type = models.CharField(
        max_length=30,
        choices=Type.choices,
        verbose_name='Type',
    )
    title = models.CharField(max_length=200, verbose_name='Titre')
    message = models.TextField(verbose_name='Message')
    is_read = models.BooleanField(default=False, verbose_name='Lu')
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Objet métier lié (tâche, phase, projet, document…)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'[{self.get_notification_type_display()}] → {self.recipient} : {self.title}'

    def mark_as_read(self):
        from django.utils import timezone
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    @property
    def target_url(self):
        """Résout l'URL de la page liée à cette notification."""
        from django.urls import reverse, NoReverseMatch
        if not self.content_type or not self.object_id:
            return None
        obj = self.content_object
        if obj is None:
            return None
        model = self.content_type.model
        try:
            if model == 'task':
                return reverse('projects:task_detail', args=[obj.pk])
            elif model == 'phase':
                return reverse('projects:detail', args=[obj.project_id])
            elif model == 'project':
                return reverse('projects:detail', args=[obj.pk])
            elif model == 'document':
                project_id = getattr(obj, 'project_id', None)
                if project_id:
                    return reverse('projects:detail', args=[project_id])
                return reverse('documents:list')
            elif model == 'demandechiffrage':
                return reverse('chiffrage:detail', args=[obj.pk])
        except (NoReverseMatch, AttributeError):
            pass
        return None

    @classmethod
    def unread_count(cls, user):
        return cls.objects.filter(recipient=user, is_read=False).count()
