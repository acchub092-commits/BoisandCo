"""
API mobile du module Chiffrage — parcours commercial terrain (création de demande
avec photos, suivi, messagerie) + Directeur Commercial, DG, Responsable Méthodes et
Méthodes/Estimateur (actions de validation/traitement des étapes qui les concernent,
avec notification push relayée automatiquement par apps.notifications).
"""
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.models import User

from .models import DemandeChiffrage, FichierChiffrage, MessageFil
from .permissions import IsChiffrageMobileUser
from .serializers import (
    DemandeChiffrageCreateSerializer, DemandeChiffrageDetailSerializer,
    DemandeChiffrageListSerializer, FichierChiffrageSerializer, MessageFilSerializer,
)
from .views import _log, _notify, _qs_for_user

RETARD_EXCLUS = [
    DemandeChiffrage.Statut.DEVIS_VALIDE, DemandeChiffrage.Statut.TRANSMIS,
    DemandeChiffrage.Statut.ACCEPTE, DemandeChiffrage.Statut.REFUSE_CLI,
    DemandeChiffrage.Statut.ARCHIVE,
]


class DemandeChiffrageViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsChiffrageMobileUser]
    http_method_names = ['get', 'post', 'head']
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        qs = _qs_for_user(self.request.user)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        if self.request.query_params.get('retard'):
            qs = qs.exclude(statut__in=RETARD_EXCLUS).filter(delai_souhaite__lt=timezone.now().date())
        search = self.request.query_params.get('q', '').strip()
        if search:
            qs = qs.filter(
                Q(reference__icontains=search)
                | Q(client_nom__icontains=search)
                | Q(client_ref_affaire__icontains=search)
            )
        return qs.prefetch_related('historique__auteur')

    def get_serializer_class(self):
        if self.action == 'create':
            return DemandeChiffrageCreateSerializer
        if self.action == 'retrieve':
            return DemandeChiffrageDetailSerializer
        return DemandeChiffrageListSerializer

    def perform_create(self, serializer):
        user = self.request.user
        demande = serializer.save(
            commercial=user,
            statut=DemandeChiffrage.Statut.EN_ATTENTE,
        )

        # Un DC (MANAGER) qui crée sa propre demande la valide automatiquement et la
        # transmet directement aux Méthodes — réplique exactement DemandeCreateView (web).
        if user.role == 'MANAGER':
            demande.statut = DemandeChiffrage.Statut.VALIDEE_DC
            demande.validated_by_dc = user
            demande.validated_dc_at = timezone.now()
            demande.save()

            _log(demande, user, 'Demande soumise', nouveau=DemandeChiffrage.Statut.EN_ATTENTE)
            _log(demande, user, 'Validée automatiquement — créée par le DC',
                 ancien=DemandeChiffrage.Statut.EN_ATTENTE, nouveau=DemandeChiffrage.Statut.VALIDEE_DC)

            resp_methodes = User.objects.filter(role='RESP_METHODES', is_active_employee=True)
            _notify(
                resp_methodes,
                f'Nouvelle demande de chiffrage — {demande.reference}',
                f'{user.get_full_name()} (DC) a soumis une demande pour {demande.client_nom}.',
                sender=user, demande=demande,
            )
        else:
            _log(demande, user, 'Demande soumise', nouveau=DemandeChiffrage.Statut.EN_ATTENTE)
            dc_users = User.objects.filter(role='MANAGER', is_active_employee=True)
            _notify(
                dc_users,
                f'Nouvelle demande de chiffrage — {demande.reference}',
                f'{user.get_full_name()} a soumis une demande pour {demande.client_nom}.',
                sender=user, demande=demande,
            )
        self._demande_cree = demande

    def create(self, request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.role in ('COMMERCIAL', 'MANAGER')):
            raise PermissionDenied("Seul un commercial ou le Directeur Commercial peut soumettre une demande depuis l'application mobile.")
        response = super().create(request, *args, **kwargs)
        demande = self._demande_cree
        response.data = DemandeChiffrageDetailSerializer(demande, context={'request': request}).data
        response.status_code = status.HTTP_201_CREATED
        return response

    @action(detail=True, methods=['post'], url_path='messages')
    def add_message(self, request, pk=None):
        demande = self.get_object()
        contenu = (request.data.get('contenu') or '').strip()
        if not contenu:
            return Response({'detail': 'Le message ne peut pas être vide.'}, status=status.HTTP_400_BAD_REQUEST)

        msg = MessageFil.objects.create(
            demande=demande, auteur=request.user, contenu=contenu,
            fichier=request.FILES.get('fichier'),
            nom_fichier=(request.FILES.get('fichier').name if request.FILES.get('fichier') else ''),
            is_internal=False,
        )
        _log(demande, request.user, 'Message ajouté')
        if demande.assigned_to_id:
            _notify(
                [demande.assigned_to], f'Nouveau message — {demande.reference}',
                f'{request.user.get_full_name()} a répondu sur {demande.reference}.',
                sender=request.user, demande=demande,
            )
        return Response(
            MessageFilSerializer(msg, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='photos',
            parser_classes=[MultiPartParser, FormParser])
    def add_photos(self, request, pk=None):
        demande = self.get_object()
        fichiers = request.FILES.getlist('fichiers')
        if not fichiers:
            return Response({'detail': 'Aucun fichier reçu.'}, status=status.HTTP_400_BAD_REQUEST)

        created = [
            FichierChiffrage.objects.create(
                demande=demande, fichier=f, nom=f.name, uploaded_by=request.user,
            )
            for f in fichiers
        ]
        _log(demande, request.user, f'{len(created)} photo(s) ajoutée(s)')
        return Response(
            FichierChiffrageSerializer(created, many=True, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='action-dc')
    def action_dc(self, request, pk=None):
        """Décision du Directeur Commercial — réplique exactement ActionDCView (web)."""
        if not (request.user.is_superuser or request.user.role == 'MANAGER'):
            raise PermissionDenied("Réservé au Directeur Commercial.")

        demande = self.get_object()
        decision = request.data.get('action')
        motif = (request.data.get('motif') or '').strip()
        ancien = demande.statut

        if decision == 'valider':
            demande.statut = DemandeChiffrage.Statut.VALIDEE_DC
            demande.validated_by_dc = request.user
            demande.validated_dc_at = timezone.now()
            demande.save()
            _log(demande, request.user, 'Validée par DC', nouveau=demande.statut, ancien=ancien)
            resp_methodes = User.objects.filter(role='RESP_METHODES', is_active_employee=True)
            _notify(
                resp_methodes, f'Nouvelle demande à assigner — {demande.reference}',
                f'La demande {demande.reference} ({demande.client_nom}) est prête à être assignée à un méthodiste.',
                sender=request.user, demande=demande,
            )
        elif decision == 'rejeter':
            if not motif:
                return Response({'detail': 'Un motif de rejet est obligatoire.'}, status=status.HTTP_400_BAD_REQUEST)
            demande.statut = DemandeChiffrage.Statut.REJETEE
            demande.save()
            _log(demande, request.user, 'Rejetée par DC', detail=motif, nouveau=demande.statut, ancien=ancien)
            _notify(
                [demande.commercial], f'Demande rejetée — {demande.reference}',
                f'Votre demande a été rejetée. Motif : {motif}', sender=request.user, demande=demande,
            )
        elif decision == 'retourner':
            if not motif:
                return Response({'detail': 'Un commentaire est obligatoire.'}, status=status.HTTP_400_BAD_REQUEST)
            demande.statut = DemandeChiffrage.Statut.RETOURNEE
            demande.save()
            _log(demande, request.user, 'Retournée pour complétion', detail=motif,
                 nouveau=demande.statut, ancien=ancien)
            _notify(
                [demande.commercial], f'Demande retournée — {demande.reference}',
                f'Des éléments complémentaires sont demandés : {motif}', sender=request.user, demande=demande,
            )
        else:
            return Response({'detail': 'Action inconnue.'}, status=status.HTTP_400_BAD_REQUEST)

        demande.refresh_from_db()
        return Response(DemandeChiffrageDetailSerializer(demande, context={'request': request}).data)

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """KPI du tableau de bord mobile — mêmes indicateurs et même périmètre
        (_qs_for_user) que DashboardView (web)."""
        qs = _qs_for_user(request.user)
        today = timezone.now().date()
        data = {
            'en_attente':   qs.filter(statut='EN_ATTENTE').count(),
            'en_chiffrage': qs.filter(statut='EN_CHIFFRAGE').count(),
            'soumis_dg':    qs.filter(statut='SOUMIS_DG').count(),
            'valides':      qs.filter(statut='DEVIS_VALIDE').count(),
            'retard':       qs.exclude(statut__in=RETARD_EXCLUS).filter(delai_souhaite__lt=today).count(),
            'accepte':      qs.filter(statut='ACCEPTE').count(),
            'refuse_cli':   qs.filter(statut='REFUSE_CLI').count(),
            'rejetee':      qs.filter(statut='REJETEE').count(),
            'accepte_mad':    qs.filter(statut='ACCEPTE').aggregate(t=Sum('montant_ht'))['t'] or 0,
            'refuse_cli_mad': qs.filter(statut='REFUSE_CLI').aggregate(t=Sum('montant_ht'))['t'] or 0,
            'rejetee_mad':    qs.filter(statut='REJETEE').aggregate(t=Sum('montant_ht'))['t'] or 0,
        }
        return Response(data)

    @action(detail=True, methods=['post'], url_path='action-rm')
    def action_rm(self, request, pk=None):
        """Décision du Responsable Méthodes — réplique exactement ValiderRMView (web)."""
        if not (request.user.is_superuser or request.user.role == 'RESP_METHODES'):
            raise PermissionDenied("Réservé au Responsable Méthodes.")

        demande = self.get_object()
        if demande.statut != DemandeChiffrage.Statut.SOUMIS_RM:
            return Response(
                {'detail': "Cette demande n'est plus soumise au Responsable Méthodes."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        decision = request.data.get('action')
        motif = (request.data.get('motif') or '').strip()
        ancien = demande.statut

        if decision == 'approuver':
            demande.statut = DemandeChiffrage.Statut.SOUMIS_DG
            demande.rm_rejet_motif = ''
            demande.save()
            _log(demande, request.user, 'Approuvé par Responsable Méthodes — soumis DG',
                 nouveau=demande.statut, ancien=ancien)
            dg_users = User.objects.filter(role='DIRECTEUR', is_active_employee=True)
            _notify(
                dg_users, f'Devis à valider — {demande.reference}',
                f'Le devis {demande.reference} ({demande.client_nom}) est prêt pour votre validation.',
                sender=request.user, demande=demande,
            )
        elif decision == 'rejeter':
            if not motif:
                return Response({'detail': 'Un motif est requis pour retourner le devis.'}, status=status.HTTP_400_BAD_REQUEST)
            demande.statut = DemandeChiffrage.Statut.EN_CHIFFRAGE
            demande.rm_rejet_motif = motif
            demande.save()
            _log(demande, request.user, f'Retourné par RM : {motif}', nouveau=demande.statut, ancien=ancien)
            if demande.assigned_to:
                _notify(
                    [demande.assigned_to], f'Devis retourné — {demande.reference}',
                    f'Le Responsable Méthodes demande des corrections : {motif}',
                    sender=request.user, demande=demande,
                )
        else:
            return Response({'detail': 'Action inconnue.'}, status=status.HTTP_400_BAD_REQUEST)

        demande.refresh_from_db()
        return Response(DemandeChiffrageDetailSerializer(demande, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='jalon')
    def set_jalon(self, request, pk=None):
        """Mise à jour du jalon interne Méthodes — réplique JalonView (web)."""
        if not (request.user.is_superuser or request.user.role == 'ESTIMATEUR'):
            raise PermissionDenied("Réservé au Service Méthodes.")

        demande = self.get_object()
        if not request.user.is_superuser and demande.assigned_to_id != request.user.id:
            raise PermissionDenied("Cette demande n'est pas affectée à votre compte.")
        jalon = request.data.get('jalon', '')
        if jalon not in dict(DemandeChiffrage.Jalon.choices):
            return Response({'detail': 'Jalon invalide.'}, status=status.HTTP_400_BAD_REQUEST)
        demande.jalon = jalon
        demande.save(update_fields=['jalon', 'updated_at'])
        _log(demande, request.user, f'Jalon mis à jour : {demande.get_jalon_display()}')

        demande.refresh_from_db()
        return Response(DemandeChiffrageDetailSerializer(demande, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='montant')
    def set_montant(self, request, pk=None):
        """Saisie du montant brouillon — réplique MontantView (web), invisible du commercial
        tant que la DG n'a pas validé (voir DemandeChiffrageListSerializer.get_montant_ht)."""
        if not (request.user.is_superuser or request.user.role == 'ESTIMATEUR'):
            raise PermissionDenied("Réservé au Service Méthodes.")

        demande = self.get_object()
        if not request.user.is_superuser and demande.assigned_to_id != request.user.id:
            raise PermissionDenied("Cette demande n'est pas affectée à votre compte.")
        montant = str(request.data.get('montant_ht', '')).strip()
        try:
            demande.montant_ht = float(montant.replace(',', '.')) if montant else None
        except ValueError:
            return Response({'detail': 'Montant invalide.'}, status=status.HTTP_400_BAD_REQUEST)
        demande.save(update_fields=['montant_ht', 'updated_at'])

        demande.refresh_from_db()
        return Response(DemandeChiffrageDetailSerializer(demande, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='soumettre-devis',
            parser_classes=[MultiPartParser, FormParser])
    def soumettre_devis(self, request, pk=None):
        """Soumission du devis (2 fichiers) au Responsable Méthodes — réplique
        SoumettreDevisView (web) exactement, y compris la limite de 50 Mo par fichier."""
        if not (request.user.is_superuser or request.user.role == 'ESTIMATEUR'):
            raise PermissionDenied("Réservé au Service Méthodes.")

        demande = self.get_object()
        if not request.user.is_superuser and demande.assigned_to_id != request.user.id:
            raise PermissionDenied("Cette demande n'est pas affectée à votre compte.")
        if demande.statut != DemandeChiffrage.Statut.EN_CHIFFRAGE:
            return Response(
                {'detail': "Cette demande n'est pas (ou plus) en cours de chiffrage."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        fichier_detail = request.FILES.get('fichier_detail')
        fichier_public = request.FILES.get('fichier_public')
        MAX_SIZE = 50 * 1024 * 1024
        if not fichier_detail or not fichier_public:
            return Response(
                {'detail': 'Les deux fichiers (chiffrage détaillé et devis sans détail) sont obligatoires.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if fichier_detail.size > MAX_SIZE or fichier_public.size > MAX_SIZE:
            return Response({'detail': 'Chaque fichier est limité à 50 Mo.'}, status=status.HTTP_400_BAD_REQUEST)

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
        demande.jalon = ''
        demande.rm_rejet_motif = ''
        demande.save()
        _log(demande, request.user, 'Devis soumis au Responsable Méthodes',
             nouveau=demande.statut, ancien=ancien)
        resp_methodes = User.objects.filter(role='RESP_METHODES', is_active_employee=True)
        _notify(
            resp_methodes, f'Devis à approuver — {demande.reference}',
            f'Le devis {demande.reference} ({demande.client_nom}) est prêt pour votre approbation.',
            sender=request.user, demande=demande,
        )

        demande.refresh_from_db()
        return Response(DemandeChiffrageDetailSerializer(demande, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='action-dg')
    def action_dg(self, request, pk=None):
        """Décision de la Direction Générale — réplique exactement ActionDGView (web)."""
        if not (request.user.is_superuser or request.user.role == 'DIRECTEUR'):
            raise PermissionDenied("Réservé à la Direction Générale.")

        demande = self.get_object()
        decision = request.data.get('action')
        motif = (request.data.get('motif') or '').strip()
        ancien = demande.statut

        if decision == 'valider':
            demande.statut = DemandeChiffrage.Statut.DEVIS_VALIDE
            demande.validated_by_dg = request.user
            demande.validated_dg_at = timezone.now()
            demande.save()
            _log(demande, request.user, 'Devis validé par la DG', nouveau=demande.statut, ancien=ancien)
            _notify(
                [demande.commercial], f'Votre devis est prêt — {demande.reference}',
                f'Le devis pour {demande.client_nom} a été validé. Vous pouvez le consulter.',
                sender=request.user, demande=demande,
            )
            try:
                if not hasattr(demande, 'projet'):
                    from apps.projects.models import Project
                    Project.creer_depuis_chiffrage(demande, validated_by=request.user)
            except Exception:
                pass
        elif decision == 'revision':
            if not motif:
                return Response({'detail': 'Un motif est requis.'}, status=status.HTTP_400_BAD_REQUEST)
            demande.statut = DemandeChiffrage.Statut.REVISION_DG
            demande.save()
            _log(demande, request.user, 'Modifications demandées par DG', detail=motif,
                 nouveau=demande.statut, ancien=ancien)
            methodes = User.objects.filter(role='ESTIMATEUR', is_active_employee=True)
            _notify(
                methodes, f'Révision demandée — {demande.reference}',
                f'La DG demande des modifications : {motif}', sender=request.user, demande=demande,
            )
        elif decision == 'refuser':
            if not motif:
                return Response({'detail': 'Un motif de refus est requis.'}, status=status.HTTP_400_BAD_REQUEST)
            demande.statut = DemandeChiffrage.Statut.ARCHIVE
            demande.save()
            _log(demande, request.user, 'Refusé et archivé par DG', detail=motif,
                 nouveau=demande.statut, ancien=ancien)
        else:
            return Response({'detail': 'Action inconnue.'}, status=status.HTTP_400_BAD_REQUEST)

        demande.refresh_from_db()
        return Response(DemandeChiffrageDetailSerializer(demande, context={'request': request}).data)
