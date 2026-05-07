"""
Permissions CRM — Bois&Co
=========================
Règles d'accès selon les rôles utilisateur :
  - DIRECTEUR / MANAGER  → directeur commercial : voit tout, valide, assigne
  - COMMERCIAL           → commercial : voit ses leads assignés uniquement
  - Autres rôles         → aucun accès CRM
"""
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def is_director(user):
    """Directeur Général ou Directeur Commercial."""
    return user.is_authenticated and (user.is_superuser or user.role in ('DIRECTEUR', 'MANAGER'))


def is_commercial(user):
    return user.is_authenticated and user.role == 'COMMERCIAL'


def can_access_crm(user):
    return user.is_authenticated and (user.is_superuser or user.role in ('DIRECTEUR', 'MANAGER', 'COMMERCIAL'))


# ─────────────────────────────────────────────────────────────────────────────
# DRF Permission classes
# ─────────────────────────────────────────────────────────────────────────────

class IsDirector(BasePermission):
    """Réservé au Directeur Général ou Directeur Commercial."""
    message = "Accès réservé aux directeurs commerciaux."

    def has_permission(self, request, view):
        return is_director(request.user)


class IsCommercial(BasePermission):
    """Réservé aux commerciaux (rôle COMMERCIAL)."""
    message = "Accès réservé aux commerciaux."

    def has_permission(self, request, view):
        return is_commercial(request.user)


class IsCRMUser(BasePermission):
    """Tout utilisateur avec accès CRM (commercial ou directeur)."""
    message = "Accès CRM non autorisé."

    def has_permission(self, request, view):
        return can_access_crm(request.user)


class CanViewLead(BasePermission):
    """
    - Directeur : voit tous les leads.
    - Commercial : voit uniquement ses leads assignés.
    """
    message = "Vous n'avez pas accès à cette opportunité."

    def has_object_permission(self, request, view, obj):
        if is_director(request.user):
            return True
        return obj.assigned_to == request.user


class CanEditLead(BasePermission):
    """
    - Directeur : peut tout éditer sauf GAGNEE / PERDUE (read-only).
    - Commercial : édite uniquement ses leads en DRAFT ou PENDING_VALIDATION.
    """
    message = "Vous ne pouvez pas modifier cette opportunité."

    def has_object_permission(self, request, view, obj):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return CanViewLead().has_object_permission(request, view, obj)

        if is_director(request.user):
            return obj.status not in ('GAGNEE', 'PERDUE')

        if is_commercial(request.user):
            return (
                obj.assigned_to == request.user
                and obj.workflow_status in ('DRAFT', 'PENDING_VALIDATION')
            )
        return False


class CanValidateLead(BasePermission):
    """Réservé au directeur commercial."""
    message = "Seul le directeur commercial peut valider une opportunité."

    def has_permission(self, request, view):
        return is_director(request.user)

    def has_object_permission(self, request, view, obj):
        return is_director(request.user)


class CanAssignLead(BasePermission):
    """Réservé au directeur commercial."""
    message = "Seul le directeur commercial peut assigner une opportunité."

    def has_permission(self, request, view):
        return is_director(request.user)


# ─────────────────────────────────────────────────────────────────────────────
# Mixin pour les vues CBV Django
# ─────────────────────────────────────────────────────────────────────────────

class CRMAccessMixin(AccessMixin):
    """
    Mixin de base : l'utilisateur doit avoir accès au CRM.
    Redirige vers login si non authentifié, lève 403 sinon.
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not can_access_crm(request.user):
            raise PermissionDenied("Accès CRM non autorisé.")
        return super().dispatch(request, *args, **kwargs)


class DirectorRequiredMixin(AccessMixin):
    """Réservé aux directeurs (DG ou DC)."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not is_director(request.user):
            raise PermissionDenied("Accès réservé aux directeurs commerciaux.")
        return super().dispatch(request, *args, **kwargs)


class LeadOwnerOrDirectorMixin(CRMAccessMixin):
    """
    Pour les vues de détail/édition d'un lead :
    - Le directeur passe toujours.
    - Le commercial ne passe que si le lead lui est assigné.
    Suppose que la vue récupère self.object (get_object() appelé avant).
    """
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        user = self.request.user
        if not is_director(user) and obj.assigned_to != user:
            raise PermissionDenied("Vous n'avez pas accès à cette opportunité.")
        return obj
