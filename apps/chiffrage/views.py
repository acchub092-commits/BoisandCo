"""
Vues du module Chiffrage — Bois&Co
RBAC :
  COMMERCIAL  → soumet et suit ses demandes
  MANAGER     → DC : valide/rejette, arbitre les modifications
  DIRECTEUR   → DG : validation finale du devis
  ESTIMATEUR  → Service Méthodes : chiffrage, fil de discussion, soumission DG
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages as django_messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import View, ListView
import mimetypes
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden, JsonResponse, FileResponse, Http404
from django.db.models import Q, Count, Sum
from django.utils import timezone

from .models import (
    DemandeChiffrage, FichierChiffrage, MessageFil,
    HistoriqueAction, DemandeModification,
)
from apps.users.models import User

ROLES_CHIFFRAGE = ('COMMERCIAL', 'MANAGER', 'DIRECTEUR', 'ESTIMATEUR', 'RESP_METHODES', 'ADMIN')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class ChiffrageRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_superuser and request.user.role not in ROLES_CHIFFRAGE:
            return HttpResponseForbidden("Accès non autorisé.")
        return super().dispatch(request, *args, **kwargs)


def _log(demande, auteur, action, detail='', ancien='', nouveau=''):
    HistoriqueAction.objects.create(
        demande=demande,
        auteur=auteur,
        action=action,
        detail=detail,
        ancien_statut=ancien,
        nouveau_statut=nouveau,
    )


def _notify(recipients, title, message, sender=None, demande=None):
    """Crée des notifications in-app pour la liste de destinataires."""
    from apps.notifications.models import Notification
    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(DemandeChiffrage) if demande else None
    for user in recipients:
        if user is None:
            continue
        Notification.objects.create(
            recipient=user,
            sender=sender,
            notification_type=Notification.Type.APPROVAL_REQUESTED,
            title=title,
            message=message,
            content_type=ct,
            object_id=demande.pk if demande else None,
        )


def _qs_for_user(user):
    """Queryset de base filtré selon le rôle."""
    qs = DemandeChiffrage.objects.select_related(
        'commercial', 'assigned_to', 'validated_by_dc', 'validated_by_dg'
    )
    if user.role == 'COMMERCIAL' and not user.is_superuser:
        return qs.filter(commercial=user)
    # MANAGER, DIRECTEUR, ESTIMATEUR, RESP_METHODES, ADMIN voient tout
    return qs


# ---------------------------------------------------------------------------
# Dashboard / Liste
# ---------------------------------------------------------------------------

class DashboardView(ChiffrageRequiredMixin, View):
    template_name = 'chiffrage/dashboard.html'

    def get(self, request):
        qs = _qs_for_user(request.user)

        # Filtres
        statut        = request.GET.get('statut', '')
        urgence       = request.GET.get('urgence', '')
        search        = request.GET.get('q', '').strip()
        retard        = request.GET.get('retard', '')
        commercial_id = request.GET.get('commercial', '')
        methodiste_id = request.GET.get('methodiste', '')

        if statut:
            qs = qs.filter(statut=statut)
        if urgence:
            qs = qs.filter(urgence=urgence)
        if search:
            qs = qs.filter(
                Q(reference__icontains=search)
                | Q(client_nom__icontains=search)
                | Q(client_ref_affaire__icontains=search)
            )
        if commercial_id:
            qs = qs.filter(commercial_id=commercial_id)
        if methodiste_id:
            qs = qs.filter(assigned_to_id=methodiste_id)

        all_qs = _qs_for_user(request.user)
        today = timezone.now().date()

        # Stats
        stats = {
            'en_attente':   all_qs.filter(statut='EN_ATTENTE').count(),
            'en_chiffrage': all_qs.filter(statut='EN_CHIFFRAGE').count(),
            'soumis_dg':    all_qs.filter(statut='SOUMIS_DG').count(),
            'valides':      all_qs.filter(statut='DEVIS_VALIDE').count(),
            'retard':       sum(
                1 for d in all_qs.exclude(statut__in=[
                    'DEVIS_VALIDE', 'TRANSMIS', 'ACCEPTE', 'REFUSE_CLI', 'ARCHIVE'
                ]) if d.delai_souhaite and d.delai_souhaite < today
            ),
            # Réponses clients — compteurs
            'accepte':    all_qs.filter(statut='ACCEPTE').count(),
            'refuse_cli': all_qs.filter(statut='REFUSE_CLI').count(),
            'rejetee':    all_qs.filter(statut='REJETEE').count(),
            # Réponses clients — montants HT
            'accepte_mad':    all_qs.filter(statut='ACCEPTE').aggregate(t=Sum('montant_ht'))['t'] or 0,
            'refuse_cli_mad': all_qs.filter(statut='REFUSE_CLI').aggregate(t=Sum('montant_ht'))['t'] or 0,
            'rejetee_mad':    all_qs.filter(statut='REJETEE').aggregate(t=Sum('montant_ht'))['t'] or 0,
        }

        # Filtre retard (post-queryset car propriété Python)
        demandes = list(qs.order_by('-created_at'))
        if retard:
            demandes = [d for d in demandes if d.is_retard]

        # Listes pour les selects — uniquement pour les rôles qui ont accès global
        from apps.users.models import User as AppUser
        can_filter_people = (
            request.user.is_superuser
            or getattr(request.user, 'role', None) in {
                User.Role.ADMIN, User.Role.DIRECTEUR, User.Role.MANAGER,
                User.Role.RESP_METHODES, User.Role.ESTIMATEUR,
            }
        )
        commerciaux = (
            AppUser.objects.filter(role=User.Role.COMMERCIAL)
            .order_by('first_name') if can_filter_people else AppUser.objects.none()
        )
        methodistes = (
            AppUser.objects.filter(role__in=[User.Role.RESP_METHODES, User.Role.ESTIMATEUR])
            .order_by('first_name') if can_filter_people else AppUser.objects.none()
        )

        return render(request, self.template_name, {
            'demandes':        demandes,
            'stats':           stats,
            'statuts':         DemandeChiffrage.Statut.choices,
            'urgences':        DemandeChiffrage.Urgence.choices,
            'sel_statut':      statut,
            'sel_urgence':     urgence,
            'search':          search,
            'sel_retard':      retard,
            'commerciaux':     commerciaux,
            'methodistes':     methodistes,
            'sel_commercial':  commercial_id,
            'sel_methodiste':  methodiste_id,
            'can_filter_people': can_filter_people,
        })


# ---------------------------------------------------------------------------
# Création demande
# ---------------------------------------------------------------------------

class DemandeCreateView(ChiffrageRequiredMixin, View):
    template_name = 'chiffrage/demande_create.html'

    def get(self, request):
        if not request.user.is_superuser and request.user.role not in ('COMMERCIAL', 'MANAGER', 'DIRECTEUR'):
            return HttpResponseForbidden()
        # Pré-remplissage depuis un lead CRM (toujours toutes les clés initialisées)
        lead_id = request.GET.get('lead_id')
        prefill = {
            'client_nom':  request.GET.get('client_nom', '') if lead_id else '',
            'description': request.GET.get('description', '') if lead_id else '',
            'lead_id':     lead_id or '',
        }
        ctx = self._ctx()
        ctx['prefill'] = prefill
        return render(request, self.template_name, ctx)

    def post(self, request):
        if not request.user.is_superuser and request.user.role not in ('COMMERCIAL', 'MANAGER', 'DIRECTEUR'):
            return HttpResponseForbidden()

        client_nom    = request.POST.get('client_nom', '').strip()
        client_ref    = request.POST.get('client_ref_affaire', '').strip()
        description   = request.POST.get('description', '').strip()
        delai         = request.POST.get('delai_souhaite', '') or None
        urgence       = request.POST.get('urgence', DemandeChiffrage.Urgence.STANDARD)
        finitions     = request.POST.get('finitions', '').strip()
        kits          = request.POST.get('kits_references', '').strip()
        quantites     = request.POST.get('quantites_estimees', '').strip()
        contraintes   = request.POST.get('contraintes_techniques', '').strip()
        commentaires  = request.POST.get('commentaires', '').strip()
        lien_telechargement = request.POST.get('lien_telechargement', '').strip()
        fichiers      = request.FILES.getlist('fichiers')

        errors = {}
        if not client_nom:
            errors['client_nom'] = 'Le nom du client est obligatoire.'
        if not description:
            errors['description'] = 'La description est obligatoire.'

        if errors:
            return render(request, self.template_name, {
                **self._ctx(), 'errors': errors, 'post': request.POST,
            })

        lead_id = request.POST.get('lead_id') or None
        # Un DC (MANAGER) qui crée sa propre demande la valide automatiquement côté DC
        # et la transmet directement aux Méthodes — pas de passage en EN_ATTENTE.
        created_by_dc = (getattr(request.user, 'role', None) == 'MANAGER')

        demande = DemandeChiffrage.objects.create(
            commercial=request.user,
            client_nom=client_nom,
            client_ref_affaire=client_ref,
            description=description,
            delai_souhaite=delai,
            urgence=urgence,
            finitions=finitions,
            kits_references=kits,
            quantites_estimees=quantites,
            contraintes_techniques=contraintes,
            commentaires=commentaires,
            lien_telechargement=lien_telechargement,
            statut=DemandeChiffrage.Statut.EN_ATTENTE,
            lead_id=lead_id,
        )

        for f in fichiers:
            FichierChiffrage.objects.create(
                demande=demande,
                fichier=f,
                nom=f.name,
                uploaded_by=request.user,
            )

        if created_by_dc:
            # Auto-validation DC : passe directement en VALIDEE_DC
            demande.statut = DemandeChiffrage.Statut.VALIDEE_DC
            demande.validated_by_dc = request.user
            demande.validated_dc_at = timezone.now()
            demande.save()

            _log(demande, request.user, 'Demande soumise',
                 nouveau=DemandeChiffrage.Statut.EN_ATTENTE)
            _log(demande, request.user, 'Validée automatiquement — créée par le DC',
                 ancien=DemandeChiffrage.Statut.EN_ATTENTE,
                 nouveau=DemandeChiffrage.Statut.VALIDEE_DC)

            # Notification → Responsable Méthodes (la DC ayant déjà validé)
            resp_methodes = User.objects.filter(role='RESP_METHODES', is_active_employee=True)
            _notify(
                resp_methodes,
                f'Nouvelle demande de chiffrage — {demande.reference}',
                f'{request.user.get_full_name()} (DC) a soumis une demande pour {client_nom}.',
                sender=request.user, demande=demande,
            )
            django_messages.success(request,
                f'Demande {demande.reference} soumise et transmise aux Méthodes.')
        else:
            _log(demande, request.user, 'Demande soumise',
                 nouveau=DemandeChiffrage.Statut.EN_ATTENTE)

            # Notification → tous les DC (MANAGER)
            dc_users = User.objects.filter(role='MANAGER', is_active_employee=True)
            _notify(
                dc_users,
                f'Nouvelle demande de chiffrage — {demande.reference}',
                f'{request.user.get_full_name()} a soumis une demande pour {client_nom}.',
                sender=request.user, demande=demande,
            )
            django_messages.success(request,
                f'Demande {demande.reference} soumise avec succès — en attente de validation.')

        return redirect('chiffrage:detail', pk=demande.pk)

    def _ctx(self):
        return {
            'urgences': DemandeChiffrage.Urgence.choices,
            'errors': {}, 'post': {},
        }


# ---------------------------------------------------------------------------
# Détail demande
# ---------------------------------------------------------------------------

class DemandeDetailView(ChiffrageRequiredMixin, View):
    template_name = 'chiffrage/demande_detail.html'

    def get(self, request, pk):
        demande = get_object_or_404(
            DemandeChiffrage.objects.prefetch_related(
                'fichiers', 'messages__auteur', 'historique__auteur',
                'demandes_modification',
            ).select_related('commercial', 'assigned_to', 'validated_by_dc', 'validated_by_dg'),
            pk=pk,
        )
        # COMMERCIAL ne voit que ses propres demandes
        if request.user.role == 'COMMERCIAL' and demande.commercial != request.user:
            return HttpResponseForbidden()

        # Fichiers — séparés en deux widgets distincts
        is_commercial = request.user.role == 'COMMERCIAL' and not request.user.is_superuser
        is_internal   = (
            request.user.role in ('DIRECTEUR', 'ESTIMATEUR', 'RESP_METHODES')
            or request.user.is_superuser
        )
        POST_DG = {'DEVIS_VALIDE', 'TRANSMIS', 'ACCEPTE', 'REFUSE_CLI', 'ARCHIVE'}
        devis_visible = demande.statut in POST_DG

        # Widget 1 — Documents du dossier (sans le devis final)
        dossier_qs = demande.fichiers.filter(is_devis=False)
        if is_commercial:
            dossier_qs = dossier_qs.filter(is_internal=False)
        fichiers = dossier_qs

        # Widget 2 — Devis (is_devis=True)
        # Utilisateurs internes (DG/Méthodes/RM) : chiffrage détaillé + devis public + archives
        # DC/Commercial : uniquement le fichier public (is_public=True) après validation DG
        all_devis_detail = demande.fichiers.filter(is_devis=True, is_public=False).order_by('-uploaded_at')
        all_devis_public = demande.fichiers.filter(is_devis=True, is_public=True).order_by('-uploaded_at')

        if is_internal:
            devis_detail   = all_devis_detail.first()
            devis_public   = all_devis_public.first()
            devis_archives = list(all_devis_detail[1:])
        elif devis_visible:
            devis_detail   = None
            devis_public   = all_devis_public.first()
            devis_archives = []
        else:
            devis_detail   = None
            devis_public   = None
            devis_archives = []

        # Messages filtrés (commerciaux ne voient pas les notes internes)
        msgs = demande.messages.filter(is_internal=False) if is_commercial else demande.messages.all()

        # Modification en attente
        modif_en_attente = demande.demandes_modification.filter(
            statut='EN_ATTENTE'
        ).first()

        # Chiffreurs disponibles (ESTIMATEUR)
        chiffreurs = User.objects.filter(role='ESTIMATEUR', is_active_employee=True)

        return render(request, self.template_name, {
            'demande':           demande,
            'fichiers':          fichiers,
            'messages':          msgs,
            'historique':        demande.historique.all(),
            'modif_en_attente':  modif_en_attente,
            'chiffreurs':        chiffreurs,
            'is_commercial':     is_commercial,
            'is_internal':       is_internal,
            'devis_detail':      devis_detail,
            'devis_public':      devis_public,
            'devis_archives':    devis_archives,
            'devis_visible':     devis_visible,
            'jalons':            DemandeChiffrage.Jalon.choices,
            'urgences':          DemandeChiffrage.Urgence.choices,
        })


# ---------------------------------------------------------------------------
# Actions DC (MANAGER)
# ---------------------------------------------------------------------------

class ActionDCView(ChiffrageRequiredMixin, View):
    def post(self, request, pk):
        if not request.user.is_superuser and request.user.role != 'MANAGER':
            return HttpResponseForbidden()

        demande = get_object_or_404(DemandeChiffrage, pk=pk)
        action  = request.POST.get('action')
        motif   = request.POST.get('motif', '').strip()

        ancien = demande.statut

        if action == 'valider':
            demande.statut = DemandeChiffrage.Statut.VALIDEE_DC
            demande.validated_by_dc = request.user
            demande.validated_dc_at = timezone.now()
            demande.save()
            _log(demande, request.user, 'Validée par DC', nouveau=demande.statut, ancien=ancien)
            # Notification → Responsable Méthodes
            resp_methodes = User.objects.filter(role='RESP_METHODES', is_active_employee=True)
            _notify(resp_methodes,
                f'Nouvelle demande à assigner — {demande.reference}',
                f'La demande {demande.reference} ({demande.client_nom}) est prête à être assignée à un méthodiste.',
                sender=request.user, demande=demande)
            django_messages.success(request, 'Demande validée et transmise au Service Méthodes.')

        elif action == 'rejeter':
            if not motif:
                django_messages.error(request, 'Un motif de rejet est obligatoire.')
                return redirect('chiffrage:detail', pk=pk)
            demande.statut = DemandeChiffrage.Statut.REJETEE
            demande.save()
            _log(demande, request.user, 'Rejetée par DC', detail=motif,
                 nouveau=demande.statut, ancien=ancien)
            _notify([demande.commercial],
                f'Demande rejetée — {demande.reference}',
                f'Votre demande a été rejetée. Motif : {motif}',
                sender=request.user, demande=demande)
            django_messages.warning(request, 'Demande rejetée. Le commercial a été notifié.')

        elif action == 'retourner':
            if not motif:
                django_messages.error(request, 'Un commentaire est obligatoire.')
                return redirect('chiffrage:detail', pk=pk)
            demande.statut = DemandeChiffrage.Statut.RETOURNEE
            demande.save()
            _log(demande, request.user, 'Retournée pour complétion', detail=motif,
                 nouveau=demande.statut, ancien=ancien)
            _notify([demande.commercial],
                f'Demande retournée — {demande.reference}',
                f'Des éléments complémentaires sont demandés : {motif}',
                sender=request.user, demande=demande)
            django_messages.info(request, 'Demande retournée au commercial pour complétion.')

        return redirect('chiffrage:detail', pk=pk)


# ---------------------------------------------------------------------------
# Actions Méthodes (ESTIMATEUR)
# ---------------------------------------------------------------------------

class AssignerView(ChiffrageRequiredMixin, View):
    def post(self, request, pk):
        if not request.user.is_superuser and request.user.role not in ('RESP_METHODES', 'DIRECTEUR'):
            return HttpResponseForbidden()
        demande = get_object_or_404(DemandeChiffrage, pk=pk,
                                    statut=DemandeChiffrage.Statut.VALIDEE_DC)
        chiffreur_id = request.POST.get('chiffreur') or None
        ancien = demande.statut
        if chiffreur_id:
            demande.assigned_to = User.objects.get(pk=chiffreur_id)
        elif request.user.role == 'RESP_METHODES':
            django_messages.error(request, 'Veuillez sélectionner un méthodiste.')
            return redirect('chiffrage:detail', pk=pk)
        else:
            demande.assigned_to = request.user
        demande.statut = DemandeChiffrage.Statut.EN_CHIFFRAGE
        demande.jalon  = DemandeChiffrage.Jalon.ANALYSE
        demande.save()
        _log(demande, request.user,
             f'Pris en charge par {demande.assigned_to.get_full_name()}',
             nouveau=demande.statut, ancien=ancien)
        django_messages.success(request, 'Demande prise en charge — chiffrage en cours.')
        return redirect('chiffrage:detail', pk=pk)


class JalonView(ChiffrageRequiredMixin, View):
    def post(self, request, pk):
        if not request.user.is_superuser and request.user.role not in ('ESTIMATEUR', 'MANAGER', 'DIRECTEUR'):
            return HttpResponseForbidden()
        demande = get_object_or_404(DemandeChiffrage, pk=pk)
        jalon = request.POST.get('jalon', '')
        if jalon in dict(DemandeChiffrage.Jalon.choices):
            demande.jalon = jalon
            demande.save(update_fields=['jalon', 'updated_at'])
            _log(demande, request.user,
                 f'Jalon mis à jour : {demande.get_jalon_display()}')
        return redirect('chiffrage:detail', pk=pk)


class MontantView(ChiffrageRequiredMixin, View):
    """Enregistrement du montant brouillon par Méthodes."""
    def post(self, request, pk):
        if not request.user.is_superuser and request.user.role not in ('ESTIMATEUR', 'MANAGER', 'DIRECTEUR'):
            return HttpResponseForbidden()
        demande = get_object_or_404(DemandeChiffrage, pk=pk)
        montant = request.POST.get('montant_ht', '').strip()
        try:
            demande.montant_ht = float(montant.replace(',', '.')) if montant else None
        except ValueError:
            pass
        demande.save(update_fields=['montant_ht', 'updated_at'])
        django_messages.success(request, 'Montant enregistré (invisible pour le commercial).')
        return redirect('chiffrage:detail', pk=pk)


class SoumettreDevisView(ChiffrageRequiredMixin, View):
    def post(self, request, pk):
        if not request.user.is_superuser and request.user.role not in ('ESTIMATEUR',):
            return HttpResponseForbidden()
        demande = get_object_or_404(
            DemandeChiffrage, pk=pk, statut=DemandeChiffrage.Statut.EN_CHIFFRAGE
        )
        fichier_detail = request.FILES.get('fichier_detail')
        fichier_public = request.FILES.get('fichier_public')
        MAX_SIZE = 50 * 1024 * 1024  # 50 Mo
        if not fichier_detail or not fichier_public:
            django_messages.error(request, 'Les deux fichiers (chiffrage détaillé et devis sans détail) sont obligatoires.')
            return redirect('chiffrage:detail', pk=pk)
        if fichier_detail.size > MAX_SIZE:
            django_messages.error(request, f'Le chiffrage détaillé dépasse la limite de 50 Mo ({fichier_detail.size // 1048576} Mo).')
            return redirect('chiffrage:detail', pk=pk)
        if fichier_public.size > MAX_SIZE:
            django_messages.error(request, f'Le devis sans détail dépasse la limite de 50 Mo ({fichier_public.size // 1048576} Mo).')
            return redirect('chiffrage:detail', pk=pk)
        FichierChiffrage.objects.create(
            demande=demande, fichier=fichier_detail, nom=fichier_detail.name,
            uploaded_by=request.user, is_devis=True, is_public=False,
        )
        FichierChiffrage.objects.create(
            demande=demande, fichier=fichier_public, nom=fichier_public.name,
            uploaded_by=request.user, is_devis=True, is_public=True,
        )
        ancien = demande.statut
        demande.statut = DemandeChiffrage.Statut.SOUMIS_RM
        demande.jalon  = ''
        demande.save()
        _log(demande, request.user, 'Devis soumis au Responsable Méthodes',
             nouveau=demande.statut, ancien=ancien)
        resp_methodes = User.objects.filter(role='RESP_METHODES', is_active_employee=True)
        _notify(resp_methodes,
            f'Devis à approuver — {demande.reference}',
            f'Le devis {demande.reference} ({demande.client_nom}) est prêt pour votre approbation.',
            sender=request.user, demande=demande)
        django_messages.success(request, 'Devis soumis au Responsable Méthodes pour approbation.')
        return redirect('chiffrage:detail', pk=pk)


class ValiderRMView(ChiffrageRequiredMixin, View):
    """Approbation ou rejet par le Responsable Méthodes."""
    def post(self, request, pk):
        if not request.user.is_superuser and request.user.role != 'RESP_METHODES':
            return HttpResponseForbidden()
        demande = get_object_or_404(
            DemandeChiffrage, pk=pk, statut=DemandeChiffrage.Statut.SOUMIS_RM
        )
        action = request.POST.get('action')
        motif  = request.POST.get('motif', '').strip()
        ancien = demande.statut

        if action == 'approuver':
            demande.statut = DemandeChiffrage.Statut.SOUMIS_DG
            demande.save()
            _log(demande, request.user, 'Approuvé par Responsable Méthodes — soumis DG',
                 nouveau=demande.statut, ancien=ancien)
            dg_users = User.objects.filter(role='DIRECTEUR', is_active_employee=True)
            _notify(dg_users,
                f'Devis à valider — {demande.reference}',
                f'Le devis {demande.reference} ({demande.client_nom}) est prêt pour votre validation.',
                sender=request.user, demande=demande)
            django_messages.success(request, 'Devis soumis à la Direction Générale.')

        elif action == 'rejeter':
            if not motif:
                django_messages.error(request, 'Un motif est requis pour retourner le devis.')
                return redirect('chiffrage:detail', pk=pk)
            demande.statut = DemandeChiffrage.Statut.EN_CHIFFRAGE
            demande.save()
            _log(demande, request.user, f'Retourné par RM : {motif}',
                 nouveau=demande.statut, ancien=ancien)
            if demande.assigned_to:
                _notify([demande.assigned_to],
                    f'Devis retourné — {demande.reference}',
                    f'Le Responsable Méthodes demande des corrections : {motif}',
                    sender=request.user, demande=demande)
            django_messages.warning(request, 'Devis retourné au méthodiste pour correction.')

        return redirect('chiffrage:detail', pk=pk)


# ---------------------------------------------------------------------------
# Actions DG (DIRECTEUR)
# ---------------------------------------------------------------------------

class ActionDGView(ChiffrageRequiredMixin, View):
    def post(self, request, pk):
        if not request.user.is_superuser and request.user.role != 'DIRECTEUR':
            return HttpResponseForbidden()
        demande = get_object_or_404(DemandeChiffrage, pk=pk)
        action = request.POST.get('action')
        motif  = request.POST.get('motif', '').strip()
        ancien = demande.statut

        if action == 'valider':
            demande.statut = DemandeChiffrage.Statut.DEVIS_VALIDE
            demande.validated_by_dg = request.user
            demande.validated_dg_at = timezone.now()
            demande.save()
            _log(demande, request.user, 'Devis validé par la DG',
                 nouveau=demande.statut, ancien=ancien)
            _notify([demande.commercial],
                f'Votre devis est prêt — {demande.reference}',
                f'Le devis pour {demande.client_nom} a été validé. Vous pouvez le consulter.',
                sender=request.user, demande=demande)
            # Création automatique du projet avec séquençage Bois&Co
            try:
                if not hasattr(demande, 'projet'):
                    from apps.projects.models import Project
                    Project.creer_depuis_chiffrage(demande, validated_by=request.user)
            except Exception:
                pass  # non-bloquant
            django_messages.success(request, 'Devis validé. Projet créé automatiquement avec le séquençage Bois&Co.')

        elif action == 'revision':
            if not motif:
                django_messages.error(request, 'Un motif est requis.')
                return redirect('chiffrage:detail', pk=pk)
            demande.statut = DemandeChiffrage.Statut.REVISION_DG
            demande.save()
            _log(demande, request.user, 'Modifications demandées par DG', detail=motif,
                 nouveau=demande.statut, ancien=ancien)
            methodes = User.objects.filter(role='ESTIMATEUR', is_active_employee=True)
            _notify(methodes,
                f'Révision demandée — {demande.reference}',
                f'La DG demande des modifications : {motif}',
                sender=request.user, demande=demande)
            django_messages.warning(request, 'Révision demandée au Service Méthodes.')

        elif action == 'refuser':
            if not motif:
                django_messages.error(request, 'Un motif de refus est requis.')
                return redirect('chiffrage:detail', pk=pk)
            demande.statut = DemandeChiffrage.Statut.ARCHIVE
            demande.save()
            _log(demande, request.user, 'Refusé et archivé par DG', detail=motif,
                 nouveau=demande.statut, ancien=ancien)
            django_messages.info(request, 'Demande refusée et archivée.')

        return redirect('chiffrage:detail', pk=pk)


# ---------------------------------------------------------------------------
# Reprise révision DG → chiffrage
# ---------------------------------------------------------------------------

class RepriseRevisionView(ChiffrageRequiredMixin, View):
    def post(self, request, pk):
        if not request.user.is_superuser and request.user.role not in ('ESTIMATEUR', 'MANAGER', 'DIRECTEUR'):
            return HttpResponseForbidden()
        demande = get_object_or_404(
            DemandeChiffrage, pk=pk, statut=DemandeChiffrage.Statut.REVISION_DG
        )
        ancien = demande.statut
        demande.statut = DemandeChiffrage.Statut.EN_CHIFFRAGE
        demande.save()
        _log(demande, request.user, 'Révision prise en compte — chiffrage repris',
             nouveau=demande.statut, ancien=ancien)
        django_messages.info(request, 'Chiffrage repris.')
        return redirect('chiffrage:detail', pk=pk)


# ---------------------------------------------------------------------------
# Résultat commercial (COMMERCIAL)
# ---------------------------------------------------------------------------

class ResultatView(ChiffrageRequiredMixin, View):
    def post(self, request, pk):
        demande = get_object_or_404(DemandeChiffrage, pk=pk)
        if request.user.role == 'COMMERCIAL' and demande.commercial != request.user:
            return HttpResponseForbidden()
        action = request.POST.get('action')
        ancien = demande.statut

        if action == 'transmettre':
            demande.statut = DemandeChiffrage.Statut.TRANSMIS
            demande.transmis_client_at = timezone.now()
            demande.save()
            _log(demande, request.user, 'Devis transmis au client',
                 nouveau=demande.statut, ancien=ancien)
            django_messages.success(request, 'Devis marqué comme transmis au client.')
        elif action == 'accepte':
            demande.statut = DemandeChiffrage.Statut.ACCEPTE
            demande.save()
            _log(demande, request.user, 'Devis accepté par le client',
                 nouveau=demande.statut, ancien=ancien)
            django_messages.success(request, 'Devis accepté par le client.')
        elif action == 'refuse':
            demande.statut = DemandeChiffrage.Statut.REFUSE_CLI
            demande.save()
            _log(demande, request.user, 'Devis refusé par le client',
                 nouveau=demande.statut, ancien=ancien)
            django_messages.info(request, 'Devis refusé par le client.')

        return redirect('chiffrage:detail', pk=pk)


# ---------------------------------------------------------------------------
# Révision technique/prix — demande par le commercial
# ---------------------------------------------------------------------------

class RevisionDemandeView(ChiffrageRequiredMixin, View):
    """Commercial demande une révision technique ou de prix après transmission au client."""

    STATUTS_AUTORISÉS = {
        DemandeChiffrage.Statut.TRANSMIS,
        DemandeChiffrage.Statut.REVISION_INFO_DC,
    }

    def post(self, request, pk):
        demande = get_object_or_404(DemandeChiffrage, pk=pk)

        if request.user.role == 'COMMERCIAL' and demande.commercial != request.user:
            django_messages.error(request, "Vous n'avez pas accès à cette demande.")
            return redirect('chiffrage:detail', pk=pk)

        if demande.statut not in self.STATUTS_AUTORISÉS:
            django_messages.error(request, "Une révision ne peut être demandée que depuis le statut « Transmis au client ».")
            return redirect('chiffrage:detail', pk=pk)

        motif = request.POST.get('motif', '').strip()
        if not motif:
            django_messages.error(request, 'Le motif de révision est obligatoire.')
            return redirect('chiffrage:detail', pk=pk)

        ancien = demande.statut
        demande.revision_motif = motif
        demande.revision_commentaire_dc = ''   # remet à zéro le commentaire DC sur re-soumission
        demande.statut = DemandeChiffrage.Statut.REVISION_DEMANDEE
        demande.save()

        # Pièce jointe optionnelle
        fichier = request.FILES.get('fichier')
        if fichier:
            FichierChiffrage.objects.create(
                demande=demande, fichier=fichier, nom=fichier.name,
                uploaded_by=request.user,
            )

        _log(demande, request.user, 'Révision technique/prix demandée', detail=motif,
             ancien=ancien, nouveau=DemandeChiffrage.Statut.REVISION_DEMANDEE)

        dc_users = User.objects.filter(role='MANAGER', is_active_employee=True)
        _notify(dc_users,
            f'Révision demandée — {demande.reference}',
            f'{request.user.get_full_name()} demande une révision : {motif[:120]}',
            sender=request.user, demande=demande)

        django_messages.success(request, 'Demande de révision transmise au Directeur Commercial.')
        return redirect('chiffrage:detail', pk=pk)


# ---------------------------------------------------------------------------
# Révision technique/prix — décision du Directeur Commercial
# ---------------------------------------------------------------------------

class RevisionDCView(ChiffrageRequiredMixin, View):
    """DC valide, demande des infos ou refuse une révision commerciale."""

    def post(self, request, pk):
        if not request.user.is_superuser and request.user.role != 'MANAGER':
            django_messages.error(request, "Action réservée au Directeur Commercial.")
            return redirect('chiffrage:detail', pk=pk)

        demande = get_object_or_404(
            DemandeChiffrage, pk=pk, statut=DemandeChiffrage.Statut.REVISION_DEMANDEE
        )
        action      = request.POST.get('action', '').strip()
        commentaire = request.POST.get('commentaire', '').strip()
        ancien      = demande.statut

        if action == 'valider':
            # DC approuve → retour circuit Méthodes (comme après validation DC normale)
            demande.statut           = DemandeChiffrage.Statut.VALIDEE_DC
            demande.validated_by_dc  = request.user
            demande.validated_dc_at  = timezone.now()
            demande.save()

            _log(demande, request.user, 'Révision approuvée par DC — transmis aux Méthodes',
                 ancien=ancien, nouveau=DemandeChiffrage.Statut.VALIDEE_DC)

            resp_methodes = User.objects.filter(role='RESP_METHODES', is_active_employee=True)
            _notify(resp_methodes,
                f'Révision à chiffrer — {demande.reference}',
                f'Révision approuvée par {request.user.get_full_name()}. Mise à jour du devis requise.',
                sender=request.user, demande=demande)

            django_messages.success(request, 'Révision approuvée — transmise au Responsable Méthodes.')

        elif action == 'info':
            if not commentaire:
                django_messages.error(request, 'Un commentaire est requis pour demander des informations.')
                return redirect('chiffrage:detail', pk=pk)

            demande.revision_commentaire_dc = commentaire
            demande.statut = DemandeChiffrage.Statut.REVISION_INFO_DC
            demande.save()

            _log(demande, request.user, 'Informations complémentaires demandées (révision)',
                 detail=commentaire, ancien=ancien, nouveau=DemandeChiffrage.Statut.REVISION_INFO_DC)

            _notify([demande.commercial],
                f'Informations requises — {demande.reference}',
                f'{request.user.get_full_name()} demande des précisions : {commentaire[:120]}',
                sender=request.user, demande=demande)

            django_messages.success(request, 'Demande d\'informations complémentaires transmise au commercial.')

        elif action == 'refuser':
            if not commentaire:
                django_messages.error(request, 'Un motif de refus est requis.')
                return redirect('chiffrage:detail', pk=pk)

            demande.statut = DemandeChiffrage.Statut.TRANSMIS   # devis initial toujours valable
            demande.revision_motif = ''
            demande.save()

            _log(demande, request.user, 'Révision refusée par DC', detail=commentaire,
                 ancien=ancien, nouveau=DemandeChiffrage.Statut.TRANSMIS)

            _notify([demande.commercial],
                f'Révision refusée — {demande.reference}',
                f'{request.user.get_full_name()} a refusé la révision : {commentaire[:120]}',
                sender=request.user, demande=demande)

            django_messages.success(request, 'Demande de révision refusée — devis initial maintenu.')

        else:
            django_messages.error(request, 'Action inconnue.')

        return redirect('chiffrage:detail', pk=pk)


# ---------------------------------------------------------------------------
# Fil de discussion
# ---------------------------------------------------------------------------

class MessageView(ChiffrageRequiredMixin, View):
    def post(self, request, pk):
        demande = get_object_or_404(DemandeChiffrage, pk=pk)
        if request.user.role == 'COMMERCIAL' and demande.commercial != request.user:
            return HttpResponseForbidden()

        contenu = request.POST.get('contenu', '').strip()
        if not contenu:
            return redirect('chiffrage:detail', pk=pk)

        fichier = request.FILES.get('fichier')
        is_internal = request.POST.get('is_internal') == '1' and request.user.role != 'COMMERCIAL'

        msg = MessageFil.objects.create(
            demande=demande,
            auteur=request.user,
            contenu=contenu,
            fichier=fichier,
            nom_fichier=fichier.name if fichier else '',
            is_internal=is_internal,
        )
        _log(demande, request.user,
             'Note interne ajoutée' if is_internal else 'Message envoyé dans le fil')

        # Notification selon rôle
        if request.user.role == 'COMMERCIAL':
            # notifier Méthodes assigné + DC
            recipients = list(filter(None, [demande.assigned_to]))
            recipients += list(User.objects.filter(role='MANAGER', is_active_employee=True))
        else:
            recipients = [demande.commercial] if not is_internal else []

        _notify(recipients,
            f'Nouveau message — {demande.reference}',
            f'{request.user.get_full_name()} : {contenu[:100]}',
            sender=request.user, demande=demande)

        return redirect('chiffrage:detail', pk=pk)


# ---------------------------------------------------------------------------
# Upload fichier
# ---------------------------------------------------------------------------

class FichierUploadView(ChiffrageRequiredMixin, View):
    def post(self, request, pk):
        demande = get_object_or_404(DemandeChiffrage, pk=pk)
        if request.user.role == 'COMMERCIAL' and demande.commercial != request.user:
            return HttpResponseForbidden()
        if request.user.role == 'COMMERCIAL' and not demande.can_commercial_edit:
            django_messages.error(request, 'Modification impossible dans ce statut.')
            return redirect('chiffrage:detail', pk=pk)

        fichiers = request.FILES.getlist('fichiers')
        is_internal = request.POST.get('is_internal') == '1' and request.user.role != 'COMMERCIAL'
        for f in fichiers:
            FichierChiffrage.objects.create(
                demande=demande, fichier=f, nom=f.name,
                uploaded_by=request.user, is_internal=is_internal,
            )
        _log(demande, request.user, f'{len(fichiers)} fichier(s) ajouté(s)')
        django_messages.success(request, f'{len(fichiers)} fichier(s) ajouté(s).')
        return redirect('chiffrage:detail', pk=pk)


# ---------------------------------------------------------------------------
# Demande de modification (Commercial → DC arbitrage)
# ---------------------------------------------------------------------------

class ModificationView(ChiffrageRequiredMixin, View):
    def post(self, request, pk):
        demande = get_object_or_404(DemandeChiffrage, pk=pk,
                                    statut=DemandeChiffrage.Statut.EN_CHIFFRAGE)
        if request.user.role == 'COMMERCIAL' and demande.commercial != request.user:
            return HttpResponseForbidden()

        nature       = request.POST.get('nature', '').strip()
        justif       = request.POST.get('justification', '').strip()
        urgence      = request.POST.get('urgence', 'STANDARD')

        if not nature or not justif:
            django_messages.error(request, 'Nature et justification sont obligatoires.')
            return redirect('chiffrage:detail', pk=pk)

        DemandeModification.objects.create(
            demande=demande, soumis_par=request.user,
            nature=nature, justification=justif, urgence=urgence,
        )
        _log(demande, request.user, 'Demande de modification soumise', detail=nature)

        dc_users = User.objects.filter(role='MANAGER', is_active_employee=True)
        _notify(list(dc_users) + list(User.objects.filter(role='ESTIMATEUR', is_active_employee=True)),
            f'Demande de modification — {demande.reference}',
            f'{request.user.get_full_name()} demande une modification : {nature}',
            sender=request.user, demande=demande)
        django_messages.success(request, 'Demande de modification soumise au DC.')
        return redirect('chiffrage:detail', pk=pk)


class ArbitrerModifView(ChiffrageRequiredMixin, View):
    def post(self, request, pk):
        if not request.user.is_superuser and request.user.role != 'MANAGER':
            return HttpResponseForbidden()
        modif  = get_object_or_404(DemandeModification, pk=pk)
        action = request.POST.get('action')
        motif  = request.POST.get('motif', '').strip()

        modif.traite_par = request.user
        modif.traite_at  = timezone.now()

        if action == 'accepter':
            modif.statut = DemandeModification.Statut.ACCEPTEE
            modif.save()
            modif.demande.statut = DemandeChiffrage.Statut.EN_CHIFFRAGE
            modif.demande.save(update_fields=['statut', 'updated_at'])
            _log(modif.demande, request.user,
                 'Modification acceptée par DC', detail=modif.nature)
            methodes = User.objects.filter(role='ESTIMATEUR', is_active_employee=True)
            _notify(methodes,
                f'Modification acceptée — {modif.demande.reference}',
                f'Le DC a accepté une modification : {modif.nature}',
                sender=request.user, demande=modif.demande)
            django_messages.success(request, 'Modification acceptée.')
        elif action == 'refuser':
            modif.statut = DemandeModification.Statut.REFUSEE
            modif.motif_refus = motif
            modif.save()
            _log(modif.demande, request.user,
                 'Modification refusée par DC', detail=motif)
            _notify([modif.soumis_par],
                f'Modification refusée — {modif.demande.reference}',
                f'Votre demande de modification a été refusée. Motif : {motif}',
                sender=request.user, demande=modif.demande)
            django_messages.info(request, 'Modification refusée.')

        return redirect('chiffrage:detail', pk=modif.demande.pk)


# ---------------------------------------------------------------------------
# Visionneuse sécurisée — devis final
# ---------------------------------------------------------------------------

class DevisPreviewView(ChiffrageRequiredMixin, View):
    """
    Sert un fichier devis (is_devis=True) en mode inline (aperçu navigateur).
    Pas de téléchargement forcé ; accès conditionné au rôle et au statut de la demande.
    """

    POST_DG = {'DEVIS_VALIDE', 'TRANSMIS', 'ACCEPTE', 'REFUSE_CLI', 'ARCHIVE'}

    def get(self, request, pk, fichier_pk):
        demande = get_object_or_404(DemandeChiffrage, pk=pk)
        fichier = get_object_or_404(
            FichierChiffrage, pk=fichier_pk, demande=demande, is_devis=True
        )

        devis_visible = demande.statut in self.POST_DG

        if request.user.role in ('DIRECTEUR', 'ESTIMATEUR', 'RESP_METHODES') or request.user.is_superuser:
            pass  # accès complet à toutes les versions
        elif devis_visible:
            # DC et Commercial : uniquement le fichier public (sans détail), version la plus récente
            if not fichier.is_public:
                raise Http404
            latest = (
                demande.fichiers.filter(is_devis=True, is_public=True)
                .order_by('-uploaded_at')
                .first()
            )
            if not latest or latest.pk != fichier.pk:
                raise Http404
        else:
            raise Http404

        content_type, _ = mimetypes.guess_type(fichier.fichier.name)
        content_type = content_type or 'application/octet-stream'

        response = FileResponse(
            fichier.fichier.open('rb'),
            content_type=content_type,
        )
        response['Content-Disposition'] = f'inline; filename="{fichier.nom}"'
        response['X-Content-Type-Options'] = 'nosniff'
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        response['Pragma'] = 'no-cache'
        # Autoriser l'iframe same-origin (override du middleware XFrameOptions)
        response['X-Frame-Options'] = 'SAMEORIGIN'
        return response


# ---------------------------------------------------------------------------
# Téléchargement sécurisé d'un fichier du dossier
# ---------------------------------------------------------------------------

class FichierDownloadView(ChiffrageRequiredMixin, View):
    """Sert un FichierChiffrage (is_devis=False) avec Content-Disposition: attachment."""

    def get(self, request, pk, fichier_pk):
        demande = get_object_or_404(DemandeChiffrage, pk=pk)
        fichier = get_object_or_404(FichierChiffrage, pk=fichier_pk, demande=demande, is_devis=False)

        try:
            content_type, _ = mimetypes.guess_type(fichier.fichier.name)
            content_type = content_type or 'application/octet-stream'
            response = FileResponse(fichier.fichier.open('rb'), content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{fichier.nom}"'
            return response
        except FileNotFoundError:
            django_messages.error(
                request,
                f'Le fichier « {fichier.nom} » est introuvable sur le serveur. '
                'Contactez un administrateur.'
            )
            return redirect('chiffrage:detail', pk=pk)


# ---------------------------------------------------------------------------
# Suppression fichier — réservé aux administrateurs
# ---------------------------------------------------------------------------

class FichierDeleteView(ChiffrageRequiredMixin, View):
    """Supprime un FichierChiffrage du disque et de la base — admin/superuser uniquement."""

    def post(self, request, pk, fichier_pk):
        if not (request.user.is_superuser or
                getattr(request.user, 'role', None) == User.Role.ADMIN):
            django_messages.error(
                request,
                "Action non autorisée : seuls les administrateurs peuvent supprimer des documents."
            )
            return redirect('chiffrage:detail', pk=pk)

        demande = get_object_or_404(DemandeChiffrage, pk=pk)
        fichier = get_object_or_404(FichierChiffrage, pk=fichier_pk, demande=demande)

        nom = fichier.nom
        fichier.fichier.delete(save=False)  # supprime le fichier physique
        fichier.delete()

        _log(demande, request.user, f'Fichier supprimé : {nom}')
        django_messages.success(request, f'Fichier « {nom} » supprimé.')
        return redirect('chiffrage:detail', pk=pk)
