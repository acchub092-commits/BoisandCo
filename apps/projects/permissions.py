from rest_framework.permissions import BasePermission

from .models import Project


def _is_project_member(user, project):
    """True if user has any access to the project."""
    if user.is_superuser or user.role in ('DIRECTEUR', 'MANAGER'):
        return True
    return (
        project.manager_id == user.pk
        or project.estimator_id == user.pk
        or project.chef_de_projet_id == user.pk
        or project.members.filter(user=user).exists()
    )


class IsProjectMember(BasePermission):
    """Grants access to any member of the project (resolved from URL pk)."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        pk = view.kwargs.get('pk') or view.kwargs.get('project_pk')
        if not pk:
            return False
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return False
        return _is_project_member(request.user, project)


class IsManagerOrAbove(BasePermission):
    """Grants access only to DIRECTEUR and MANAGER roles."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_superuser or request.user.role in ('DIRECTEUR', 'MANAGER')


class IsChefDeProjet(BasePermission):
    """Grants access to the designated chef de projet of the project."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        pk = view.kwargs.get('pk') or view.kwargs.get('project_pk')
        if not pk:
            return False
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return False
        return (
            request.user.is_superuser
            or request.user.role in ('DIRECTEUR', 'MANAGER')
            or project.chef_de_projet_id == request.user.pk
        )
