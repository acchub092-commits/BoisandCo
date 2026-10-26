"""Permissions API mobile — commercial terrain (création/suivi de ses demandes) +
Directeur Commercial, DG, Responsable Méthodes et Méthodes/Estimateur (actions de
validation des étapes qui les concernent)."""
from rest_framework.permissions import BasePermission

ROLES_MOBILE = ('COMMERCIAL', 'MANAGER', 'DIRECTEUR', 'RESP_METHODES', 'ESTIMATEUR')


def is_mobile_user(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.role in ROLES_MOBILE))


class IsChiffrageMobileUser(BasePermission):
    """Accès à l'API mobile Chiffrage — commercial (ses propres demandes), DC/DG/RM/Méthodes
    (toutes, comme sur le web — RG déjà en place côté desktop, `_qs_for_user`)."""

    message = "Cette API est réservée aux intervenants du processus de chiffrage."

    def has_permission(self, request, view):
        return is_mobile_user(request.user)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser or user.role != 'COMMERCIAL':
            return True
        return obj.commercial_id == user.id
