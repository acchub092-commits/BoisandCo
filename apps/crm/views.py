import json
import os
from datetime import date, timedelta
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Sum, Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import TemplateView, DetailView, View, ListView

from apps.users.models import User
from apps.projects.models import Project
from .models import (
    Lead, LeadNote, Activity, ACTIVITY_ICONS,
    Appointment, LeadDocument, LeadActivityLog, ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE,
)
from .permissions import is_director, is_commercial, can_access_crm


# ── Couleurs et labels des colonnes ─────────────────────────────────────────
COLUMN_META = {
    Lead.Status.VISITE:        {'label': 'Visites',       'color': '#64748b', 'bg': '#f1f5f9'},
    Lead.Status.OPPORTUNITE:   {'label': 'Opportunités',  'color': '#2563eb', 'bg': '#eff6ff'},
    Lead.Status.QUALIFICATION: {'label': 'Qualification', 'color': '#d97706', 'bg': '#fffbeb'},
    Lead.Status.CHIFFRAGE:     {'label': 'Chiffrage',     'color': '#7c3aed', 'bg': '#f5f3ff'},
    Lead.Status.OFFRE:         {'label': 'Offre envoyée', 'color': '#0891b2', 'bg': '#ecfeff'},
}


class PipelineView(LoginRequiredMixin, TemplateView):
    """Vue Kanban du pipeline commercial."""
    template_name = 'crm/pipeline.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        leads = Lead.objects.select_related('assigned_to').filter(
            status__in=Lead.PIPELINE_STAGES
        )

        columns = []
        for status in Lead.PIPELINE_STAGES:
            meta  = COLUMN_META[status]
            items = [l for l in leads if l.status == status]
            total_budget = sum(
                l.budget_mad for l in items if l.budget_mad
            )
            columns.append({
                'status':       status,
                'label':        meta['label'],
                'color':        meta['color'],
                'bg':           meta['bg'],
                'leads':        items,
                'count':        len(items),
                'total_budget': total_budget,
            })

        ctx['columns']        = columns
        ctx['statuses']       = Lead.Status.choices
        ctx['won_leads']      = Lead.objects.filter(status=Lead.Status.GAGNEE).select_related('assigned_to')[:10]
        ctx['lost_leads']     = Lead.objects.filter(status=Lead.Status.PERDUE).select_related('assigned_to')[:10]
        ctx['won_count']      = Lead.objects.filter(status=Lead.Status.GAGNEE).count()
        ctx['lost_count']     = Lead.objects.filter(status=Lead.Status.PERDUE).count()
        ctx['total_pipeline'] = sum(
            l.budget_mad for l in leads if l.budget_mad
        )
        ctx['kpis'] = {
            'visite':  leads.filter(status=Lead.Status.VISITE).count(),
            'offre':   leads.filter(status=Lead.Status.OFFRE).count(),
            'gagnes':  ctx['won_count'],
            'perdus':  ctx['lost_count'],
        }
        return ctx


class LeadCreateView(LoginRequiredMixin, View):
    template_name = 'crm/lead_form.html'

    def _ctx(self, lead=None, errors=None, post=None):
        import datetime
        from types import SimpleNamespace
        _p = post or {}

        def v(f, default=''):
            """POST value → lead value → default."""
            pval = _p.get(f)
            if pval is not None and pval != '':
                return pval
            val = getattr(lead, f, None) if lead else None
            if isinstance(val, (datetime.date, datetime.datetime)):
                return val.strftime('%Y-%m-%d')
            return val if val is not None else default

        # SimpleNamespace so Django templates can do vals.field_name via getattr
        vals = SimpleNamespace(
            contact_name      = v('contact_name'),
            company           = v('company'),
            project_name      = v('project_name'),
            location          = v('location'),
            email             = v('email'),
            phone             = v('phone'),
            client_type       = v('client_type'),
            project_type      = v('project_type'),
            products          = v('products'),
            status            = v('status'),
            potential         = v('potential'),
            canal_origine     = v('canal_origine'),
            flux_type         = v('flux_type'),
            assigned_to       = str(v('assigned_to_id') or ''),
            next_followup_date= v('next_followup_date'),
            budget_mad        = v('budget_mad', ''),
            nb_logements      = v('nb_logements', ''),
            start_date_est    = v('start_date_est'),
            end_date_est      = v('end_date_est'),
            probability       = v('probability'),
            competitor        = v('competitor'),
            strategic_comment = v('strategic_comment'),
            offer_amount_ht   = v('offer_amount_ht', ''),
            offer_sent_date   = v('offer_sent_date'),
            offer_validity_days = v('offer_validity_days', 30),
            loss_reason       = v('loss_reason'),
            loss_notes        = v('loss_notes'),
        )

        return {
            'lead':         lead,
            'vals':         vals,
            'errors':       errors or {},
            'statuses':     Lead.Status.choices,
            'potentials':   Lead.Potential.choices,
            'canaux':       Lead.Canal.choices,
            'flux_types':   Lead.FluxType.choices,
            'probs':        Lead.Probability.choices,
            'loss_reasons': Lead.LossReason.choices,
            'team':         User.objects.filter(is_active_employee=True).order_by('last_name'),
        }

    def get(self, request, pk=None):
        lead = get_object_or_404(Lead, pk=pk) if pk else None
        return render(request, self.template_name, self._ctx(lead=lead))

    def post(self, request, pk=None):
        lead = get_object_or_404(Lead, pk=pk) if pk else None
        data   = request.POST
        errors = {}

        contact_name = data.get('contact_name', '').strip()
        project_name = data.get('project_name', '').strip()
        if not contact_name:
            errors['contact_name'] = 'Le nom du contact est obligatoire.'
        if not project_name:
            errors['project_name'] = 'Le nom du projet est obligatoire.'

        if errors:
            return render(request, self.template_name, self._ctx(lead=lead, errors=errors, post=data))

        fields = {
            'contact_name':        contact_name,
            'project_name':        project_name,
            'company':             data.get('company', '').strip(),
            'client_type':         data.get('client_type', '').strip(),
            'email':               data.get('email', '').strip(),
            'phone':               data.get('phone', '').strip(),
            'location':            data.get('location', '').strip(),
            'project_type':        data.get('project_type', '').strip(),
            'products':            data.get('products', '').strip(),
            'potential':           data.get('potential', Lead.Potential.MOYEN),
            'canal_origine':       data.get('canal_origine', ''),
            'flux_type':           data.get('flux_type', ''),
            'status':              data.get('status', Lead.Status.VISITE),
            'next_followup_date':  data.get('next_followup_date') or None,
            'budget_mad':          data.get('budget_mad') or None,
            'nb_logements':        data.get('nb_logements') or None,
            'start_date_est':      data.get('start_date_est') or None,
            'end_date_est':        data.get('end_date_est') or None,
            'probability':         data.get('probability', ''),
            'competitor':          data.get('competitor', '').strip(),
            'strategic_comment':   data.get('strategic_comment', '').strip(),
            'offer_amount_ht':     data.get('offer_amount_ht') or None,
            'offer_sent_date':     data.get('offer_sent_date') or None,
            'offer_validity_days': int(data.get('offer_validity_days') or 30),
            'loss_reason':         data.get('loss_reason', ''),
            'loss_notes':          data.get('loss_notes', '').strip(),
            'assigned_to_id':      data.get('assigned_to') or None,
        }

        if lead:
            for k, v in fields.items():
                setattr(lead, k, v)
            lead.save()
            messages.success(request, f'Lead « {lead.project_name} » mis à jour.')
        else:
            lead = Lead.objects.create(**fields, created_by=request.user)
            messages.success(request, f'Lead « {lead.project_name} » créé.')

        return redirect('crm:lead_detail', pk=lead.pk)


class LeadDetailView(LoginRequiredMixin, DetailView):
    model = Lead
    template_name = 'crm/lead_detail.html'
    context_object_name = 'lead'

    def get_queryset(self):
        return Lead.objects.select_related('assigned_to', 'created_by', 'project').prefetch_related('notes__author')

    def get_queryset(self):
        return Lead.objects.select_related(
            'assigned_to', 'created_by', 'project'
        ).prefetch_related('notes__author', 'activities__assigned_to', 'chiffrages')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['statuses']      = Lead.Status.choices
        ctx['pipeline_meta'] = COLUMN_META
        ctx['projects']      = Project.objects.exclude(
            lead__isnull=False
        ).order_by('-created_at')[:20]
        ctx['activity_types']  = Activity.Type.choices
        ctx['activity_icons']  = ACTIVITY_ICONS
        ctx['team']            = User.objects.filter(is_active_employee=True).order_by('last_name')
        return ctx


class LeadStatusUpdateView(LoginRequiredMixin, View):
    """Change le statut d'un lead (glisser-déposer ou bouton)."""

    def post(self, request, pk):
        lead   = get_object_or_404(Lead, pk=pk)
        status = request.POST.get('status')
        if status in dict(Lead.Status.choices):
            lead.status = status
            # Si gagné, effacer motif perte
            if status == Lead.Status.GAGNEE:
                lead.loss_reason = ''
                lead.loss_notes  = ''
            lead.save(update_fields=['status', 'loss_reason', 'loss_notes', 'updated_at'])
            messages.success(request, f'Statut mis à jour : {lead.get_status_display()}')
        return redirect('crm:lead_detail', pk=lead.pk)


class LeadDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)
        name = lead.project_name
        lead.delete()
        messages.success(request, f'Lead « {name} » supprimé.')
        return redirect('crm:pipeline')


class LeadNoteCreateView(LoginRequiredMixin, View):
    """Ajoute une note / historique d'échange sur un lead."""

    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)
        text = request.POST.get('text', '').strip()
        if text:
            LeadNote.objects.create(lead=lead, author=request.user, text=text)
        return redirect('crm:lead_detail', pk=lead.pk)


class LeadLinkProjectView(LoginRequiredMixin, View):
    """Lie un lead gagné à un dossier projet existant."""

    def post(self, request, pk):
        lead       = get_object_or_404(Lead, pk=pk)
        project_id = request.POST.get('project_id')
        if project_id:
            try:
                project = Project.objects.get(pk=project_id)
                lead.project = project
                lead.status  = Lead.Status.GAGNEE
                lead.save(update_fields=['project', 'status', 'updated_at'])
                messages.success(request, f'Lead lié au projet {project.reference}.')
            except Project.DoesNotExist:
                messages.error(request, 'Projet introuvable.')
        return redirect('crm:lead_detail', pk=lead.pk)


# ── Activités ────────────────────────────────────────────────────────────────

class ActivityCreateView(LoginRequiredMixin, View):
    """Crée une activité depuis un lead ou depuis l'agenda."""

    def post(self, request, lead_pk=None):
        lead = get_object_or_404(Lead, pk=lead_pk) if lead_pk else None

        subject       = request.POST.get('subject', '').strip()
        activity_type = request.POST.get('activity_type', Activity.Type.APPEL)
        planned_date  = request.POST.get('planned_date', '')
        planned_time  = request.POST.get('planned_time', '09:00')
        duration_min  = int(request.POST.get('duration_min', 60) or 60)
        location      = request.POST.get('location', '').strip()
        assigned_to_id = request.POST.get('assigned_to') or None
        compte_rendu  = request.POST.get('compte_rendu', '').strip()
        status        = request.POST.get('status', Activity.Status.PLANIFIE)

        if subject and planned_date:
            from datetime import datetime
            try:
                dt_str = f'{planned_date} {planned_time}'
                planned_at = timezone.make_aware(
                    datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
                )
            except ValueError:
                planned_at = timezone.now()

            Activity.objects.create(
                lead=lead,
                activity_type=activity_type,
                subject=subject,
                planned_at=planned_at,
                duration_min=duration_min,
                location=location,
                assigned_to_id=assigned_to_id or request.user.pk,
                status=status,
                compte_rendu=compte_rendu,
                created_by=request.user,
            )
            messages.success(request, 'Activité enregistrée.')

        if lead:
            return redirect('crm:lead_detail', pk=lead.pk)
        return redirect('crm:agenda')


class ActivityUpdateView(LoginRequiredMixin, View):
    """Modifie une activité et/ou ajoute un compte rendu."""

    def get(self, request, pk):
        activity = get_object_or_404(Activity, pk=pk)
        return render(request, 'crm/activity_form.html', {
            'activity':       activity,
            'activity_types': Activity.Type.choices,
            'team':           User.objects.filter(is_active_employee=True).order_by('last_name'),
            'leads':          Lead.objects.filter(status__in=Lead.PIPELINE_STAGES).order_by('project_name'),
        })

    def post(self, request, pk):
        activity = get_object_or_404(Activity, pk=pk)
        from datetime import datetime

        planned_date = request.POST.get('planned_date', '')
        planned_time = request.POST.get('planned_time', '09:00')
        if planned_date:
            try:
                dt_str = f'{planned_date} {planned_time}'
                activity.planned_at = timezone.make_aware(
                    datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
                )
            except ValueError:
                pass

        activity.subject       = request.POST.get('subject', activity.subject).strip()
        activity.activity_type = request.POST.get('activity_type', activity.activity_type)
        activity.duration_min  = int(request.POST.get('duration_min', activity.duration_min) or 60)
        activity.location      = request.POST.get('location', '').strip()
        activity.status        = request.POST.get('status', activity.status)
        activity.compte_rendu  = request.POST.get('compte_rendu', '').strip()
        assigned_id = request.POST.get('assigned_to')
        if assigned_id:
            activity.assigned_to_id = assigned_id
        lead_id = request.POST.get('lead_id')
        activity.lead_id = lead_id if lead_id else None
        activity.save()
        messages.success(request, 'Activité mise à jour.')

        if activity.lead_id:
            return redirect('crm:lead_detail', pk=activity.lead_id)
        return redirect('crm:agenda')


class ActivityDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        activity = get_object_or_404(Activity, pk=pk)
        lead_pk = activity.lead_id
        activity.delete()
        messages.success(request, 'Activité supprimée.')
        if lead_pk:
            return redirect('crm:lead_detail', pk=lead_pk)
        return redirect('crm:agenda')


# ── Agenda ───────────────────────────────────────────────────────────────────

class AgendaView(LoginRequiredMixin, TemplateView):
    """
    Agenda partagé des activités commerciales.
    Le directeur voit tous les commerciaux ; un commercial voit uniquement les siennes.
    """
    template_name = 'crm/agenda.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        # Filtre par commercial
        filter_user_id = self.request.GET.get('commercial')
        periode        = self.request.GET.get('periode', 'semaine')  # semaine / mois / tout

        qs = Activity.objects.select_related('lead', 'assigned_to').order_by('planned_at')

        # Commerciaux sans rôle directeur/manager voient uniquement les leurs
        if not user.is_manager_or_above:
            qs = qs.filter(assigned_to=user)
        elif filter_user_id:
            qs = qs.filter(assigned_to_id=filter_user_id)

        # Filtre temporel
        today = date.today()
        if periode == 'semaine':
            start = today - timedelta(days=today.weekday())
            end   = start + timedelta(days=6)
            qs    = qs.filter(planned_at__date__range=[start, end])
        elif periode == 'mois':
            start = today.replace(day=1)
            if today.month == 12:
                end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            qs = qs.filter(planned_at__date__range=[start, end])

        # Stats rapides
        all_qs = Activity.objects.select_related('assigned_to')
        if not user.is_manager_or_above:
            all_qs = all_qs.filter(assigned_to=user)

        ctx.update({
            'activities':      qs,
            'periode':         periode,
            'filter_user_id':  filter_user_id,
            'team':            User.objects.filter(
                is_active_employee=True,
                role__in=['COMMERCIAL', 'MANAGER', 'DIRECTEUR']
            ).order_by('last_name'),
            'activity_types':  Activity.Type.choices,
            'activity_icons':  ACTIVITY_ICONS,
            'leads_actifs':    Lead.objects.filter(
                status__in=Lead.PIPELINE_STAGES
            ).order_by('project_name'),
            'today':           today,
            'stats': {
                'total':    all_qs.count(),
                'planifie': all_qs.filter(status='PLANIFIE').count(),
                'realise':  all_qs.filter(status='REALISE').count(),
                'en_retard': all_qs.filter(
                    status='PLANIFIE', planned_at__lt=timezone.now()
                ).count(),
            },
        })
        return ctx


# ── Chiffrage depuis lead ─────────────────────────────────────────────────────

class LeadChiffrageCreateView(LoginRequiredMixin, View):
    """Redirige vers la création de chiffrage en pré-remplissant depuis le lead."""

    def get(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)
        from django.urls import reverse
        from urllib.parse import urlencode
        params = urlencode({
            'lead_id':    lead.pk,
            'client_nom': lead.company or lead.contact_name,
            'description': f'{lead.project_name} — {lead.location}',
        })
        return redirect(f"{reverse('chiffrage:create')}?{params}")


# ═════════════════════════════════════════════════════════════════════════════
# NOUVEAU — Dashboard CRM enrichi
# ═════════════════════════════════════════════════════════════════════════════

class CRMDashboardView(LoginRequiredMixin, TemplateView):
    """
    Dashboard CRM avec KPIs, pipeline valeur, leads à valider,
    prochains RDV et journal d'activité récent.
    """
    template_name = 'crm/crm_dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        if not can_access_crm(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx   = super().get_context_data(**kwargs)
        user  = self.request.user
        today = date.today()

        # Queryset de base selon le rôle
        qs_base = Lead.objects.all() if is_director(user) else Lead.objects.filter(assigned_to=user)

        # KPIs pipeline
        actifs   = qs_base.filter(status__in=Lead.PIPELINE_STAGES)
        pipeline_value = actifs.aggregate(total=Sum('budget_mad'))['total'] or 0

        # Opportunités à valider (visibles seulement par directeur)
        pending = Lead.objects.filter(
            workflow_status=Lead.WorkflowStatus.PENDING_VALIDATION
        ) if is_director(user) else Lead.objects.none()

        # Prochains RDV (7 jours)
        rdv_qs = Appointment.objects.select_related('lead', 'created_by').filter(
            scheduled_at__gte=timezone.now(),
            scheduled_at__date__lte=today + timedelta(days=7),
            status=Appointment.Status.PLANIFIE,
        )
        if not is_director(user):
            rdv_qs = rdv_qs.filter(Q(lead__assigned_to=user) | Q(attendees=user)).distinct()

        # Journal récent
        logs_qs = LeadActivityLog.objects.select_related('lead', 'performed_by')
        if not is_director(user):
            logs_qs = logs_qs.filter(lead__assigned_to=user)
        recent_logs = logs_qs.order_by('-created_at')[:15]

        # Répartition par statut
        status_counts = {
            s: qs_base.filter(status=s).count()
            for s in [Lead.Status.VISITE, Lead.Status.OPPORTUNITE,
                      Lead.Status.QUALIFICATION, Lead.Status.CHIFFRAGE,
                      Lead.Status.OFFRE, Lead.Status.GAGNEE, Lead.Status.PERDUE]
        }

        ctx.update({
            'kpis': {
                'actifs':         actifs.count(),
                'pipeline_value': pipeline_value,
                'rdv_semaine':    rdv_qs.count(),
                'a_valider':      pending.count(),
                'gagnes_mois':    qs_base.filter(
                    status=Lead.Status.GAGNEE,
                    updated_at__month=today.month, updated_at__year=today.year,
                ).count(),
            },
            'pending_leads':  pending.select_related('assigned_to', 'created_by').order_by('-updated_at')[:10],
            'prochains_rdv':  rdv_qs.order_by('scheduled_at')[:8],
            'recent_logs':    recent_logs,
            'status_counts':  status_counts,
            'is_director':    is_director(user),
        })
        return ctx


# ═════════════════════════════════════════════════════════════════════════════
# Workflow validation — Lead
# ═════════════════════════════════════════════════════════════════════════════

class LeadSubmitView(LoginRequiredMixin, View):
    """
    Commercial soumet un lead DRAFT → PENDING_VALIDATION.
    Notifie le DC via le système de notifications in-app.
    """
    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)

        if not (is_commercial(request.user) or is_director(request.user)):
            raise PermissionDenied

        if lead.workflow_status != Lead.WorkflowStatus.DRAFT:
            messages.error(request, "Ce lead n'est pas en brouillon.")
            return redirect('crm:lead_detail', pk=pk)

        lead.workflow_status = Lead.WorkflowStatus.PENDING_VALIDATION
        lead.source          = Lead.Source.COMMERCIAL_CREATED
        lead.save(update_fields=['workflow_status', 'source', 'updated_at'])

        LeadActivityLog.objects.create(
            lead=lead,
            log_type=LeadActivityLog.LogType.STATUS_CHANGE,
            content=f'Soumis à validation par {request.user.get_full_name()}.',
            performed_by=request.user,
        )

        # Notification in-app aux directeurs
        _notify_directors(
            request,
            title='Opportunité à valider',
            message=f'« {lead.project_name} » soumise par {request.user.get_full_name()}.',
        )

        messages.success(request, 'Opportunité soumise à validation.')
        return redirect('crm:lead_detail', pk=pk)


class LeadValidateView(LoginRequiredMixin, View):
    """DC valide une opportunité PENDING → VALIDATED."""

    def post(self, request, pk):
        if not is_director(request.user):
            raise PermissionDenied

        lead = get_object_or_404(Lead, pk=pk)
        if lead.workflow_status != Lead.WorkflowStatus.PENDING_VALIDATION:
            messages.error(request, "Ce lead n'est pas en attente de validation.")
            return redirect('crm:lead_detail', pk=pk)

        lead.workflow_status = Lead.WorkflowStatus.VALIDATED
        lead.validated_by    = request.user
        lead.validated_at    = timezone.now()
        lead.save(update_fields=['workflow_status', 'validated_by', 'validated_at', 'updated_at'])

        LeadActivityLog.objects.create(
            lead=lead,
            log_type=LeadActivityLog.LogType.VALIDATION,
            content=f'Validé par {request.user.get_full_name()}.',
            performed_by=request.user,
        )
        messages.success(request, f'Opportunité « {lead.project_name} » validée.')
        return redirect('crm:lead_detail', pk=pk)


class LeadRejectView(LoginRequiredMixin, View):
    """DC rejette une opportunité → retour DRAFT avec commentaire."""

    def post(self, request, pk):
        if not is_director(request.user):
            raise PermissionDenied

        lead    = get_object_or_404(Lead, pk=pk)
        comment = request.POST.get('comment', '').strip()

        lead.workflow_status = Lead.WorkflowStatus.DRAFT
        lead.save(update_fields=['workflow_status', 'updated_at'])

        LeadActivityLog.objects.create(
            lead=lead,
            log_type=LeadActivityLog.LogType.STATUS_CHANGE,
            content=f'Rejeté par {request.user.get_full_name()}. {comment}'.strip(),
            performed_by=request.user,
        )
        messages.warning(request, f'Opportunité « {lead.project_name} » renvoyée en brouillon.')
        return redirect('crm:lead_detail', pk=pk)


class LeadAssignView(LoginRequiredMixin, View):
    """DC assigne ou réassigne un lead à un commercial."""

    def post(self, request, pk):
        if not is_director(request.user):
            raise PermissionDenied

        lead    = get_object_or_404(Lead, pk=pk)
        user_id = request.POST.get('assigned_to')
        commercial = get_object_or_404(User, pk=user_id) if user_id else None

        old_assignee  = lead.assigned_to
        lead.assigned_to = commercial
        lead.save(update_fields=['assigned_to', 'updated_at'])

        who = commercial.get_full_name() if commercial else '—'
        LeadActivityLog.objects.create(
            lead=lead,
            log_type=LeadActivityLog.LogType.ASSIGNMENT,
            content=f'Assigné à {who} (était : {old_assignee.get_full_name() if old_assignee else "—"}).',
            performed_by=request.user,
        )
        messages.success(request, f'Opportunité assignée à {who}.')
        return redirect('crm:lead_detail', pk=pk)


# ═════════════════════════════════════════════════════════════════════════════
# Rendez-vous (Appointment)
# ═════════════════════════════════════════════════════════════════════════════

class AppointmentCreateView(LoginRequiredMixin, View):
    """Planifie un RDV sur un lead."""

    def get(self, request, lead_pk):
        lead = get_object_or_404(Lead, pk=lead_pk)
        _check_lead_access(request.user, lead)
        team = User.objects.filter(is_active=True, role__in=['DIRECTEUR', 'MANAGER', 'COMMERCIAL']).order_by('last_name')
        return render(request, 'crm/appointment_form.html', {
            'lead':               lead,
            'appointment_types':  Appointment.AppointmentType.choices,
            'team':               team,
            'is_create':          True,
        })

    def post(self, request, lead_pk):
        lead = get_object_or_404(Lead, pk=lead_pk)
        _check_lead_access(request.user, lead)

        title      = request.POST.get('title', '').strip()
        apt_type   = request.POST.get('appointment_type', Appointment.AppointmentType.DECOUVERTE)
        sched_date = request.POST.get('scheduled_date', '')
        sched_time = request.POST.get('scheduled_time', '09:00')
        duration   = int(request.POST.get('duration_minutes', 60) or 60)
        location   = request.POST.get('location', '').strip()
        attendee_ids = request.POST.getlist('attendees')

        if not title or not sched_date:
            messages.error(request, 'Titre et date sont obligatoires.')
            return redirect('crm:appointment_create', lead_pk=lead_pk)

        from datetime import datetime
        try:
            scheduled_at = timezone.make_aware(
                datetime.strptime(f'{sched_date} {sched_time}', '%Y-%m-%d %H:%M')
            )
        except ValueError:
            scheduled_at = timezone.now()

        apt = Appointment.objects.create(
            lead=lead,
            title=title,
            appointment_type=apt_type,
            scheduled_at=scheduled_at,
            duration_minutes=duration,
            location=location,
            status=Appointment.Status.PLANIFIE,
            created_by=request.user,
        )
        if attendee_ids:
            apt.attendees.set(User.objects.filter(pk__in=attendee_ids))

        LeadActivityLog.objects.create(
            lead=lead,
            log_type=LeadActivityLog.LogType.RDV_ADDED,
            content=f'RDV planifié : « {title} » le {scheduled_at:%d/%m/%Y à %H:%M}.',
            performed_by=request.user,
        )
        messages.success(request, 'Rendez-vous planifié.')
        return redirect('crm:lead_detail', pk=lead_pk)


class AppointmentUpdateView(LoginRequiredMixin, View):
    """Modifie un RDV existant."""

    def get(self, request, pk):
        apt  = get_object_or_404(Appointment, pk=pk)
        _check_lead_access(request.user, apt.lead)
        team = User.objects.filter(is_active=True, role__in=['DIRECTEUR', 'MANAGER', 'COMMERCIAL']).order_by('last_name')
        return render(request, 'crm/appointment_form.html', {
            'lead':              apt.lead,
            'appointment':       apt,
            'appointment_types': Appointment.AppointmentType.choices,
            'team':              team,
            'is_create':         False,
        })

    def post(self, request, pk):
        apt = get_object_or_404(Appointment, pk=pk)
        _check_lead_access(request.user, apt.lead)

        from datetime import datetime
        sched_date = request.POST.get('scheduled_date', '')
        sched_time = request.POST.get('scheduled_time', '09:00')
        if sched_date:
            try:
                apt.scheduled_at = timezone.make_aware(
                    datetime.strptime(f'{sched_date} {sched_time}', '%Y-%m-%d %H:%M')
                )
            except ValueError:
                pass

        apt.title            = request.POST.get('title', apt.title).strip()
        apt.appointment_type = request.POST.get('appointment_type', apt.appointment_type)
        apt.duration_minutes = int(request.POST.get('duration_minutes', apt.duration_minutes) or 60)
        apt.location         = request.POST.get('location', '').strip()
        apt.status           = request.POST.get('status', apt.status)
        apt.save()

        attendee_ids = request.POST.getlist('attendees')
        if attendee_ids:
            apt.attendees.set(User.objects.filter(pk__in=attendee_ids))

        messages.success(request, 'Rendez-vous mis à jour.')
        return redirect('crm:lead_detail', pk=apt.lead_id)


class AppointmentReportView(LoginRequiredMixin, View):
    """Rédige / modifie le compte rendu d'un RDV."""

    def get(self, request, pk):
        apt = get_object_or_404(Appointment, pk=pk)
        _check_lead_access(request.user, apt.lead)
        return render(request, 'crm/appointment_report.html', {
            'appointment': apt,
            'doc_types':   LeadDocument.DocType.choices,
        })

    def post(self, request, pk):
        apt    = get_object_or_404(Appointment, pk=pk)
        _check_lead_access(request.user, apt.lead)
        report = request.POST.get('report', '').strip()

        apt.report = report
        apt.status = Appointment.Status.REALISE
        if not apt.report_written_at:
            apt.report_written_at = timezone.now()
        apt.save(update_fields=['report', 'status', 'report_written_at', 'updated_at'])

        # Upload de fichiers joints au CR
        files = request.FILES.getlist('files')
        for f in files:
            _save_lead_document(
                lead=apt.lead, uploaded_by=request.user,
                file=f, title=f.name,
                doc_type=request.POST.get('doc_type', LeadDocument.DocType.MEETING_REPORT),
                appointment=apt,
            )

        LeadActivityLog.objects.create(
            lead=apt.lead,
            log_type=LeadActivityLog.LogType.RDV_DONE,
            content=f'Compte rendu rédigé pour le RDV « {apt.title} ».',
            performed_by=request.user,
        )
        messages.success(request, 'Compte rendu enregistré.')
        return redirect('crm:lead_detail', pk=apt.lead_id)


# ═════════════════════════════════════════════════════════════════════════════
# Documents
# ═════════════════════════════════════════════════════════════════════════════

class LeadDocumentUploadView(LoginRequiredMixin, View):
    """Upload d'un document sur une opportunité."""

    def get(self, request, lead_pk):
        lead = get_object_or_404(Lead, pk=lead_pk)
        _check_lead_access(request.user, lead)
        return render(request, 'crm/document_upload.html', {
            'lead':      lead,
            'doc_types': LeadDocument.DocType.choices,
        })

    def post(self, request, lead_pk):
        lead = get_object_or_404(Lead, pk=lead_pk)
        _check_lead_access(request.user, lead)

        f        = request.FILES.get('file')
        title    = request.POST.get('title', '').strip()
        doc_type = request.POST.get('doc_type', LeadDocument.DocType.OTHER)
        desc     = request.POST.get('description', '').strip()

        if not f:
            messages.error(request, 'Aucun fichier sélectionné.')
            return redirect('crm:document_upload', lead_pk=lead_pk)

        ext = os.path.splitext(f.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            messages.error(request, f'Extension non autorisée : {ext}')
            return redirect('crm:document_upload', lead_pk=lead_pk)

        if f.size > MAX_UPLOAD_SIZE:
            messages.error(request, 'Fichier trop lourd (max 20 Mo).')
            return redirect('crm:document_upload', lead_pk=lead_pk)

        doc = _save_lead_document(
            lead=lead, uploaded_by=request.user,
            file=f, title=title or f.name,
            doc_type=doc_type, description=desc,
        )

        LeadActivityLog.objects.create(
            lead=lead,
            log_type=LeadActivityLog.LogType.DOCUMENT_ADDED,
            content=f'Document ajouté : « {doc.title} » ({doc.get_doc_type_display()}).',
            performed_by=request.user,
        )
        messages.success(request, 'Document enregistré.')
        return redirect('crm:lead_detail', pk=lead_pk)


class LeadDocumentDeleteView(LoginRequiredMixin, View):
    """Supprime un document (directeur ou uploadeur)."""

    def post(self, request, pk):
        doc = get_object_or_404(LeadDocument, pk=pk)
        if not is_director(request.user) and doc.uploaded_by != request.user:
            raise PermissionDenied
        lead_pk = doc.lead_id
        doc.file.delete(save=False)
        doc.delete()
        messages.success(request, 'Document supprimé.')
        return redirect('crm:lead_detail', pk=lead_pk)


# ═════════════════════════════════════════════════════════════════════════════
# Journal d'activité (note manuelle)
# ═════════════════════════════════════════════════════════════════════════════

class LeadLogCreateView(LoginRequiredMixin, View):
    """Ajoute une note ou un log manuel sur un lead (HTMX ou POST classique)."""

    def post(self, request, lead_pk):
        lead     = get_object_or_404(Lead, pk=lead_pk)
        _check_lead_access(request.user, lead)
        content  = request.POST.get('content', '').strip()
        log_type = request.POST.get('log_type', LeadActivityLog.LogType.NOTE)

        if content:
            log = LeadActivityLog.objects.create(
                lead=lead,
                log_type=log_type,
                content=content,
                performed_by=request.user,
            )
            if request.headers.get('HX-Request'):
                return render(request, 'crm/partials/log_entry.html', {'log': log})

        return redirect('crm:lead_detail', pk=lead_pk)


# ═════════════════════════════════════════════════════════════════════════════
# Helpers internes
# ═════════════════════════════════════════════════════════════════════════════

def _check_lead_access(user, lead):
    """Lève PermissionDenied si l'utilisateur n'a pas accès à ce lead."""
    if not can_access_crm(user):
        raise PermissionDenied
    if not is_director(user) and lead.assigned_to != user:
        raise PermissionDenied


def _save_lead_document(lead, uploaded_by, file, title, doc_type, description='', appointment=None):
    """Crée et sauvegarde un LeadDocument."""
    return LeadDocument.objects.create(
        lead=lead,
        appointment=appointment,
        doc_type=doc_type,
        title=title,
        description=description,
        file=file,
        uploaded_by=uploaded_by,
    )


def _notify_directors(request, title, message):
    """Crée une notification in-app pour tous les directeurs/managers actifs."""
    try:
        from apps.notifications.models import Notification
        directors = User.objects.filter(role__in=['DIRECTEUR', 'MANAGER'], is_active=True)
        for director in directors:
            Notification.objects.create(
                recipient=director,
                sender=request.user,
                notification_type=Notification.Type.APPROVAL_REQUESTED,
                title=title,
                message=message,
            )
    except Exception:
        pass  # Ne jamais bloquer l'action métier pour une notif
