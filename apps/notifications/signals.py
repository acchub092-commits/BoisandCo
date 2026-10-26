from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Notification


@receiver(post_save, sender=Notification)
def relay_notification_as_push(sender, instance, created, **kwargs):
    if not created:
        return
    from .push import send_push_for_notification
    send_push_for_notification(instance)
