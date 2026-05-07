from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Document


@receiver(post_save, sender=Document)
def notify_on_document_added(sender, instance, created, **kwargs):
    """Notifie l'équipe du projet quand un document est déposé."""
    if not created:
        return
    try:
        from apps.notifications.models import Notification
        from django.contrib.contenttypes.models import ContentType
    except ImportError:
        return

    project = instance.project
    uploader = instance.uploaded_by
    ct = ContentType.objects.get_for_model(Document)

    # Destinataires : manager + estimateur, en excluant l'uploader
    recipients = set()
    recipients.add(project.manager)
    if project.estimator:
        recipients.add(project.estimator)
    if uploader:
        recipients.discard(uploader)

    # Si l'uploader est le seul responsable, on le notifie quand même
    # pour confirmer le dépôt (notification de confirmation)
    if not recipients:
        recipients.add(uploader)

    uploader_name = uploader.get_full_name() if uploader else 'Un collaborateur'

    for recipient in recipients:
        Notification.objects.create(
            recipient=recipient,
            sender=uploader,
            notification_type=Notification.Type.DOCUMENT_ADDED,
            title='Nouveau document déposé',
            message=(
                f'« {instance.name} » a été déposé sur le projet '
                f'{project.reference} par {uploader_name}.'
            ),
            content_type=ct,
            object_id=instance.pk,
        )
