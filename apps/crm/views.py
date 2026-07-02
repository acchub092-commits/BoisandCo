import csv
import io
import json
import os
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Sum, Q
from django.http import JsonResponse, HttpResponse
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
        user = self.request.user

        # Filtrage RBAC : commerciaux ne voient que leurs leads
        base_qs = Lead.objects.select_related('assigned_to')
        if not is_director(user) and not user.is_superuser:
            base_qs = base_qs.filter(
                Q(assigned_to=user) | Q(created_by=user)
            )

        leads = base_qs.filter(status__in=Lead.PIPELINE_STAGES)

        columns = []
        for status in Lead.PIPELINE_STAGES:
            meta  = COLUMN_META[status]
            items = [l for l in leads if l.status == status]
            total_budget = sum(l.budget_mad for l in items if l.budget_mad)
            columns.append({
                'status':       status,
                'label':        meta['label'],
                'color':        meta['color'],
                'bg':           meta['bg'],
                'leads':        items,
                'count':        len(items),
                'total_budget': total_budget,
            })

        won_qs  = base_qs.filter(status=Lead.Status.GAGNEE)
        lost_qs = base_qs.filter(status=Lead.Status.PERDUE)

        ctx['columns']        = columns
        ctx['statuses']       = Lead.Status.choices
        ctx['won_leads']      = won_qs.order_by('-updated_at')[:10]
        ctx['lost_leads']     = lost_qs.order_by('-updated_at')[:10]
        ctx['won_count']      = won_qs.count()
        ctx['lost_count']     = lost_qs.count()
        ctx['total_pipeline'] = sum(l.budget_mad for l in leads if l.budget_mad)
        ctx['is_director']    = is_director(user) or user.is_superuser
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
        from django.db.models import Count as DCount
        ctx   = super().get_context_data(**kwargs)
        user  = self.request.user
        today = date.today()

        # ── Queryset de base (RBAC) ──────────────────────────────────────────
        qs_base = Lead.objects.all() if is_director(user) else Lead.objects.filter(
            Q(assigned_to=user) | Q(created_by=user)
        )

        # ── Helpers mois ─────────────────────────────────────────────────────
        def _month_start(months_back):
            m, y = today.month - months_back, today.year
            while m <= 0:
                m += 12; y -= 1
            return date(y, m, 1)

        def _next_month(d):
            return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)

        this_month  = _month_start(0)
        last_month  = _month_start(1)
        next_month  = _next_month(this_month)

        # ── KPIs pipeline ────────────────────────────────────────────────────
        actifs         = qs_base.filter(status__in=Lead.PIPELINE_STAGES)
        actifs_n       = actifs.count()
        pipeline_value = float(actifs.aggregate(t=Sum('budget_mad'))['t'] or 0)

        actifs_last    = qs_base.filter(
            status__in=Lead.PIPELINE_STAGES,
            created_at__lt=this_month,
        ).count()

        # Win rate
        closed     = qs_base.filter(status__in=[Lead.Status.GAGNEE, Lead.Status.PERDUE]).count()
        won_total  = qs_base.filter(status=Lead.Status.GAGNEE).count()
        win_rate   = round(won_total / closed * 100) if closed else 0

        gagnes_mois = qs_base.filter(
            status=Lead.Status.GAGNEE,
            updated_at__gte=this_month, updated_at__lt=next_month,
        ).count()
        gagnes_last = qs_base.filter(
            status=Lead.Status.GAGNEE,
            updated_at__gte=last_month, updated_at__lt=this_month,
        ).count()

        # ── Leads à valider (directeur) ──────────────────────────────────────
        pending = Lead.objects.filter(
            workflow_status=Lead.WorkflowStatus.PENDING_VALIDATION
        ) if is_director(user) else Lead.objects.none()

        # ── Prochains RDV (7 jours) ──────────────────────────────────────────
        rdv_qs = Appointment.objects.select_related('lead', 'created_by').filter(
            scheduled_at__gte=timezone.now(),
            scheduled_at__date__lte=today + timedelta(days=7),
            status=Appointment.Status.PLANIFIE,
        )
        if not is_director(user):
            rdv_qs = rdv_qs.filter(Q(lead__assigned_to=user) | Q(attendees=user)).distinct()

        # ── Journal récent ───────────────────────────────────────────────────
        logs_qs = LeadActivityLog.objects.select_related('lead', 'performed_by')
        if not is_director(user):
            logs_qs = logs_qs.filter(lead__assigned_to=user)
        recent_logs = logs_qs.order_by('-created_at')[:12]

        # ── Répartition par statut ───────────────────────────────────────────
        STAGES_ORDER = [
            Lead.Status.VISITE, Lead.Status.OPPORTUNITE, Lead.Status.QUALIFICATION,
            Lead.Status.CHIFFRAGE, Lead.Status.OFFRE, Lead.Status.GAGNEE, Lead.Status.PERDUE,
        ]
        STAGE_LABELS = {
            'VISITE': 'Visites', 'OPPORTUNITE': 'Opportunités', 'QUALIFICATION': 'Qualification',
            'CHIFFRAGE': 'Chiffrage', 'OFFRE': 'Offre envoyée', 'GAGNEE': 'Gagnés', 'PERDUE': 'Perdus',
        }
        STAGE_COLORS = {
            'VISITE': '#64748b', 'OPPORTUNITE': '#2563eb', 'QUALIFICATION': '#d97706',
            'CHIFFRAGE': '#7c3aed', 'OFFRE': '#0891b2', 'GAGNEE': '#22804c', 'PERDUE': '#ef4444',
        }
        status_counts = {s: qs_base.filter(status=s).count() for s in STAGES_ORDER}

        # ── Données Chart.js ─────────────────────────────────────────────────
        # 1. Funnel (entonnoir) — stages actifs uniquement
        funnel_labels  = [STAGE_LABELS[s] for s in Lead.PIPELINE_STAGES]
        funnel_counts  = [status_counts[s] for s in Lead.PIPELINE_STAGES]
        funnel_budgets = [
            float(qs_base.filter(status=s).aggregate(t=Sum('budget_mad'))['t'] or 0)
            for s in Lead.PIPELINE_STAGES
        ]
        funnel_colors  = [STAGE_COLORS[s] for s in Lead.PIPELINE_STAGES]

        # 2. Tendance mensuelle (6 derniers mois)
        trend_labels, trend_created, trend_won = [], [], []
        MONTHS_FR = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc']
        for i in range(5, -1, -1):
            ms = _month_start(i)
            me = _next_month(ms)
            trend_labels.append(MONTHS_FR[ms.month - 1])
            trend_created.append(qs_base.filter(created_at__gte=ms, created_at__lt=me).count())
            trend_won.append(qs_base.filter(
                status=Lead.Status.GAGNEE, updated_at__gte=ms, updated_at__lt=me
            ).count())

        # 3. Win/Loss donut
        won_n  = status_counts[Lead.Status.GAGNEE]
        lost_n = status_counts[Lead.Status.PERDUE]

        # 4. Budget par stage (barres)
        budget_labels = [STAGE_LABELS[s] for s in Lead.PIPELINE_STAGES]
        budget_values = funnel_budgets

        # ── Performance par commercial (directeurs) ──────────────────────────
        perf_commerciaux = []
        if is_director(user):
            from apps.users.models import User as AppUser
            perf_commerciaux = list(
                AppUser.objects.filter(role='COMMERCIAL', is_active_employee=True).annotate(
                    n_actifs=DCount('assigned_leads', filter=Q(assigned_leads__status__in=Lead.PIPELINE_STAGES)),
                    n_gagnes=DCount('assigned_leads', filter=Q(assigned_leads__status=Lead.Status.GAGNEE)),
                    pipeline=Sum('assigned_leads__budget_mad', filter=Q(assigned_leads__status__in=Lead.PIPELINE_STAGES)),
                ).order_by('-n_actifs')
            )

        # ── Top leads par budget ─────────────────────────────────────────────
        top_leads = list(
            actifs.filter(budget_mad__isnull=False).select_related('assigned_to')
            .order_by('-budget_mad')[:6]
        )

        # ── Format montant ───────────────────────────────────────────────────
        def _fmt(v):
            v = float(v or 0)
            if v >= 1_000_000: return f'{v/1_000_000:.1f} M'
            if v >= 1_000:     return f'{v/1_000:.0f} K'
            return f'{v:.0f}'

        ctx.update({
            'kpis': {
                'actifs':          actifs_n,
                'actifs_trend':    actifs_n - actifs_last,
                'pipeline_value':  pipeline_value,
                'pipeline_fmt':    _fmt(pipeline_value),
                'win_rate':        win_rate,
                'rdv_semaine':     rdv_qs.count(),
                'a_valider':       pending.count(),
                'gagnes_mois':     gagnes_mois,
                'gagnes_trend':    gagnes_mois - gagnes_last,
            },
            'pending_leads':     pending.select_related('assigned_to', 'created_by').order_by('-updated_at')[:8],
            'prochains_rdv':     rdv_qs.order_by('scheduled_at')[:6],
            'recent_logs':       recent_logs,
            'status_counts':     status_counts,
            'is_director':       is_director(user) or user.is_superuser,
            'perf_commerciaux':  perf_commerciaux,
            'top_leads':         top_leads,
            # Charts JSON
            'chart_funnel': json.dumps({
                'labels': funnel_labels, 'counts': funnel_counts,
                'budgets': funnel_budgets, 'colors': funnel_colors,
            }),
            'chart_trend': json.dumps({
                'labels': trend_labels, 'created': trend_created, 'won': trend_won,
            }),
            'chart_winloss': json.dumps({
                'won': won_n, 'lost': lost_n,
                'total': won_n + lost_n,
                'win_rate': win_rate,
            }),
            'chart_budget': json.dumps({
                'labels': budget_labels, 'values': budget_values, 'colors': funnel_colors,
            }),
            'fmt': _fmt,
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


# ─────────────────────────────────────────────────────────────────────────────
# Import en masse — Administrateur uniquement
# ─────────────────────────────────────────────────────────────────────────────

_STATUT_MAP = {
    'prospection': Lead.Status.VISITE,
    'visite':      Lead.Status.VISITE,
    'opportunite': Lead.Status.OPPORTUNITE,
    'qualification': Lead.Status.QUALIFICATION,
    'en cours':    Lead.Status.CHIFFRAGE,
    'chiffrage':   Lead.Status.CHIFFRAGE,
    'negociation': Lead.Status.OFFRE,
    'négociation': Lead.Status.OFFRE,
    'offre':       Lead.Status.OFFRE,
    'gagné':       Lead.Status.GAGNEE,
    'gagne':       Lead.Status.GAGNEE,
    'perdu':       Lead.Status.PERDUE,
    'perdue':      Lead.Status.PERDUE,
}
_POTENTIEL_MAP = {
    'faible': Lead.Potential.FAIBLE, 'low':    Lead.Potential.FAIBLE,
    'moyen':  Lead.Potential.MOYEN,  'medium': Lead.Potential.MOYEN,
    'important': Lead.Potential.IMPORTANT, 'high': Lead.Potential.IMPORTANT,
}
_PROBA_MAP = {
    'low': Lead.Probability.LOW, 'med': Lead.Probability.MED, 'high': Lead.Probability.HIGH,
}


def _parse_date_import(val):
    if not val:
        return None
    from datetime import datetime
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(val.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_budget(val):
    if not val:
        return None
    cleaned = val.replace(' ', '').replace('\xa0', '').replace(',', '.').replace('%', '')
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _map_proba_pct(pct_str):
    try:
        val = int(pct_str.replace('%', '').strip())
    except Exception:
        return Lead.Probability.LOW
    if val <= 10:
        return Lead.Probability.LOW
    elif val <= 60:
        return Lead.Probability.MED
    return Lead.Probability.HIGH


class ImportLeadsView(LoginRequiredMixin, View):
    """Import en masse de leads depuis un CSV — réservé aux administrateurs."""
    template_name = 'crm/import_leads.html'

    def _check_admin(self, request):
        allowed = {User.Role.ADMIN, User.Role.DIRECTEUR, User.Role.MANAGER}
        if not (request.user.is_superuser or getattr(request.user, 'role', None) in allowed):
            raise PermissionDenied

    def get(self, request):
        self._check_admin(request)

        # Téléchargement du canevas vierge
        if request.GET.get('action') == 'template':
            return self._download_template()

        return render(request, self.template_name, {
            'user_list': User.objects.filter(role=User.Role.COMMERCIAL).order_by('first_name'),
        })

    def post(self, request):
        self._check_admin(request)

        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, 'Veuillez sélectionner un fichier CSV.')
            return redirect('crm:import_leads')

        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Le fichier doit être au format .csv')
            return redirect('crm:import_leads')

        # Détecter l'encodage
        raw = csv_file.read()
        for enc in ('utf-8-sig', 'utf-8', 'latin-1', 'cp1252'):
            try:
                content = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue

        # Construire le cache utilisateurs (prénom → user)
        user_cache = {u.first_name.strip().lower(): u for u in User.objects.all() if u.first_name.strip()}

        reader = csv.DictReader(io.StringIO(content), delimiter=';')
        headers = [h.strip().lower() for h in (reader.fieldnames or [])]

        # Détecter le format : DC (français) ou import interne
        is_dc_format = 'commercial' in headers and 'potentiel (mad)' in headers

        created = skipped = errors = unknown = 0
        error_details = []

        for i, row in enumerate(reader, start=2):
            row = {k.strip().lower(): (v or '').strip() for k, v in row.items() if k}

            if is_dc_format:
                commercial_name = row.get('commercial', '')
                nom_projet      = row.get('projet', '') or row.get('nom_projet', '')
                entreprise      = row.get('client', '') or row.get('entreprise', '')
                segment         = row.get('segment', '') or row.get('type_projet', '')
                ville           = row.get('ville', '').replace('#valeur!', '').strip()
                region          = row.get('région', '') or row.get('region', '')
                pays            = row.get('pays', '')
                budget_raw      = row.get('potentiel (mad)', '') or row.get('budget_mad', '')
                proba_raw       = row.get('probabilité', '') or row.get('probabilite', '')
                commentaire     = row.get('commentaire terrain', '') or row.get('commentaire', '')
                statut_raw      = row.get('statut', '')
                closing_raw     = row.get('date closing est.', '') or row.get('date_closing_est', '')
                priority_raw    = row.get('priorité (auto)', '') or row.get('potentiel', '')
                potentiel_val   = _POTENTIEL_MAP.get(priority_raw.lower(), Lead.Potential.MOYEN)
                proba_val       = _map_proba_pct(proba_raw)
            else:
                commercial_name = row.get('commercial', '')
                nom_projet      = row.get('nom_projet', '')
                entreprise      = row.get('entreprise', '')
                segment         = row.get('type_projet', '')
                ville           = row.get('ville', '')
                region          = row.get('region', '')
                pays            = row.get('pays', '')
                budget_raw      = row.get('budget_mad', '')
                proba_raw       = row.get('probabilite', '')
                commentaire     = row.get('commentaire', '')
                statut_raw      = row.get('statut', '')
                closing_raw     = row.get('date_closing_est', '')
                potentiel_val   = _POTENTIEL_MAP.get(row.get('potentiel', '').lower(), Lead.Potential.MOYEN)
                proba_val       = _PROBA_MAP.get(proba_raw.lower(), Lead.Probability.LOW)

            if not commercial_name or not nom_projet:
                continue

            user = user_cache.get(commercial_name.lower())
            if not user:
                unknown += 1
                error_details.append(f'Ligne {i} — Commercial inconnu : "{commercial_name}" ({nom_projet})')
                continue

            loc = ville or region
            status = _STATUT_MAP.get(statut_raw.lower(), Lead.Status.VISITE)

            try:
                Lead.objects.create(
                    project_name      = nom_projet,
                    company           = entreprise,
                    contact_name      = entreprise or nom_projet,
                    location          = loc,
                    project_type      = segment,
                    budget_mad        = _parse_budget(budget_raw),
                    probability       = proba_val,
                    potential         = potentiel_val,
                    status            = status,
                    strategic_comment = commentaire,
                    end_date_est      = _parse_date_import(closing_raw),
                    assigned_to       = user,
                    created_by        = user,
                    workflow_status   = Lead.WorkflowStatus.VALIDATED,
                    source            = Lead.Source.DIRECTOR_ASSIGNED,
                )
                created += 1
            except Exception as e:
                errors += 1
                error_details.append(f'Ligne {i} — Erreur : {nom_projet} ({e})')

        # Rapport
        if created:
            messages.success(request, f'{created} lead(s) importé(s) avec succès.')
        if unknown:
            messages.warning(request, f'{unknown} ligne(s) ignorée(s) : commercial introuvable dans le système.')
        if errors:
            messages.error(request, f'{errors} erreur(s) lors de l\'import.')

        request.session['import_errors'] = error_details[:50]
        return redirect('crm:import_leads')

    def _download_template(self):
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="canevas_import_leads.csv"'
        writer = csv.writer(response, delimiter=';')

        # En-tête avec exemples de valeurs
        writer.writerow([
            'Commercial', 'Client', 'Projet', 'Segment',
            'Ville', 'Région', 'Pays',
            'Potentiel (MAD)', 'Probabilité',
            'Commentaire terrain', 'Statut',
            'Date Closing Est.',
        ])
        # Ligne d'aide
        writer.writerow([
            'Prénom exact du commercial', 'Nom de la société', 'Nom du projet',
            'Residential / Commercial / Hospitality / Institutional / Industrial & Logistics',
            'Casablanca', 'Casablanca-Settat', 'Maroc',
            '5000000', '50%',
            'Commentaire libre', 'Prospection / En cours / Négociation / Gagné / Perdu',
            'JJ/MM/AAAA',
        ])
        # Exemple concret
        writer.writerow([
            'Bruno', 'CGI', 'RESIDENCE LES ORANGERS', 'Residential',
            'Casablanca', 'Casablanca-Settat', 'Maroc',
            '12000000', '50%',
            'Devis remis au client, RDV prévu fin juin', 'En cours',
            '30/09/2026',
        ])
        writer.writerow([
            'Amine', 'ADDOHA', 'TOUR PRESTIGE', 'Hospitality',
            'Marrakech', 'Marrakech-Safi', 'Maroc',
            '8500000', '80%',
            'Appel d\'offre lancé, consultation en cours', 'Négociation',
            '15/08/2026',
        ])
        return response


# ── COMEX Dashboard ──────────────────────────────────────────────────────────

class COMEXDashboardView(LoginRequiredMixin, TemplateView):
    """Tableau de bord COMEX — synthèse pipeline commercial pour la Direction."""
    template_name = 'crm/comex.html'

    MONTHLY_TARGET = 20_000_000  # MAD — objectif mensuel de référence

    def dispatch(self, request, *args, **kwargs):
        allowed = {User.Role.ADMIN, User.Role.DIRECTEUR, User.Role.MANAGER}
        if not (request.user.is_superuser or getattr(request.user, 'role', None) in allowed):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from collections import defaultdict
        ctx = super().get_context_data(**kwargs)
        today = date.today()

        # ── Source : OpportunitePipeline (données saisies dans Saisie Pipeline) ──
        all_opps = list(OpportunitePipeline.objects.select_related('commercial').all())
        active   = [o for o in all_opps if o.statut != OpportunitePipeline.Statut.PERDU]
        pipeline = [o for o in active   if o.statut != OpportunitePipeline.Statut.GAGNE]

        # ── KPIs ──────────────────────────────────────────────────────────────
        total_pot  = sum(float(o.potentiel_mad or 0) for o in pipeline)
        total_pond = sum(float(o.pondere or 0) for o in active)
        nb_actifs  = len(active)
        nb_high    = sum(1 for o in active if o.priorite == 'HIGH')

        # ── Alertes brutes (une entrée par type d'alerte par opportunité) ────────
        alerts_raw = []
        for o in active:
            for alert_type in (o.alerte.split(' · ') if o.alerte else []):
                alerts_raw.append({'opp': o, 'type': alert_type})

        # ── Par commercial ────────────────────────────────────────────────────
        com = defaultdict(lambda: {'count': 0, 'pot': 0.0, 'pond': 0.0, 'high': 0, 'user': None})
        for o in active:
            k = o.commercial.get_full_name() if o.commercial else 'Non assigné'
            com[k]['count'] += 1
            com[k]['pot']   += float(o.potentiel_mad or 0)
            com[k]['pond']  += float(o.pondere or 0)
            if o.priorite == 'HIGH':
                com[k]['high'] += 1
            com[k]['user'] = o.commercial
        tot_com = sum(d['pot'] for d in com.values()) or 1
        commerciaux = sorted([
            {'name': k, 'user': d['user'], 'count': d['count'],
             'pot': d['pot'], 'pct': round(d['pot'] / tot_com * 100, 1),
             'pond': d['pond'], 'high': d['high']}
            for k, d in com.items()
        ], key=lambda x: -x['pot'])

        # ── Par statut ────────────────────────────────────────────────────────
        stat_labels = [
            ('Prospection', [OpportunitePipeline.Statut.PROSPECTION]),
            ('En cours',    [OpportunitePipeline.Statut.EN_COURS]),
            ('Négociation', [OpportunitePipeline.Statut.NEGOCIATION]),
            ('Gagné',       [OpportunitePipeline.Statut.GAGNE]),
            ('Perdu',       [OpportunitePipeline.Statut.PERDU]),
        ]
        tot_all = sum(float(o.potentiel_mad or 0) for o in all_opps) or 1
        statuts = []
        for label, codes in stat_labels:
            grp  = [o for o in all_opps if o.statut in codes]
            pot  = sum(float(o.potentiel_mad or 0) for o in grp)
            pond = sum(float(o.pondere or 0) for o in grp)
            statuts.append({'label': label, 'count': len(grp),
                            'pot': pot, 'pct': round(pot / tot_all * 100, 1), 'pond': pond})

        # ── Par segment ───────────────────────────────────────────────────────
        seg = defaultdict(lambda: {'count': 0, 'pot': 0.0, 'pond': 0.0, 'high': 0})
        for o in pipeline:
            k = o.segment or 'Non défini'
            seg[k]['count'] += 1
            seg[k]['pot']   += float(o.potentiel_mad or 0)
            seg[k]['pond']  += float(o.pondere or 0)
            if o.priorite == 'HIGH':
                seg[k]['high'] += 1
        tot_seg = sum(d['pot'] for d in seg.values()) or 1
        segments = sorted([
            {'label': k, 'count': d['count'], 'pot': d['pot'],
             'pct': round(d['pot'] / tot_seg * 100, 1), 'pond': d['pond'], 'high': d['high']}
            for k, d in seg.items()
        ], key=lambda x: -x['pot'])

        # ── Top villes ────────────────────────────────────────────────────────
        geo = defaultdict(lambda: {'count': 0, 'pot': 0.0, 'pond': 0.0})
        for o in pipeline:
            city = (o.ville or '').strip().title() or 'Non renseigné'
            geo[city]['count'] += 1
            geo[city]['pot']   += float(o.potentiel_mad or 0)
            geo[city]['pond']  += float(o.pondere or 0)
        tot_geo = sum(d['pot'] for d in geo.values()) or 1
        top_villes = sorted(
            [{'ville': k, 'count': d['count'], 'pot': d['pot'],
              'pct': round(d['pot'] / tot_geo * 100, 1), 'pond': d['pond']}
             for k, d in geo.items() if k not in ('Non Renseigné', 'Non renseigné') and d['pot'] > 0],
            key=lambda x: -x['pot']
        )[:12]

        # ── Top 10 projets prioritaires ───────────────────────────────────────
        top_raw = sorted(
            [o for o in pipeline if o.potentiel_mad],
            key=lambda o: -(float(o.pondere or 0))
        )[:10]
        top_projets = [
            {'opp': o, 'pond': float(o.pondere or 0),
             'alerts': o.alerte.split(' · ') if o.alerte else []}
            for o in top_raw
        ]

        # ── Dépendance commerciale ────────────────────────────────────────────
        dependance = sorted([
            {'name': c['name'], 'user': c['user'], 'pct': c['pct'], 'pot': c['pot'],
             'signal': 'danger' if c['pct'] > 50 else ('warning' if c['pct'] > 30 else 'ok')}
            for c in commerciaux
        ], key=lambda x: -x['pct'])

        # ── Pilotage temporel ─────────────────────────────────────────────────
        j30 = today + timedelta(days=30)
        j90 = today + timedelta(days=90)
        bmap = {'0-30 j': [], '30-90 j': [], '+90 j': [], 'Dépassé': [], 'Non renseigné': []}
        for o in pipeline:
            if not o.date_closing_est:
                bmap['Non renseigné'].append(o)
            elif o.date_closing_est < today:
                bmap['Dépassé'].append(o)
            elif o.date_closing_est <= j30:
                bmap['0-30 j'].append(o)
            elif o.date_closing_est <= j90:
                bmap['30-90 j'].append(o)
            else:
                bmap['+90 j'].append(o)
        tot_tp    = sum(float(o.potentiel_mad or 0) for o in pipeline) or 1
        tot_tpond = sum(float(o.pondere or 0)       for o in pipeline) or 1
        temporal  = []
        for label in ['0-30 j', '30-90 j', '+90 j', 'Dépassé', 'Non renseigné']:
            ls   = bmap[label]
            pot  = sum(float(o.potentiel_mad or 0) for o in ls)
            pond = sum(float(o.pondere or 0) for o in ls)
            temporal.append({
                'label': label, 'count': len(ls), 'pot': pot,
                'pct_pot':  round(pot  / tot_tp    * 100, 1),
                'pond': pond,
                'pct_pond': round(pond / tot_tpond * 100, 1),
            })

        # ── Synthèse alertes ──────────────────────────────────────────────────
        sans_action      = sum(1 for o in active if not o.prochaine_action)
        high_sans_action = sum(1 for o in active if o.priorite == 'HIGH' and not o.prochaine_action)
        incoherent       = sum(1 for o in active
                               if o.probabilite and Decimal(o.probabilite) >= Decimal('0.80')
                               and o.statut == OpportunitePipeline.Statut.PROSPECTION)
        montant_vide     = sum(1 for o in active if not o.potentiel_mad)
        prob_manquante   = sum(1 for o in active if not o.probabilite)

        synthese = [
            {'type': 'SANS ACTION PLANIFIÉE',    'count': sans_action,      'niveau': 'Immédiat'},
            {'type': '80%+ SANS ACTION',          'count': high_sans_action, 'niveau': 'Critique'},
            {'type': 'STATUT/PROB INCOHÉRENT',    'count': incoherent,       'niveau': 'Haute'},
            {'type': 'MONTANT VIDE',              'count': montant_vide,     'niveau': 'Immédiat'},
            {'type': 'PROB MANQUANTE',            'count': prob_manquante,   'niveau': 'Haute'},
        ]

        # ── Totaux lignes de pied de tableau ─────────────────────────────────
        statut_total = {
            'count': len(all_opps),
            'pot':   sum(float(o.potentiel_mad or 0) for o in all_opps),
            'pond':  sum(float(o.pondere or 0)       for o in all_opps),
        }
        segment_total = {
            'count': sum(s['count'] for s in segments),
            'pot':   sum(s['pot']   for s in segments),
            'pond':  sum(s['pond']  for s in segments),
            'high':  sum(s['high']  for s in segments),
        }
        villes_total = {
            'count': sum(v['count'] for v in top_villes),
            'pot':   sum(v['pot']   for v in top_villes),
            'pond':  sum(v['pond']  for v in top_villes),
            'pct':   round(sum(v['pot'] for v in top_villes) / tot_geo * 100, 1),
        }

        ctx.update({
            'today': today,
            'total_pot': total_pot,
            'total_pond': total_pond,
            'nb_actifs': nb_actifs,
            'nb_alertes': len(alerts_raw),
            'nb_high': nb_high,
            'commerciaux': commerciaux,
            'statuts': statuts,
            'segments': segments,
            'top_villes': top_villes,
            'top_projets': top_projets,
            'dependance': dependance,
            'alerts_list': alerts_raw[:50],
            'temporal': temporal,
            'couverture_mois': round(total_pond / self.MONTHLY_TARGET, 1) if self.MONTHLY_TARGET else 0,
            'pipeline_30j': sum(float(o.pondere or 0) for o in bmap['0-30 j']),
            'monthly_target': self.MONTHLY_TARGET,
            'synthese': synthese,
            'statut_total':  statut_total,
            'segment_total': segment_total,
            'villes_total':  villes_total,
        })
        return ctx


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline Commercial — Saisie & Analyse
# ─────────────────────────────────────────────────────────────────────────────

from .models import OpportunitePipeline  # noqa: E402
from .forms import OpportunitePipelineForm  # noqa: E402
from .permissions import CRMAccessMixin  # noqa: E402


class ImportPipelineView(CRMAccessMixin, View):
    """Import CSV des opportunités pipeline — réservé DC/DG."""
    template_name = 'crm/import_pipeline.html'

    PROBA_MAP = {
        '0%': '', '0 %': '',
        '10%': '0.10', '10 %': '0.10',
        '50%': '0.50', '50 %': '0.50',
        '80%': '0.80', '80 %': '0.80',
        '100%': '1.00', '100 %': '1.00',
    }
    STATUTS_VALIDES  = {'Prospection', 'En cours', 'Négociation', 'Gagné', 'Perdu'}
    SEGMENTS_VALIDES = {
        'Residential', 'Commercial', 'Hospitality',
        'Institutional', 'Industrial & Logistics',
    }

    def dispatch(self, request, *args, **kwargs):
        if not (is_director(request.user) or request.user.is_superuser):
            messages.error(request, "Import réservé au Directeur Commercial / DG.")
            return redirect('crm:analyse_pipeline')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        fichier = request.FILES.get('fichier')
        if not fichier:
            messages.error(request, "Aucun fichier sélectionné.")
            return render(request, self.template_name)

        # Lecture (UTF-8-BOM puis Latin-1 en fallback)
        try:
            content = fichier.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            fichier.seek(0)
            content = fichier.read().decode('cp1252')

        # Carte prénom → User
        commercial_map = {
            u.first_name.strip().lower(): u
            for u in User.objects.filter(
                role__in=('COMMERCIAL', 'MANAGER'), is_active_employee=True,
            )
        }

        reader   = csv.reader(io.StringIO(content), delimiter=';')
        imported = []
        skipped  = []

        for i, row in enumerate(reader):
            if i == 0:
                continue                          # en-tête
            row = (row + [''] * 25)[:25]          # normaliser la longueur

            comm_name = row[0].strip()
            client    = row[1].strip()
            projet    = row[2].strip()

            if not comm_name and not client:
                continue                          # ligne vide

            commercial = commercial_map.get(comm_name.lower())
            if not commercial:
                skipped.append({'ligne': i + 1, 'client': client or '—',
                                'projet': projet or '—',
                                'raison': f'Commercial « {comm_name} » introuvable'})
                continue

            if not client or not projet:
                skipped.append({'ligne': i + 1, 'client': client or '—',
                                'projet': projet or '—',
                                'raison': 'Client ou Projet vide'})
                continue

            seg_raw  = row[3].strip()
            segment  = seg_raw if seg_raw in self.SEGMENTS_VALIDES else 'Residential'

            ville = row[4].strip()
            if ville.startswith('#'):
                ville = ''

            region = row[5].strip()
            pays   = row[6].strip() or 'Maroc'

            potentiel    = self._parse_mad(row[7])
            probabilite  = self.PROBA_MAP.get(row[8].strip(), '')
            commentaire  = row[10].strip()

            stat_raw = row[11].strip()
            statut   = stat_raw if stat_raw in self.STATUTS_VALIDES else 'Prospection'

            prochaine_action = row[12].strip()
            date_action      = self._parse_date(row[13])
            date_closing     = self._parse_date(row[16])

            risque_raw = row[18].strip()
            risque     = risque_raw if risque_raw in ('High', 'Medium', 'Low') else ''

            OpportunitePipeline.objects.create(
                commercial=commercial,
                client=client,
                projet=projet,
                segment=segment,
                ville=ville,
                region=region,
                pays=pays,
                potentiel_mad=potentiel,
                probabilite=probabilite,
                commentaire_terrain=commentaire,
                statut=statut,
                prochaine_action=prochaine_action,
                date_action=date_action,
                date_closing_est=date_closing,
                risque=risque,
            )
            imported.append({
                'client':     client,
                'projet':     projet,
                'commercial': commercial.get_full_name(),
                'statut':     statut,
            })

        return render(request, self.template_name, {
            'imported': imported,
            'skipped':  skipped,
            'done':     True,
        })

    @staticmethod
    def _parse_date(s):
        s = s.strip()
        if not s:
            return None
        from datetime import datetime as _dt
        for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
            try:
                return _dt.strptime(s, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_mad(s):
        cleaned = s.strip().replace('\xa0', '').replace(' ', '').replace(',', '.')
        if not cleaned:
            return None
        try:
            return Decimal(cleaned)
        except Exception:
            return None


class SaisiePipelineView(CRMAccessMixin, View):
    template_name = 'crm/saisie_pipeline.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not is_director(request.user):
            messages.error(request, "La création d'opportunités est réservée au Directeur Commercial.")
            return redirect('crm:analyse_pipeline')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        form = OpportunitePipelineForm(user=request.user)
        return render(request, self.template_name, {'form': form, 'is_edit': False})

    def post(self, request):
        form = OpportunitePipelineForm(request.POST, user=request.user)
        if form.is_valid():
            opp = form.save(commit=False)
            opp.save()
            messages.success(request, f'Opportunité « {opp.client} — {opp.projet} » enregistrée.')
            return redirect('crm:saisie_pipeline')
        return render(request, self.template_name, {'form': form, 'is_edit': False})


class SaisiePipelineEditView(CRMAccessMixin, View):
    template_name = 'crm/saisie_pipeline.html'

    def _get_opp(self, request, pk):
        if not is_director(request.user):
            messages.error(request, "La modification est réservée au Directeur Commercial.")
            return None
        return get_object_or_404(OpportunitePipeline, pk=pk)

    def get(self, request, pk):
        opp = self._get_opp(request, pk)
        if opp is None:
            return redirect('crm:analyse_pipeline')
        form = OpportunitePipelineForm(instance=opp, user=request.user)
        return render(request, self.template_name, {'form': form, 'opp': opp, 'is_edit': True})

    def post(self, request, pk):
        opp = self._get_opp(request, pk)
        if opp is None:
            return redirect('crm:analyse_pipeline')
        form = OpportunitePipelineForm(request.POST, instance=opp, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Opportunité mise à jour.')
            return redirect('crm:analyse_pipeline')
        return render(request, self.template_name, {'form': form, 'opp': opp, 'is_edit': True})


class OpportunitePipelineDetailView(CRMAccessMixin, View):
    template_name = 'crm/pipeline_detail.html'

    def get(self, request, pk):
        opp = get_object_or_404(OpportunitePipeline, pk=pk)
        if is_commercial(request.user) and opp.commercial != request.user:
            messages.error(request, "Vous ne pouvez consulter que vos propres opportunités.")
            return redirect('crm:analyse_pipeline')
        return render(request, self.template_name, {'opp': opp})


class SaisiePipelineDeleteView(CRMAccessMixin, View):
    def post(self, request, pk):
        if not is_director(request.user):
            messages.error(request, 'Suppression réservée au Directeur Commercial / DG.')
            return redirect('crm:analyse_pipeline')
        opp   = get_object_or_404(OpportunitePipeline, pk=pk)
        label = str(opp)
        opp.delete()
        messages.success(request, f'Opportunité « {label} » supprimée.')
        return redirect('crm:analyse_pipeline')


class AnalysePipelineView(CRMAccessMixin, View):
    template_name = 'crm/analyse_pipeline.html'

    def get(self, request):
        qs = OpportunitePipeline.objects.select_related('commercial').all()
        if is_commercial(request.user):
            qs = qs.filter(commercial=request.user)

        f_commercial = request.GET.get('commercial', '')
        f_statut     = request.GET.get('statut', '')
        f_segment    = request.GET.get('segment', '')
        if f_commercial and is_director(request.user):
            qs = qs.filter(commercial_id=f_commercial)
        if f_statut:
            qs = qs.filter(statut=f_statut)
        if f_segment:
            qs = qs.filter(segment=f_segment)

        opportunites = list(qs)

        total_mad  = sum(o.potentiel_mad for o in opportunites if o.potentiel_mad) or 0
        total_pond = sum(o.pondere for o in opportunites if o.pondere) or 0
        nb_actifs  = sum(1 for o in opportunites if o.statut not in ('Gagné', 'Perdu'))
        nb_alertes = sum(1 for o in opportunites if o.alerte)

        commerciaux = User.objects.filter(role__in=('COMMERCIAL', 'MANAGER'), is_active_employee=True).order_by('last_name')

        # Agrégats pour les graphiques
        from collections import defaultdict
        _by_statut  = defaultdict(lambda: {'count': 0, 'pot': 0.0})
        _by_segment = defaultdict(lambda: {'count': 0, 'pot': 0.0})
        _by_comm    = defaultdict(lambda: {'count': 0, 'pot': 0.0, 'name': ''})
        for o in opportunites:
            _by_statut[o.statut]['count']  += 1
            _by_statut[o.statut]['pot']    += float(o.potentiel_mad or 0)
            _by_segment[o.segment]['count'] += 1
            _by_segment[o.segment]['pot']   += float(o.potentiel_mad or 0)
            _by_comm[o.commercial_id]['count'] += 1
            _by_comm[o.commercial_id]['pot']   += float(o.potentiel_mad or 0)
            _by_comm[o.commercial_id]['name']   = o.commercial.get_full_name() or o.commercial.username

        chart_statut  = [{'label': k, 'count': v['count'], 'pot': int(v['pot'])} for k, v in _by_statut.items()]
        chart_segment = [{'label': k, 'count': v['count'], 'pot': int(v['pot'])} for k, v in _by_segment.items()]
        chart_comm    = sorted(
            [{'label': v['name'], 'count': v['count'], 'pot': int(v['pot'])} for v in _by_comm.values()],
            key=lambda x: -x['pot']
        )

        return render(request, self.template_name, {
            'opportunites':  opportunites,
            'total_mad':     total_mad,
            'total_pond':    total_pond,
            'nb_actifs':     nb_actifs,
            'nb_alertes':    nb_alertes,
            'commerciaux':   commerciaux,
            'statuts':       OpportunitePipeline.Statut.choices,
            'segments':      OpportunitePipeline.Segment.choices,
            'f_commercial':  f_commercial,
            'f_statut':      f_statut,
            'f_segment':     f_segment,
            'is_director':   is_director(request.user),
            'chart_statut':  chart_statut,
            'chart_segment': chart_segment,
            'chart_comm':    chart_comm,
        })
