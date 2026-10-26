from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification, PushSubscription
from .serializers import NotificationSerializer


class PushSubscribeView(APIView):
    """Enregistre (ou met à jour) l'abonnement Web Push envoyé par la PWA
    (résultat de `PushManager.subscribe()` côté navigateur)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        endpoint = request.data.get('endpoint')
        keys = request.data.get('keys') or {}
        p256dh = keys.get('p256dh')
        auth = keys.get('auth')
        if not endpoint or not p256dh or not auth:
            return Response({'detail': "Abonnement push incomplet."}, status=status.HTTP_400_BAD_REQUEST)

        PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                'user': request.user, 'p256dh': p256dh, 'auth': auth,
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:255],
            },
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PushUnsubscribeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        endpoint = request.data.get('endpoint')
        if endpoint:
            PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationListView(generics.ListAPIView):
    """Cloche de notifications — liste paginée, la plus récente en premier."""

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user).select_related('sender')
        if self.request.query_params.get('unread') == '1':
            qs = qs.filter(is_read=False)
        return qs


class NotificationUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'count': Notification.unread_count(request.user)})


class NotificationMarkReadView(APIView):
    """Marque une notification (ou toutes) comme lue — reflète NotificationMarkReadView (web)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        if pk:
            notif = Notification.objects.filter(pk=pk, recipient=request.user).first()
            if notif:
                notif.mark_as_read()
        else:
            Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({'count': Notification.unread_count(request.user)})
