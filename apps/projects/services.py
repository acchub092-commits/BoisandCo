from django.utils import timezone

from .models import Project, ProjectStep


def desig_chef_de_projet(project: Project, chef, designated_by) -> Project:
    """Désigne un chef de projet. Nécessite validation admin ultérieure."""
    project.chef_de_projet = chef
    project.chef_designe_par = designated_by
    project.chef_designe_le = timezone.now()
    project.chef_valide_par_admin = False
    project.chef_valide_le = None
    project.save(update_fields=[
        'chef_de_projet', 'chef_designe_par', 'chef_designe_le',
        'chef_valide_par_admin', 'chef_valide_le',
    ])
    return project


def validate_chef(project: Project, admin) -> Project:
    """Valide la désignation du chef de projet (réservé DIRECTEUR/MANAGER)."""
    if not project.chef_de_projet:
        raise ValueError('Aucun chef de projet désigné.')
    project.chef_valide_par_admin = True
    project.chef_valide_le = timezone.now()
    project.save(update_fields=['chef_valide_par_admin', 'chef_valide_le'])
    return project


def complete_step(step: ProjectStep, user) -> ProjectStep:
    """Marque une étape comme terminée."""
    if step.is_completed:
        return step
    step.is_completed = True
    step.completed_at = timezone.now()
    step.completed_by = user
    step.save(update_fields=['is_completed', 'completed_at', 'completed_by'])
    return step
