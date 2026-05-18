import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, get_object_or_404, render
from django.views.generic import TemplateView, ListView, DetailView, View
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models import User
from .models import (
    Project, ProjectTemplate, PhaseTemplate, TaskTemplate,
    Phase, Task, TaskAssignment,
    ProjectMember, TaskComment, PhaseComment, ProjectMessage,
    ProjectStep, StepComment, ProjectComment,
    InstallationPlan, InstallationReport,
    ETAPES_BOISANDCO, PARTIE_LABELS,
)
from .permissions import IsProjectMember, IsManagerOrAbove, IsChefDeProjet
from .serializers_comments import (
    StepCommentSerializer, ProjectCommentSerializer, ProjectStepSerializer,
)
from .services import desig_chef_de_projet, validate_chef, complete_step


def _visible_projects(user):
    """Projects the user is allowed to see.
    DIRECTEUR, MANAGER, ESTIMATEUR, ADV, ATELIER and superusers see everything.
    Others see projects where they have any of the following roles:
    - manager or estimator on the project
    - declared ProjectMember
    - designated chef de projet
    - created the project directly (created_by)
    - commercial who submitted the chiffrage that originated the project
    """
    if user.is_superuser or user.role in ('DIRECTEUR', 'MANAGER', 'ESTIMATEUR', 'ADV', 'ATELIER'):
        return Project.objects.all()
    return Project.objects.filter(
        Q(manager=user) |
        Q(estimator=user) |
        Q(members__user=user) |
        Q(chef_de_projet=user) |
        Q(created_by=user) |
        Q(demande_chiffrage__commercial=user)
    ).distinct()


# Maps phase.owner_label → list of User.role codes who can comment
_OWNER_LABEL_ROLES = {
    'Commercial':       ['COMMERCIAL'],
    'DC + Commercial':  ['MANAGER', 'COMMERCIAL'],
    'DC':               ['MANAGER'],
    'BE':               ['ESTIMATEUR'],
    'BE + DG':          ['ESTIMATEUR', 'DIRECTEUR'],
    'BE Méthodes':      ['ESTIMATEUR'],
    'ADV':              ['ADV'],
    'Production':       ['ATELIER'],
    'Logistique':       ['CHAUFFEUR'],
    'Equipe pose':      ['POSEUR'],
    'Pose':             ['POSEUR'],
    'Pose + ADV':       ['POSEUR', 'ADV'],
    'ADV + Finance':    ['ADV', 'FINANCE'],
    'ADV + Pose':       ['ADV', 'POSEUR'],
    'SAV':              ['SAV'],
}


def _can_comment_phase(user, phase):
    """True if user's role matches the phase owner or user is management."""
    if user.is_superuser or user.role in ('DIRECTEUR', 'MANAGER'):
        return True
    allowed = _OWNER_LABEL_ROLES.get(phase.owner_label, [])
    return user.role in allowed


class ProjectAccessMixin(LoginRequiredMixin):
    """Mixin that raises 404 for users without access to the project."""

    def _get_project(self):
        pk = self.kwargs.get('pk') or self.kwargs.get('project_pk')
        project = get_object_or_404(Project, pk=pk)
        if not _visible_projects(self.request.user).filter(pk=project.pk).exists():
            raise Http404
        return project

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        # Validate project access early
        try:
            self._get_project()
        except Http404:
            raise
        return super().dispatch(request, *args, **kwargs)


class DashboardView(LoginRequiredMixin, TemplateView):
    """Vue tableau de bord — point d'entrée de l'application."""
    template_name = 'projects/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        all_projects = _visible_projects(self.request.user).select_related('manager')
        active = all_projects.exclude(status=Project.Status.CLOTURE)

        ctx['kpis'] = {
            'total': all_projects.count(),
            'actifs': active.count(),
            'en_production': all_projects.filter(status=Project.Status.PRODUCTION).count(),
            'en_pose': all_projects.filter(status=Project.Status.POSE).count(),
        }
        ctx['projets_actifs'] = active.order_by('-created_at')[:8]
        ctx['pipeline'] = [
            {'status': s, 'label': l, 'count': all_projects.filter(status=s).count()}
            for s, l in Project.Status.choices
        ]
        return ctx


class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    context_object_name = 'projects'

    def get_template_names(self):
        if self.request.GET.get('partial') == 'list':
            return ['projects/_project_list_partial.html']
        return ['projects/project_list.html']

    def get_queryset(self):
        qs = _visible_projects(self.request.user).select_related('manager')

        # Recherche textuelle : nom, référence, client, adresse
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(reference__icontains=q) |
                Q(client_name__icontains=q) |
                Q(address__icontains=q)
            )

        # Filtre statut
        status = self.request.GET.get('status', '')
        if status:
            qs = qs.filter(status=status)

        # Filtre manager
        manager_id = self.request.GET.get('manager', '')
        if manager_id:
            try:
                qs = qs.filter(manager_id=int(manager_id))
            except (ValueError, TypeError):
                pass

        # Filtre date début ≥
        start_after = self.request.GET.get('start_after', '')
        if start_after:
            qs = qs.filter(start_date__gte=start_after)

        # Filtre date fin ≤
        end_before = self.request.GET.get('end_before', '')
        if end_before:
            qs = qs.filter(end_date__lte=end_before)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['project_statuses'] = Project.Status.choices
        ctx['managers'] = (
            User.objects.filter(is_active_employee=True)
            .order_by('last_name', 'first_name')
        )
        # Valeurs courantes des filtres
        ctx['q']               = self.request.GET.get('q', '')
        ctx['selected_status'] = self.request.GET.get('status', '')
        ctx['selected_manager']= self.request.GET.get('manager', '')
        ctx['start_after']     = self.request.GET.get('start_after', '')
        ctx['end_before']      = self.request.GET.get('end_before', '')
        # Nombre de filtres actifs
        ctx['active_filters_count'] = sum([
            bool(ctx['q']),
            bool(ctx['selected_status']),
            bool(ctx['selected_manager']),
            bool(ctx['start_after']),
            bool(ctx['end_before']),
        ])
        # Total non filtré (pour affichage "X / Y projets")
        ctx['total_count'] = _visible_projects(self.request.user).count()
        return ctx


class ProjectCreateView(LoginRequiredMixin, View):
    """Création manuelle de projet — réservée aux administrateurs.
    Tous les autres rôles créent des projets via le workflow chiffrage.
    """
    template_name = 'projects/project_form.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def _ctx(self):
        team = User.objects.filter(is_active_employee=True).order_by('last_name')
        by_role = {}
        for u in team:
            by_role.setdefault(u.get_role_display(), []).append(u)
        return {
            'teams': team,
            'teams_by_role': by_role,
            'templates': ProjectTemplate.objects.filter(is_active=True),
            'statuses': Project.Status.choices,
            'errors': {},
            'post': {},
        }

    def get(self, request):
        return render(request, self.template_name, self._ctx())

    def post(self, request):
        data = request.POST
        files = request.FILES
        errors = {}

        name = data.get('name', '').strip()
        client_name = data.get('client_name', '').strip()
        manager_id = data.get('manager')
        status = data.get('status', Project.Status.AVANT_VENTE)

        if not name:
            errors['name'] = 'Le nom du projet est obligatoire.'
        if not client_name:
            errors['client_name'] = 'Le nom du client est obligatoire.'
        if not manager_id:
            errors['manager'] = 'Veuillez désigner un manager.'

        if errors:
            ctx = self._ctx()
            ctx.update({'errors': errors, 'post': data})
            return render(request, self.template_name, ctx)

        project = Project.objects.create(
            name=name,
            client_name=client_name,
            client_email=data.get('client_email', ''),
            client_phone=data.get('client_phone', ''),
            address=data.get('address', ''),
            manager_id=manager_id,
            estimator_id=data.get('estimator') or None,
            status=status,
            start_date=data.get('start_date') or None,
            end_date=data.get('end_date') or None,
            budget=data.get('budget') or None,
            notes=data.get('notes', ''),
            created_by=request.user,
            initial_order=files.get('initial_order') or None,
        )

        # Membres de l'équipe sélectionnés (checkboxes)
        member_ids = data.getlist('members')
        for uid in member_ids:
            ProjectMember.objects.get_or_create(
                project=project,
                user_id=uid,
                defaults={'added_by': request.user},
            )

        # Instancier depuis gabarit si sélectionné
        template_id = data.get('template')
        if template_id:
            try:
                tmpl = ProjectTemplate.objects.get(pk=template_id)
                project.create_from_template(tmpl)
            except ProjectTemplate.DoesNotExist:
                pass
        else:
            # Phases et tâches saisies manuellement (JSON)
            phases_json = data.get('phases_json', '').strip()
            if phases_json:
                try:
                    phases_data = json.loads(phases_json)
                    for i, ph in enumerate(phases_data):
                        phase_name = ph.get('name', '').strip()
                        if not phase_name:
                            continue
                        phase = Phase.objects.create(
                            project=project,
                            name=phase_name,
                            order=i,
                            estimated_days=int(ph.get('days') or 0),
                            is_active=(i == 0),
                        )
                        for j, tk in enumerate(ph.get('tasks', [])):
                            task_name = tk.get('name', '').strip()
                            if not task_name:
                                continue
                            Task.objects.create(
                                phase=phase,
                                name=task_name,
                                order=j,
                                required_role=tk.get('role', 'ANY'),
                                estimated_hours=float(tk.get('hours') or 0),
                                status=(
                                    Task.Status.ACTIVE
                                    if i == 0 and j == 0
                                    else Task.Status.EN_ATTENTE
                                ),
                            )
                except (json.JSONDecodeError, ValueError, KeyError):
                    pass

        messages.success(request, f'Projet « {project.name} » créé avec succès.')
        return redirect('projects:detail', pk=project.pk)


class TaskDetailView(LoginRequiredMixin, DetailView):
    """Détail d'une tâche : assignés, commentaires, pièces jointes."""
    model = Task
    template_name = 'projects/task_detail.html'
    context_object_name = 'task'

    def get_queryset(self):
        return Task.objects.select_related(
            'phase__project__manager',
        ).prefetch_related(
            'assignments__user',
            'comments__author',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        task = self.object
        ctx['project'] = task.phase.project
        ctx['phase'] = task.phase
        ctx['assignable_users'] = User.objects.filter(is_active_employee=True).order_by('last_name')
        ctx['assigned_ids'] = list(task.assignments.values_list('user_id', flat=True))
        return ctx


class TaskCommentCreateView(LoginRequiredMixin, View):
    """Crée un commentaire (texte + fichier + audio) sur une tâche."""

    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        text = request.POST.get('text', '').strip()
        attachment = request.FILES.get('attachment')
        audio = request.FILES.get('audio')

        if text or attachment or audio:
            TaskComment.objects.create(
                task=task,
                author=request.user,
                text=text,
                attachment=attachment or None,
                audio=audio or None,
            )
        return redirect('projects:task_detail', pk=task.pk)


class PhaseCommentCreateView(LoginRequiredMixin, View):
    """Crée un commentaire (texte + fichier + audio) sur une phase du planning.
    Seuls les rôles responsables de la phase (et les managers) peuvent commenter.
    """

    def post(self, request, pk):
        phase = get_object_or_404(Phase, pk=pk)
        if not _can_comment_phase(request.user, phase):
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden('Vous ne pouvez pas commenter cette étape.')
        text = request.POST.get('text', '').strip()
        attachment = request.FILES.get('attachment')
        audio = request.FILES.get('comment_audio')

        if text or attachment or audio:
            PhaseComment.objects.create(
                phase=phase,
                author=request.user,
                text=text,
                attachment=attachment or None,
                audio=audio or None,
            )
        return redirect('projects:detail', pk=phase.project_id)


class ProjectMessageCreateView(LoginRequiredMixin, View):
    """Crée un message dans le chat projet (HTMX)."""

    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        content = request.POST.get('content', '').strip()
        attachment = request.FILES.get('attachment')
        audio = request.FILES.get('audio')
        reply_to_id = request.POST.get('reply_to') or None

        reply_to = None
        if reply_to_id:
            try:
                reply_to = ProjectMessage.objects.get(pk=reply_to_id, project=project)
            except ProjectMessage.DoesNotExist:
                pass

        if content or attachment or audio:
            ProjectMessage.objects.create(
                project=project,
                author=request.user,
                content=content,
                reply_to=reply_to,
                attachment=attachment or None,
                attachment_name=attachment.name if attachment else '',
                audio=audio or None,
            )

        msgs = (
            ProjectMessage.objects
            .filter(project=project)
            .select_related('author', 'reply_to__author')
            .order_by('created_at')
        )
        return render(request, 'projects/partials/_chat_messages.html', {
            'chat_messages': msgs,
            'project': project,
            'request': request,
        })


class ProjectMessageListView(LoginRequiredMixin, View):
    """Rafraîchit les messages du chat (polling HTMX)."""

    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        msgs = (
            ProjectMessage.objects
            .filter(project=project)
            .select_related('author', 'reply_to__author')
            .order_by('created_at')
        )
        return render(request, 'projects/partials/_chat_messages.html', {
            'chat_messages': msgs,
            'project': project,
            'request': request,
        })


class PhaseActivateView(LoginRequiredMixin, View):
    """Active une phase (via HTMX POST)."""

    def post(self, request, pk):
        phase = get_object_or_404(Phase, pk=pk)
        if not phase.is_active and not phase.is_completed:
            phase.activate()
        return redirect('projects:detail', pk=phase.project_id)


class PhaseCompleteView(LoginRequiredMixin, View):
    """Clôture une phase et active la suivante (via HTMX POST)."""

    def post(self, request, pk):
        phase = get_object_or_404(Phase, pk=pk)
        if phase.is_active and not phase.is_completed:
            phase.complete()
        return redirect('projects:detail', pk=phase.project_id)


class TaskProgressView(LoginRequiredMixin, View):
    """Met à jour l'avancement d'une tâche + crée un commentaire optionnel."""

    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        try:
            value = int(request.POST.get('progress', 0))
        except (ValueError, TypeError):
            value = 0
        task.set_progress(value)

        # Commentaire optionnel joint à la mise à jour
        text = request.POST.get('comment_text', '').strip()
        attachment = request.FILES.get('comment_file')
        audio = request.FILES.get('comment_audio')
        if text or attachment or audio:
            TaskComment.objects.create(
                task=task,
                author=request.user,
                text=text,
                attachment=attachment or None,
                audio=audio or None,
            )

        return redirect('projects:detail', pk=task.phase.project_id)


class TaskAssignView(LoginRequiredMixin, View):
    """Affecte un utilisateur à une tâche (via HTMX POST)."""

    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        user_id = request.POST.get('user_id')
        if user_id:
            TaskAssignment.objects.get_or_create(
                task=task,
                user_id=user_id,
                defaults={'assigned_by': request.user, 'is_primary': True},
            )
        return redirect('projects:detail', pk=task.phase.project_id)


class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = 'projects/project_detail.html'
    context_object_name = 'project'

    def get_queryset(self):
        return _visible_projects(self.request.user).prefetch_related(
            'phases__tasks__assignments__user',
            'phases__tasks__comments',
            'phases__comments__author',
            'members__user',
        ).select_related('manager', 'estimator', 'chef_de_projet', 'chef_designe_par')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        project = self.object
        user = self.request.user
        phases = list(project.phases.order_by('order'))

        parties = {
            'A': {'label': PARTIE_LABELS['A'], 'color': 'foret',  'phases': []},
            'B': {'label': PARTIE_LABELS['B'], 'color': 'blue',   'phases': []},
            'C': {'label': PARTIE_LABELS['C'], 'color': 'amber',  'phases': []},
        }
        for ph in phases:
            key = ph.partie if ph.partie in parties else 'A'
            parties[key]['phases'].append(ph)

        # Attach comment permission directly to each phase object
        for ph in phases:
            ph.user_can_comment = _can_comment_phase(user, ph)

        ctx['parties']    = parties
        ctx['step_range'] = range(1, 19)
        ctx['chat_messages'] = (
            ProjectMessage.objects
            .filter(project=project)
            .select_related('author', 'reply_to__author')
            .order_by('created_at')
        )

        # Chef de projet
        ctx['can_designate_chef'] = user.is_superuser or user.role in ('DIRECTEUR', 'MANAGER')
        ctx['designatable_users'] = (
            User.objects.filter(is_active_employee=True).order_by('last_name', 'first_name')
            if ctx['can_designate_chef'] else []
        )

        # Project steps with per-step comment permission
        steps = list(
            ProjectStep.objects
            .filter(project=project)
            .prefetch_related('comments__author')
            .order_by('order')
        )
        for s in steps:
            s.user_can_comment = (
                user.is_superuser
                or user.role in ('DIRECTEUR', 'MANAGER')
                or user.role in (s.responsables_roles or [])
            )
        ctx['project_steps'] = steps
        return ctx


# ---------------------------------------------------------------------------
# Gestion des gabarits (Templates)
# ---------------------------------------------------------------------------

class TemplateListView(LoginRequiredMixin, ListView):
    """Liste tous les gabarits de projet."""
    model = ProjectTemplate
    template_name = 'projects/template_list.html'
    context_object_name = 'templates'
    ordering = ['name']

    def get_queryset(self):
        return ProjectTemplate.objects.prefetch_related(
            'phase_templates__task_templates'
        ).order_by('name')


class TemplateSaveView(LoginRequiredMixin, View):
    """Créer ou modifier un gabarit via formulaire Alpine.js dynamique."""
    template_name = 'projects/template_form.html'

    def _build_phases_json(self, template):
        phases = []
        for pt in template.phase_templates.order_by('order'):
            tasks = [
                {
                    'name': tt.name,
                    'role': tt.required_role,
                    'hours': str(tt.estimated_hours),
                }
                for tt in pt.task_templates.order_by('order')
            ]
            phases.append({
                'name': pt.name,
                'days': pt.estimated_days,
                'tasks': tasks,
            })
        return json.dumps(phases)

    def get(self, request, pk=None):
        tmpl = get_object_or_404(ProjectTemplate, pk=pk) if pk else None
        ctx = {
            'tmpl': tmpl,
            'phases_json': self._build_phases_json(tmpl) if tmpl else '[]',
        }
        return render(request, self.template_name, ctx)

    def post(self, request, pk=None):
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'

        if not name:
            tmpl = get_object_or_404(ProjectTemplate, pk=pk) if pk else None
            ctx = {
                'tmpl': tmpl,
                'phases_json': self._build_phases_json(tmpl) if tmpl else '[]',
                'error': 'Le nom du gabarit est obligatoire.',
            }
            return render(request, self.template_name, ctx)

        if pk:
            tmpl = get_object_or_404(ProjectTemplate, pk=pk)
            tmpl.name = name
            tmpl.description = description
            tmpl.is_active = is_active
            tmpl.save()
            # Supprimer les anciennes phases (cascade supprime les tâches)
            tmpl.phase_templates.all().delete()
            action = 'mis à jour'
        else:
            tmpl = ProjectTemplate.objects.create(
                name=name,
                description=description,
                is_active=is_active,
                created_by=request.user,
            )
            action = 'créé'

        # Recréer phases et tâches depuis le JSON Alpine.js
        phases_json = request.POST.get('phases_json', '[]').strip()
        try:
            phases_data = json.loads(phases_json)
            for i, ph in enumerate(phases_data):
                phase_name = ph.get('name', '').strip()
                if not phase_name:
                    continue
                phase = PhaseTemplate.objects.create(
                    template=tmpl,
                    name=phase_name,
                    order=i,
                    estimated_days=int(ph.get('days') or 0),
                )
                for j, tk in enumerate(ph.get('tasks', [])):
                    task_name = tk.get('name', '').strip()
                    if not task_name:
                        continue
                    TaskTemplate.objects.create(
                        phase=phase,
                        name=task_name,
                        order=j,
                        required_role=tk.get('role', 'ANY'),
                        estimated_hours=float(tk.get('hours') or 0),
                    )
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

        messages.success(request, f'Gabarit « {tmpl.name} » {action} avec succès.')
        return redirect('projects:template_list')


class TemplateDeleteView(LoginRequiredMixin, View):
    """Supprime un gabarit."""

    def post(self, request, pk):
        tmpl = get_object_or_404(ProjectTemplate, pk=pk)
        name = tmpl.name
        tmpl.delete()
        messages.success(request, f'Gabarit « {name} » supprimé.')
        return redirect('projects:template_list')


# ---------------------------------------------------------------------------
# Gestion de la pose
# ---------------------------------------------------------------------------

class PoseDashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard pose : tous les projets en phase POSE avec leur équipe."""
    template_name = 'projects/pose_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pose_projects = Project.objects.filter(
            status=Project.Status.POSE
        ).select_related('manager').prefetch_related(
            'installation_plan__chef_chantier',
            'installation_plan__team_members',
            'installation_reports',
        )
        # Tous les projets actifs pour vue globale
        all_active = Project.objects.exclude(
            status=Project.Status.CLOTURE
        ).select_related('manager').prefetch_related('installation_plan')

        poseurs = User.objects.filter(
            role__in=[User.Role.POSEUR, User.Role.CHAUFFEUR, User.Role.MANAGER],
            is_active_employee=True,
        ).order_by('last_name')

        ctx['pose_projects'] = pose_projects
        ctx['all_active']    = all_active
        ctx['poseurs']       = poseurs
        ctx['total_en_pose'] = pose_projects.count()
        return ctx


class InstallationPlanUpdateView(LoginRequiredMixin, View):
    """Crée ou met à jour le plan de pose d'un projet."""

    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        plan, _ = InstallationPlan.objects.get_or_create(project=project)

        plan.chef_chantier_id = request.POST.get('chef_chantier') or None
        plan.planned_start    = request.POST.get('planned_start') or None
        plan.planned_end      = request.POST.get('planned_end') or None
        plan.notes            = request.POST.get('notes', '').strip()
        plan.save()

        member_ids = request.POST.getlist('team_members')
        plan.team_members.set(member_ids)

        messages.success(request, 'Plan de pose mis à jour.')
        return redirect('projects:pose_project', pk=project.pk)


class PoseProjectView(LoginRequiredMixin, DetailView):
    """Détail pose d'un projet : équipe + rapports."""
    model = Project
    template_name = 'projects/pose_project.html'
    context_object_name = 'project'

    def get_queryset(self):
        return Project.objects.select_related('manager').prefetch_related(
            'installation_plan__chef_chantier',
            'installation_plan__team_members',
            'installation_reports__reported_by',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        project = self.object
        try:
            ctx['plan'] = project.installation_plan
        except InstallationPlan.DoesNotExist:
            ctx['plan'] = None

        ctx['reports'] = project.installation_reports.select_related('reported_by').order_by('-year', '-week_number')
        ctx['poseurs']  = User.objects.filter(
            role__in=[User.Role.POSEUR, User.Role.CHAUFFEUR, User.Role.MANAGER],
            is_active_employee=True,
        ).order_by('last_name')

        import datetime
        today = datetime.date.today()
        ctx['current_week'] = today.isocalendar()[1]
        ctx['current_year'] = today.year
        return ctx


class InstallationReportCreateView(LoginRequiredMixin, View):
    """Crée un rapport hebdomadaire de pose."""

    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        import datetime
        today = datetime.date.today()

        week = int(request.POST.get('week_number', today.isocalendar()[1]))
        year = int(request.POST.get('year', today.year))

        report, created = InstallationReport.objects.get_or_create(
            project=project,
            week_number=week,
            year=year,
            defaults={'reported_by': request.user},
        )
        if not created:
            report.reported_by = request.user

        report.progress_percent      = int(request.POST.get('progress_percent', 0))
        report.notes                 = request.POST.get('notes', '').strip()
        report.difficulties          = request.POST.get('difficulties', '').strip()
        report.incident              = bool(request.POST.get('incident'))
        report.incident_description  = request.POST.get('incident_description', '').strip()

        photo = request.FILES.get('photo')
        if photo:
            report.photo = photo

        report.save()
        messages.success(request, f'Rapport S{week}/{year} enregistré.')
        return redirect('projects:pose_project', pk=project.pk)


# ---------------------------------------------------------------------------
# Planning / Gantt (séquençage standard Bois&Co)
# ---------------------------------------------------------------------------

class ProjectGanttView(LoginRequiredMixin, View):
    template_name = 'projects/project_gantt.html'

    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        phases = list(project.phases.order_by('order'))

        # Regroupement par partie pour l'affichage
        parties = {
            'A': {'label': PARTIE_LABELS['A'], 'color': 'foret',  'phases': []},
            'B': {'label': PARTIE_LABELS['B'], 'color': 'blue',   'phases': []},
            'C': {'label': PARTIE_LABELS['C'], 'color': 'amber',  'phases': []},
        }
        for ph in phases:
            key = ph.partie if ph.partie in parties else 'A'
            parties[key]['phases'].append(ph)

        return render(request, self.template_name, {
            'project':    project,
            'phases':     phases,
            'parties':    parties,
            'step_range': range(1, 19),
        })


class GanttPhaseUpdateView(LoginRequiredMixin, View):
    """Met à jour les dates planifiées et le statut d'une phase du Gantt.
    Réservé aux rôles responsables de la phase (+ DIRECTEUR/MANAGER/admin).
    """

    def post(self, request, pk, phase_pk):
        project = get_object_or_404(Project, pk=pk)
        phase   = get_object_or_404(Phase, pk=phase_pk, project=project)
        if not _can_comment_phase(request.user, phase):
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden('Votre rôle ne vous permet pas de modifier cette étape.')

        phase.planned_start  = request.POST.get('planned_start')  or None
        phase.planned_end    = request.POST.get('planned_end')    or None
        phase.is_completed   = request.POST.get('is_completed') == '1'
        phase.is_active      = request.POST.get('is_active')    == '1'
        try:
            phase.progress = max(0, min(100, int(request.POST.get('progress', phase.progress))))
        except (ValueError, TypeError):
            pass
        # Forcer 100% si marquée terminée
        if phase.is_completed:
            phase.progress = 100
        phase.save(update_fields=['planned_start', 'planned_end', 'is_completed', 'is_active', 'progress'])

        messages.success(request, f'Étape "{phase.name}" mise à jour.')
        # Rediriger vers le projet si appelé depuis le détail, sinon vers le gantt
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER', '')
        if 'planning' not in next_url:
            return redirect('projects:detail', pk=project.pk)
        return redirect('projects:gantt', pk=project.pk)


# ---------------------------------------------------------------------------
# Vues Django — Chef de projet (formulaires HTML)
# ---------------------------------------------------------------------------

class ChefDesignFormView(LoginRequiredMixin, View):
    """POST depuis le formulaire de la fiche projet — désigne un chef de projet."""

    def post(self, request, pk):
        if not (request.user.is_superuser or request.user.role in ('DIRECTEUR', 'MANAGER')):
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden()
        project = get_object_or_404(Project, pk=pk)
        chef_id = request.POST.get('chef_id')
        if chef_id:
            try:
                chef = User.objects.get(pk=chef_id)
                desig_chef_de_projet(project, chef, request.user)
                messages.success(request, f'{chef.get_full_name()} désigné chef de projet.')
            except User.DoesNotExist:
                messages.error(request, 'Utilisateur introuvable.')
        return redirect('projects:detail', pk=pk)


class ChefValidateFormView(LoginRequiredMixin, View):
    """POST depuis la fiche projet — valide la désignation du chef de projet."""

    def post(self, request, pk):
        if not (request.user.is_superuser or request.user.role in ('DIRECTEUR', 'MANAGER')):
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden()
        project = get_object_or_404(Project, pk=pk)
        try:
            validate_chef(project, request.user)
            messages.success(request, 'Désignation validée.')
        except ValueError as e:
            messages.error(request, str(e))
        return redirect('projects:detail', pk=pk)


# ---------------------------------------------------------------------------
# Vues Django — Commentaires ProjectStep (formulaires HTML)
# ---------------------------------------------------------------------------

class ProjectStepCommentFormView(LoginRequiredMixin, View):
    """POST depuis la fiche projet — ajoute un commentaire sur une étape projet."""

    def post(self, request, pk):
        from .models import StepComment
        step = get_object_or_404(ProjectStep, pk=pk)
        can = (
            request.user.is_superuser
            or request.user.role in ('DIRECTEUR', 'MANAGER')
            or request.user.role in (step.responsables_roles or [])
        )
        if not can:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden('Vous ne pouvez pas commenter cette étape.')
        text = request.POST.get('text', '').strip()
        attachment = request.FILES.get('attachment') or None
        if text or attachment:
            StepComment.objects.create(step=step, author=request.user, text=text, attachment=attachment)
        return redirect('projects:detail', pk=step.project_id)


class ProjectStepCompleteFormView(LoginRequiredMixin, View):
    """POST depuis la fiche projet — marque une étape projet comme terminée."""

    def post(self, request, pk):
        step = get_object_or_404(ProjectStep, pk=pk)
        can = (
            request.user.is_superuser
            or request.user.role in ('DIRECTEUR', 'MANAGER')
            or step.project.chef_de_projet_id == request.user.pk
        )
        if not can:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden()
        complete_step(step, request.user)
        messages.success(request, f'Étape « {step.name} » marquée terminée.')
        return redirect('projects:detail', pk=step.project_id)


# ---------------------------------------------------------------------------
# API DRF — Chef de projet
# ---------------------------------------------------------------------------

class DesignChefView(APIView):
    """POST /api/projets/<pk>/chef/ — désigne un chef de projet."""
    permission_classes = [IsAuthenticated, IsManagerOrAbove]

    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        chef_id = request.data.get('chef_id')
        if not chef_id:
            return Response({'detail': 'chef_id requis.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            chef = User.objects.get(pk=chef_id)
        except User.DoesNotExist:
            return Response({'detail': 'Utilisateur introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        desig_chef_de_projet(project, chef, request.user)
        return Response({
            'chef_id': chef.pk,
            'chef_name': chef.get_full_name() or chef.username,
            'designe_le': project.chef_designe_le,
            'valide': project.chef_valide_par_admin,
        })


class ValidateChefView(APIView):
    """POST /api/projets/<pk>/chef/valider/ — valide la désignation (DIRECTEUR/MANAGER)."""
    permission_classes = [IsAuthenticated, IsManagerOrAbove]

    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        try:
            validate_chef(project, request.user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'valide': True, 'valide_le': project.chef_valide_le})


# ---------------------------------------------------------------------------
# API DRF — Étapes projet
# ---------------------------------------------------------------------------

class ProjectStepListView(generics.ListCreateAPIView):
    """GET/POST /api/projets/<pk>/etapes/"""
    serializer_class = ProjectStepSerializer
    permission_classes = [IsAuthenticated, IsProjectMember]

    def get_queryset(self):
        return ProjectStep.objects.filter(project_id=self.kwargs['pk']).order_by('order')

    def perform_create(self, serializer):
        project = get_object_or_404(Project, pk=self.kwargs['pk'])
        serializer.save(project=project)


class ProjectStepCompleteView(APIView):
    """POST /api/etapes/<pk>/terminer/ — marque une étape comme terminée."""
    permission_classes = [IsAuthenticated, IsChefDeProjet]

    def get_project_pk(self):
        step = get_object_or_404(ProjectStep, pk=self.kwargs['pk'])
        return step.project_id

    def post(self, request, pk):
        step = get_object_or_404(ProjectStep, pk=pk)
        # Check permission via project
        if not (
            request.user.is_superuser
            or request.user.role in ('DIRECTEUR', 'MANAGER')
            or step.project.chef_de_projet_id == request.user.pk
        ):
            return Response({'detail': 'Permission refusée.'}, status=status.HTTP_403_FORBIDDEN)
        complete_step(step, request.user)
        return Response({'is_completed': True, 'completed_at': step.completed_at})


# ---------------------------------------------------------------------------
# API DRF — Commentaires étapes
# ---------------------------------------------------------------------------

class StepCommentListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/etapes/<pk>/commentaires/
    GET: accessible à tous les membres du projet.
    POST: réservé aux rôles dans step.responsables_roles (+ DIRECTEUR/MANAGER).
    """
    serializer_class = StepCommentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return StepComment.objects.filter(step_id=self.kwargs['pk']).select_related('author')

    def create(self, request, *args, **kwargs):
        step = get_object_or_404(ProjectStep, pk=self.kwargs['pk'])
        user = request.user
        can = (
            user.is_superuser
            or user.role in ('DIRECTEUR', 'MANAGER')
            or user.role in (step.responsables_roles or [])
        )
        if not can:
            return Response(
                {'detail': 'Vous ne pouvez pas commenter cette étape.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        step = get_object_or_404(ProjectStep, pk=self.kwargs['pk'])
        serializer.save(step=step, author=self.request.user)


# ---------------------------------------------------------------------------
# API DRF — Commentaires projet
# ---------------------------------------------------------------------------

class ProjectCommentListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/projets/<pk>/commentaires/"""
    serializer_class = ProjectCommentSerializer
    permission_classes = [IsAuthenticated, IsProjectMember]

    def get_queryset(self):
        return ProjectComment.objects.filter(project_id=self.kwargs['pk']).select_related('author')

    def perform_create(self, serializer):
        project = get_object_or_404(Project, pk=self.kwargs['pk'])
        serializer.save(project=project, author=self.request.user)
