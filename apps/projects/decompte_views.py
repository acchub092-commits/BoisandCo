"""
Vues module Suivi Décomptes — autonome, aucune liaison avec le modèle Project.
"""
import csv
import io
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View

from apps.projects.models import DecompteProjet, DecompteAvenant, DecompteLigne
from apps.projects.decompte_forms import DecompteProjetForm, DecompteAvenantForm, DecompteLigneForm
from apps.projects.decompte_service import (
    peut_lire, peut_ecrire, compute_kpis, get_dashboard_rows,
)
from apps.users.models import User


def _check_lecture(user):
    if not peut_lire(user):
        raise PermissionDenied


def _check_ecriture(user):
    if not peut_ecrire(user):
        raise PermissionDenied


# ── Dashboard global ──────────────────────────────────────────────────────────

class DecompteDashboardView(LoginRequiredMixin, View):
    template_name = 'decomptes/dashboard.html'

    def get(self, request):
        _check_lecture(request.user)
        rows = get_dashboard_rows(request.user)

        total_marche     = sum(r['marche_yc_avenants'] for r in rows)
        total_liv        = sum(r['cumul_liv_systeme']   for r in rows)
        total_reglements = sum(r['cumul_reglements']    for r in rows)
        total_non_attach = sum(r['reste_a_attacher']    for r in rows if r['reste_a_attacher'] > 0)
        total_reste_liv  = sum(r['reste_a_livrer']      for r in rows)
        nb_alertes       = sum(1 for r in rows if r['alerte_acompte'] < 0)

        return render(request, self.template_name, {
            'rows':             rows,
            'total_marche':     total_marche,
            'total_liv':        total_liv,
            'total_reglements': total_reglements,
            'total_non_attach': total_non_attach,
            'total_reste_liv':  total_reste_liv,
            'nb_alertes':       nb_alertes,
            'peut_ecrire':      peut_ecrire(request.user),
        })


# ── Création d'un projet décompte ─────────────────────────────────────────────

class DecompteProjetCreateView(LoginRequiredMixin, View):
    template_name = 'decomptes/projet_form.html'

    def get(self, request):
        _check_ecriture(request.user)
        return render(request, self.template_name, {'form': DecompteProjetForm(), 'is_edit': False})

    def post(self, request):
        _check_ecriture(request.user)
        form = DecompteProjetForm(request.POST)
        if form.is_valid():
            dp = form.save(commit=False)
            dp.created_by = request.user
            dp.save()
            messages.success(request, f'Projet « {dp.reference} » créé.')
            return redirect('projects:decompte_projet', pk=dp.pk)
        return render(request, self.template_name, {'form': form, 'is_edit': False})


# ── Fiche projet décompte ─────────────────────────────────────────────────────

class DecompteProjetDetailView(LoginRequiredMixin, View):
    template_name = 'decomptes/projet_detail.html'

    def get(self, request, pk):
        _check_lecture(request.user)
        projet   = get_object_or_404(DecompteProjet, pk=pk)
        kpis     = compute_kpis(projet)
        lignes   = projet.decompte_lignes.select_related('saisie_par').order_by('-created_at')
        avenants = projet.avenants_decompte.order_by('date_avenant')
        return render(request, self.template_name, {
            'projet':      projet,
            'kpis':        kpis,
            'lignes':      lignes,
            'avenants':    avenants,
            'meta_form':   DecompteProjetForm(instance=projet),
            'peut_ecrire': peut_ecrire(request.user),
        })

    def post(self, request, pk):
        _check_ecriture(request.user)
        projet = get_object_or_404(DecompteProjet, pk=pk)
        form   = DecompteProjetForm(request.POST, instance=projet)
        if form.is_valid():
            form.save()
            messages.success(request, 'Informations projet mises à jour.')
            return redirect('projects:decompte_projet', pk=pk)
        kpis     = compute_kpis(projet)
        lignes   = projet.decompte_lignes.select_related('saisie_par').order_by('-created_at')
        avenants = projet.avenants_decompte.order_by('date_avenant')
        return render(request, self.template_name, {
            'projet':      projet,
            'kpis':        kpis,
            'lignes':      lignes,
            'avenants':    avenants,
            'meta_form':   form,
            'peut_ecrire': True,
        })


# ── Saisie / édition d'une ligne de décompte ─────────────────────────────────

class DecompteSaisieView(LoginRequiredMixin, View):
    template_name = 'decomptes/saisie.html'

    def _get_ligne(self, pk, lid):
        return get_object_or_404(DecompteLigne, pk=lid, projet_id=pk) if lid else None

    def get(self, request, pk, lid=None):
        _check_ecriture(request.user)
        projet = get_object_or_404(DecompteProjet, pk=pk)
        kpis   = compute_kpis(projet)
        ligne  = self._get_ligne(pk, lid)
        if ligne:
            form    = DecompteLigneForm(instance=ligne)
            is_edit = True
        else:
            from datetime import date as _date
            today = _date.today()
            form    = DecompteLigneForm(initial={
                'semaine': today.isocalendar()[1],
                'annee':   today.year,
                'is_dernier_decompte': True,
            })
            is_edit = False
        return render(request, self.template_name, {
            'projet':  projet,
            'kpis':    kpis,
            'form':    form,
            'is_edit': is_edit,
            'ligne':   ligne,
        })

    def post(self, request, pk, lid=None):
        _check_ecriture(request.user)
        projet = get_object_or_404(DecompteProjet, pk=pk)
        ligne  = self._get_ligne(pk, lid)
        form   = DecompteLigneForm(request.POST, instance=ligne)
        if form.is_valid():
            obj            = form.save(commit=False)
            obj.projet     = projet
            obj.saisie_par = request.user
            obj.save()
            msg = 'Décompte mis à jour.' if ligne else 'Nouvelle ligne de décompte enregistrée.'
            messages.success(request, msg)
            return redirect('projects:decompte_projet', pk=pk)
        kpis = compute_kpis(projet)
        return render(request, self.template_name, {
            'projet':  projet,
            'kpis':    kpis,
            'form':    form,
            'is_edit': ligne is not None,
            'ligne':   ligne,
        })


# ── Avenant ───────────────────────────────────────────────────────────────────

class AvenantCreateView(LoginRequiredMixin, View):
    template_name = 'decomptes/avenant_form.html'

    def get(self, request, pk):
        _check_ecriture(request.user)
        projet = get_object_or_404(DecompteProjet, pk=pk)
        return render(request, self.template_name, {'projet': projet, 'form': DecompteAvenantForm()})

    def post(self, request, pk):
        _check_ecriture(request.user)
        projet = get_object_or_404(DecompteProjet, pk=pk)
        form   = DecompteAvenantForm(request.POST)
        if form.is_valid():
            av            = form.save(commit=False)
            av.projet     = projet
            av.created_by = request.user
            av.save()
            messages.success(request, f'Avenant « {av.libelle} » ajouté.')
            return redirect('projects:decompte_projet', pk=pk)
        return render(request, self.template_name, {'projet': projet, 'form': form})


class AvenantDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk, aid):
        _check_ecriture(request.user)
        av = get_object_or_404(DecompteAvenant, pk=aid, projet_id=pk)
        av.delete()
        messages.success(request, 'Avenant supprimé.')
        return redirect('projects:decompte_projet', pk=pk)


# ── Import CSV ────────────────────────────────────────────────────────────────

class ImportDecompteCSVView(LoginRequiredMixin, View):
    """
    Import CSV multi-lignes — crée ou met à jour des DecompteProjet autonomes.
    Aucune recherche dans la base Project.

    Structure du fichier (séparateur ;) :
    - Ligne avec Projet non vide  → nouveau DecompteProjet
    - Lignes sans Projet          → DecompteLigne supplémentaires du même projet
    Colonnes calculées ignorées : TTC, Alerte Acompte, Marché yc Avenants,
    Cumul Règlements, Reste à Livrer, Reste à Attacher.
    """
    template_name = 'decomptes/import_csv.html'

    TYPE_MAP = {
        'DECOMPTE': 'DECOMPTE', 'DÉCOMPTE': 'DECOMPTE',
        'SITUATION': 'SITUATION',
        'FACTURE':   'FACTURE',
        'AVOIR':     'AVOIR',
    }

    def get(self, request):
        _check_ecriture(request.user)
        return render(request, self.template_name)

    def post(self, request):
        _check_ecriture(request.user)
        fichier = request.FILES.get('fichier')
        if not fichier:
            messages.error(request, 'Aucun fichier sélectionné.')
            return render(request, self.template_name)

        try:
            content = fichier.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            fichier.seek(0)
            content = fichier.read().decode('cp1252')

        # Table de lookup utilisateurs (prénom → User)
        user_map = {
            u.first_name.strip().lower(): u
            for u in User.objects.filter(is_active_employee=True)
            if u.first_name.strip()
        }

        reader = csv.DictReader(io.StringIO(content), delimiter=';')

        # ── Passe 1 : grouper les lignes par projet ────────────────────────
        groups  = []
        current = None

        for i, raw_row in enumerate(reader, start=2):
            row = {(k.strip() if k else ''): (v.strip() if v else '') for k, v in raw_row.items()}
            if not any(row.values()):
                continue
            projet_name = self._get(row, 'projet')
            if projet_name:
                current = {'base': row, 'lignes': [row], 'line': i}
                groups.append(current)
            elif current is not None:
                current['lignes'].append(row)

        # ── Passe 2 : créer / mettre à jour les objets ────────────────────
        imported = []
        skipped  = []

        for group in groups:
            base       = group['base']
            lignes     = group['lignes']
            start_line = group['line']

            reference   = self._get(base, 'projet')
            client_name = self._get(base, 'client')

            if not reference:
                continue

            # Créer ou récupérer le DecompteProjet (clé = reference)
            dp, created = DecompteProjet.objects.get_or_create(
                reference=reference,
                defaults={'client_name': client_name or reference, 'created_by': request.user},
            )

            # Mise à jour des champs base
            if client_name:
                dp.client_name = client_name
            dp.nom_projet = self._get(base, 'nom_projet') or dp.nom_projet

            adj_raw      = self._get(base, 'adjudication').lower()
            dp.adjudication = adj_raw in ('oui', 'yes', '1', 'true')

            dp.lot = self._get(base, 'lot') or dp.lot

            regime_raw = (self._get(base, 'régime') or self._get(base, 'regime')).upper()
            dp.regime  = 'SANS_TVA' if 'SANS' in regime_raw else 'AVEC_TVA'

            montant_ht = self._dec(self._get(base, 'montant marché ht') or self._get(base, 'montant marche ht'))
            if montant_ht:
                dp.montant_marche_ht = montant_ht

            comm_prenom = self._get(base, 'commercial')
            if comm_prenom:
                dp.commercial = user_map.get(comm_prenom.lower())

            chef_prenom = self._get(base, 'chef de projet')
            if chef_prenom:
                dp.chef_de_projet = user_map.get(chef_prenom.lower())

            # init_* = 0 (tous les décomptes sont fournis dans le fichier)
            for field in ('init_attachement', 'init_rg', 'init_rf', 'init_prorata',
                          'init_acompte', 'init_reglements', 'init_liv_systeme'):
                setattr(dp, field, Decimal('0'))

            dp.save()

            # Avenant
            avenant_val = self._dec(self._get(base, 'avenants'))
            if avenant_val:
                DecompteAvenant.objects.get_or_create(
                    projet=dp,
                    libelle='Avenant (import CSV)',
                    defaults={'montant_ht': avenant_val, 'created_by': request.user},
                )

            # Suppression et re-création des lignes (re-import idempotent)
            dp.decompte_lignes.all().delete()

            for j, lg_row in enumerate(lignes):
                is_last = (j == len(lignes) - 1)

                type_raw = (
                    self._get(lg_row, 'type opération') or
                    self._get(lg_row, 'type operation') or 'DECOMPTE'
                ).upper()
                type_op = self.TYPE_MAP.get(type_raw, 'DECOMPTE')

                DecompteLigne.objects.create(
                    projet                = dp,
                    numero_decompte       = self._get(lg_row, 'n° décompte') or self._get(lg_row, 'n° decompte'),
                    type_operation        = type_op,
                    date_edition_facture  = self._date(
                        self._get(lg_row, 'date édition facture') or
                        self._get(lg_row, 'date edition facture')
                    ),
                    ref_piece             = (
                        self._get(lg_row, 'réf. pièce') or
                        self._get(lg_row, 'ref. piece') or
                        self._get(lg_row, 'réf pièce')
                    ),
                    attachement           = self._dec(self._get(lg_row, 'attachement')),
                    prorata               = self._dec(self._get(lg_row, 'prorata')),
                    rg                    = self._dec(self._get(lg_row, 'rg')),
                    rf                    = self._dec(self._get(lg_row, 'rf')),
                    autre                 = self._dec(self._get(lg_row, 'autre')),
                    amortissement_acompte = self._dec(
                        self._get(lg_row, "amortissement d'acompte") or
                        self._get(lg_row, 'amortissement acompte')
                    ),
                    acompte               = self._dec(self._get(lg_row, 'acompte')),
                    ht                    = self._dec(self._get(lg_row, 'ht')),
                    reglement             = self._dec(
                        self._get(lg_row, 'reglement') or self._get(lg_row, 'règlement')
                    ),
                    liv_systeme           = self._dec(
                        self._get(lg_row, 'liv système') or
                        self._get(lg_row, 'liv systeme') or
                        self._get(lg_row, 'liv système')
                    ),
                    is_dernier_decompte   = is_last,
                    saisie_par            = request.user,
                )

            imported.append({
                'ref':       dp.reference,
                'client':    dp.client_name,
                'projet':    reference,
                'nb_lignes': len(lignes),
                'created':   created,
            })

        return render(request, self.template_name, {
            'imported': imported,
            'skipped':  skipped,
            'done':     True,
        })

    @staticmethod
    def _get(row: dict, key: str) -> str:
        key_lower = key.lower()
        for k, v in row.items():
            if k.lower() == key_lower:
                return (v or '').strip()
        return ''

    @staticmethod
    def _dec(s) -> Decimal:
        if not s:
            return Decimal('0')
        s = str(s).strip().replace('\xa0', '').replace(' ', '').replace(',', '.')
        try:
            return Decimal(s)
        except InvalidOperation:
            return Decimal('0')

    @staticmethod
    def _date(s):
        if not s:
            return None
        from datetime import datetime
        s = str(s).strip()
        for fmt in ('%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d'):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None
