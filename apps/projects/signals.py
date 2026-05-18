"""
Signaux de l'app projects.
Le workflow domino est géré directement dans Task.set_progress() et Phase.complete().
Ces signaux gèrent les effets de bord : notifications, mises à jour de statut projet.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Task, TaskAssignment, Phase, Project


@receiver(post_save, sender=Task)
def notify_on_task_status_change(sender, instance, created, **kwargs):
    """Crée une notification quand une tâche change de statut."""
    if created:
        return

    update_fields = kwargs.get('update_fields')
    if update_fields and 'status' not in update_fields:
        return

    # Import ici pour éviter la dépendance circulaire
    try:
        from apps.notifications.models import Notification
    except ImportError:
        return

    assignees = instance.assignments.select_related('user').values_list('user', flat=True)
    if not assignees:
        return

    if instance.status == Task.Status.ACTIVE:
        title = 'Nouvelle tâche activée'
        message = f'La tâche « {instance.name} » est maintenant active sur le projet {instance.phase.project.reference}.'
        notif_type = Notification.Type.TASK_ACTIVATED

    elif instance.status == Task.Status.TERMINEE:
        title = 'Tâche terminée'
        message = f'La tâche « {instance.name} » a été marquée terminée.'
        notif_type = Notification.Type.TASK_COMPLETED

    else:
        return

    from apps.notifications.models import Notification
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(Task)
    for user_id in assignees:
        Notification.objects.get_or_create(
            recipient_id=user_id,
            notification_type=notif_type,
            content_type=ct,
            object_id=instance.pk,
            is_read=False,
            defaults={'title': title, 'message': message},
        )


@receiver(post_save, sender=Phase)
def notify_on_phase_change(sender, instance, created, **kwargs):
    """Notifie le manager quand une phase démarre ou se termine."""
    if created:
        return
    update_fields = kwargs.get('update_fields')
    if not update_fields:
        return

    try:
        from apps.notifications.models import Notification
        from django.contrib.contenttypes.models import ContentType
    except ImportError:
        return

    manager = instance.project.manager
    ct = ContentType.objects.get_for_model(Phase)

    if 'is_active' in update_fields and instance.is_active:
        Notification.objects.create(
            recipient=manager,
            notification_type=Notification.Type.PHASE_STARTED,
            title='Phase démarrée',
            message=f'La phase « {instance.name} » a démarré sur {instance.project.reference}.',
            content_type=ct,
            object_id=instance.pk,
        )
    elif 'is_completed' in update_fields and instance.is_completed:
        Notification.objects.create(
            recipient=manager,
            notification_type=Notification.Type.PHASE_DONE,
            title='Phase terminée',
            message=f'La phase « {instance.name} » est terminée sur {instance.project.reference}.',
            content_type=ct,
            object_id=instance.pk,
        )


@receiver(post_save, sender=Project)
def notify_on_chef_designation(sender, instance, created, **kwargs):
    """Notifie le chef de projet quand il est désigné."""
    if created:
        return
    update_fields = kwargs.get('update_fields')
    if not update_fields or 'chef_de_projet' not in update_fields:
        return
    if not instance.chef_de_projet:
        return
    try:
        from apps.notifications.models import Notification
        from django.contrib.contenttypes.models import ContentType
    except ImportError:
        return

    ct = ContentType.objects.get_for_model(Project)
    Notification.objects.create(
        recipient=instance.chef_de_projet,
        sender=instance.chef_designe_par,
        notification_type=Notification.Type.TASK_ASSIGNED,
        title='Vous êtes désigné chef de projet',
        message=(
            f'Vous avez été désigné chef de projet sur {instance.reference} — {instance.name}.'
        ),
        content_type=ct,
        object_id=instance.pk,
    )


@receiver(post_save, sender=TaskAssignment)
def notify_on_assignment(sender, instance, created, **kwargs):
    """Notifie l'utilisateur quand il est affecté à une tâche."""
    if not created:
        return
    try:
        from apps.notifications.models import Notification
        from django.contrib.contenttypes.models import ContentType
    except ImportError:
        return

    ct = ContentType.objects.get_for_model(Task)
    Notification.objects.create(
        recipient=instance.user,
        sender=instance.assigned_by,
        notification_type=Notification.Type.TASK_ASSIGNED,
        title='Vous avez été affecté à une tâche',
        message=(
            f'Vous avez été affecté à « {instance.task.name} » '
            f'sur le projet {instance.task.phase.project.reference}.'
        ),
        content_type=ct,
        object_id=instance.task.pk,
    )
