"""
Relais Web Push (VAPID) des notifications in-app vers les abonnements navigateur
enregistrés par la PWA mobile — effet « notification comme WhatsApp » sur un
téléphone même quand l'app n'est pas ouverte.

Best-effort : un échec d'envoi push ne doit jamais faire échouer la création de
la Notification in-app elle-même (voir le signal post_save qui appelle ceci).
"""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def mobile_url_for(notification):
    """URL mobile ouverte au clic (push ou cloche de notifications in-app). Seul le module
    Chiffrage a une PWA pour l'instant — les autres types de notification ouvrent simplement
    l'accueil de l'app."""
    if notification.content_type and notification.content_type.model == 'demandechiffrage' and notification.object_id:
        return f'/m/chiffrage/#/detail/{notification.object_id}'
    return '/m/chiffrage/'


def send_push_for_notification(notification):
    if not settings.VAPID_PRIVATE_KEY:
        return

    from .models import PushSubscription

    subscriptions = list(PushSubscription.objects.filter(user_id=notification.recipient_id))
    if not subscriptions:
        return

    from pywebpush import WebPushException, webpush

    payload = json.dumps({
        'title': notification.title,
        'body': notification.message,
        'url': mobile_url_for(notification),
    })

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                },
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={'sub': settings.VAPID_CLAIM_EMAIL},
            )
        except WebPushException as exc:
            status_code = getattr(exc.response, 'status_code', None)
            if status_code in (404, 410):
                sub.delete()
            else:
                logger.warning('Échec envoi push (sub %s) : %s', sub.pk, exc)
        except Exception:
            logger.warning('Erreur inattendue envoi push (sub %s)', sub.pk, exc_info=True)
