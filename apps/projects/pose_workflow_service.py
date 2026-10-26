"""
Service — workflow de pointage par composant (module Gestion de la pose).
RBAC, transitions d'état (BROUILLON → VALIDÉ → PAYÉ) et audit systématique.
Chaque action métier écrit une ligne dans PosePointageAudit (RG-19, RG-22).
"""
from decimal import Decimal, InvalidOperation

from django.db.models import Q, Sum
from django.utils import timezone

ROLES_SUPERVISION_POSE = ('DIRECTEUR', 'DG_POSE', 'ADMIN')


class PointageWorkflowError(Exception):
    """Violation d'une règle de gestion (RG-xx) du workflow de pointage par composant."""
    pass


def _est_supervision(user) -> bool:
    return user.is_superuser or getattr(user, 'role', None) in ROLES_SUPERVISION_POSE


def _notifier_dg_pose(sender, title, message, linked_obj=None):
    """Centralise chez le Responsable de la pose (DG_POSE) toute demande nécessitant sa
    validation — pièce de comptage, demande de modification/dérogation, demande de paiement —
    via la cloche de notifications déjà utilisée dans le reste de l'application."""
    from django.contrib.contenttypes.models import ContentType

    from apps.notifications.models import Notification
    from apps.users.models import User

    destinataires = User.objects.filter(role='DG_POSE', is_active=True)
    content_type = ContentType.objects.get_for_model(linked_obj) if linked_obj else None
    Notification.objects.bulk_create([
        Notification(
            recipient=destinataire, sender=sender,
            notification_type=Notification.Type.APPROVAL_REQUESTED,
            title=title, message=message,
            content_type=content_type, object_id=linked_obj.pk if linked_obj else None,
        )
        for destinataire in destinataires if destinataire.pk != getattr(sender, 'pk', None)
    ])


def _est_delegue(user, project) -> bool:
    from .models_pose import PoseDelegation

    today = timezone.now().date()
    return PoseDelegation.objects.filter(
        project=project, conducteur_delegue=user, actif=True,
    ).filter(
        Q(date_debut__isnull=True) | Q(date_debut__lte=today),
    ).filter(
        Q(date_fin__isnull=True) | Q(date_fin__gte=today),
    ).exists()


def projets_visibles_pointage(user):
    """RG-17 : périmètre visible = projets dont l'utilisateur est chef OU délégué ;
    Directeur/DG_POSE/Admin/superuser voient tous les projets de pose."""
    from .models import Project

    qs = Project.objects.filter(pose_meta__isnull=False)
    if _est_supervision(user):
        return qs
    from .models_pose import PoseDelegation

    today = timezone.now().date()
    delegues_ids = PoseDelegation.objects.filter(
        conducteur_delegue=user, actif=True,
    ).filter(
        Q(date_debut__isnull=True) | Q(date_debut__lte=today),
    ).filter(
        Q(date_fin__isnull=True) | Q(date_fin__gte=today),
    ).values_list('project_id', flat=True)

    return qs.filter(Q(chef_de_projet=user) | Q(pk__in=list(delegues_ids))).distinct()


def peut_saisir(user, project) -> bool:
    """RG-18 : saisie (BROUILLON) par le chef de projet ou un conducteur délégué."""
    if user.is_superuser:
        return True
    role = getattr(user, 'role', None)
    if role == 'CHEF_PROJET_POSE' and project.chef_de_projet_id == user.id:
        return True
    if role == 'CONDUCTEUR_POSE':
        return _est_delegue(user, project)
    return False


def peut_valider(user, fiche) -> bool:
    """RG-18/RG-25 : Chef (de ce projet) ou supervision, jamais le saisisseur de la fiche."""
    if fiche.saisi_par_id == user.id:
        return False
    if _est_supervision(user):
        return True
    if getattr(user, 'role', None) == 'CHEF_PROJET_POSE':
        project = fiche.decomposition.article.project
        return project.chef_de_projet_id == user.id
    return False


def peut_gerer_decomposition(user, project) -> bool:
    """RG-12 : Chef (ses projets), Directeur/DG_POSE/Admin (tous)."""
    if _est_supervision(user):
        return True
    return getattr(user, 'role', None) == 'CHEF_PROJET_POSE' and project.chef_de_projet_id == user.id


def peut_gerer_delegation(user, project) -> bool:
    """RG-16 : le chef de projet délègue ses propres projets ; Directeur/Admin gèrent tous les projets."""
    if _est_supervision(user):
        return True
    return getattr(user, 'role', None) == 'CHEF_PROJET_POSE' and project.chef_de_projet_id == user.id


def peut_marquer_paye(user, project) -> bool:
    """RG-26 : marquer un pointage validé comme payé — Chef (ses projets), Directeur/DG_POSE/Admin (tous)."""
    if _est_supervision(user):
        return True
    return getattr(user, 'role', None) == 'CHEF_PROJET_POSE' and project.chef_de_projet_id == user.id


def peut_approuver_modification(user) -> bool:
    """RG-20 : modification d'un pointage VALIDÉ non payé — réservée à l'Administrateur
    (contrairement à la dérogation sur pointage PAYÉ, RG-21, qui reste ouverte à la
    supervision au sens large)."""
    return bool(user.is_superuser or getattr(user, 'role', None) == 'ADMIN')


def peut_accorder_derogation(user) -> bool:
    """RG-21 : dérogation sur un pointage PAYÉ — Directeur/DG_POSE/Admin, un seul suffit."""
    return _est_supervision(user)


def _valider_quantite(quantite) -> Decimal:
    try:
        quantite = Decimal(str(quantite).replace(',', '.'))
    except InvalidOperation:
        raise PointageWorkflowError('Quantité posée invalide.')
    if quantite < 0:
        raise PointageWorkflowError('La quantité posée ne peut pas être négative (RG-06).')
    return quantite


def _appliquer_quantite(user, decomposition, poseur, quantite):
    """Ajoute un incrément de pointage à une fiche (nouveau pointage progressif). Le nombre
    saisi représente ce qui a été posé depuis la dernière fois — il s'ajoute à la quantité
    déjà validée, il ne la remplace jamais. Une fiche BROUILLON, VALIDÉ ou même déjà PAYÉ (en
    partie ou en totalité) accepte un nouvel incrément, ce qui rouvre un nouveau cycle
    BROUILLON → VALIDÉ : le paiement porte sur ce qui a été payé (quantite_payee), jamais sur
    la totalité de la fiche — poser plus ne doit jamais bloquer, sinon le poseur ne pourrait
    plus travailler après un premier règlement partiel. Seule une fiche verrouillée
    (verrou_modification — dérogation demandée sur une correction rétroactive) est figée.
    `poseur` : None pour une fiche partagée (article à ≤1 poseur), sinon la fiche individuelle
    de ce poseur (article à 2+ poseurs — RG « split par poseur »). Usage interne : ne vérifie
    pas le verrou projet (piece_en_attente) — voir enregistrer_pointages_groupe, seul point
    d'entrée public."""
    from .models_pose import PosePointageAudit, PosePointageComposant

    increment = _valider_quantite(quantite)

    fiche, created = PosePointageComposant.objects.get_or_create(decomposition=decomposition, poseur=poseur)
    if fiche.verrou_modification:
        raise PointageWorkflowError(
            "Cette fiche est verrouillée (dérogation en cours) — passez par une demande de dérogation."
        )

    ancienne_valeur = str(fiche.quantite_posee)
    nouvelle_quantite = fiche.quantite_posee + increment
    fiche.quantite_posee = nouvelle_quantite
    fiche.statut = PosePointageComposant.Statut.BROUILLON
    fiche.saisi_par = user
    fiche.date_saisie = timezone.now()
    fiche.save()

    PosePointageAudit.objects.create(
        fiche=fiche, acteur=user,
        action=PosePointageAudit.Action.CREATION if created else PosePointageAudit.Action.MODIFICATION,
        ancienne_valeur=ancienne_valeur, nouvelle_valeur=str(nouvelle_quantite),
    )
    return fiche


def article_verrouille(article) -> bool:
    """Un article dont au moins un composant est passé PAYÉ est figé : son prix de pose et
    ses poseurs affectés ne peuvent plus être modifiés (seule une dérogation rouvre le
    composant concerné, jamais le prix/poseur de l'article directement)."""
    from .models_pose import PosePointageComposant

    return PosePointageComposant.objects.filter(
        decomposition__article=article, decomposition__actif=True,
        statut=PosePointageComposant.Statut.PAYE,
    ).exists()


def piece_en_attente(project):
    """La pièce de comptage EN_ATTENTE du projet, s'il y en a une — une seule à la fois
    (nouvelle règle : bloque toute nouvelle saisie sur le projet tant qu'elle n'est pas validée)."""
    from .models_pose import PosePieceComptage

    return PosePieceComptage.objects.filter(
        project=project, statut=PosePieceComptage.Statut.EN_ATTENTE,
    ).select_related('saisi_par').prefetch_related(
        'lignes__decomposition__article', 'lignes__medias',
    ).first()


def _parse_cle_saisie(cle):
    """Décode une clé de saisie : 'decomposition_pk' (fiche partagée) ou
    'decomposition_pk:poseur_pk' (fiche individuelle — article à 2+ poseurs).
    Retourne (decomposition_pk: int, poseur_pk: int | None)."""
    cle = str(cle)
    if ':' in cle:
        dpk, ppk = cle.split(':', 1)
        return int(dpk), int(ppk)
    return int(cle), None


def _type_media(fichier):
    """Déduit PHOTO/VIDEO d'un fichier envoyé (content-type puis extension en secours,
    les navigateurs mobiles n'envoyant pas toujours un content-type fiable). None si ni
    l'un ni l'autre n'est reconnu — rejeté par l'appelant."""
    from .models_pose import PosePieceComptageMedia

    content_type = (getattr(fichier, 'content_type', '') or '').lower()
    nom = (getattr(fichier, 'name', '') or '').lower()
    if content_type.startswith('video/') or nom.endswith(('.mp4', '.mov', '.avi', '.webm', '.mkv', '.3gp')):
        return PosePieceComptageMedia.TypeMedia.VIDEO
    if content_type.startswith('image/') or nom.endswith(('.jpg', '.jpeg', '.png', '.heic', '.heif', '.webp', '.gif')):
        return PosePieceComptageMedia.TypeMedia.PHOTO
    return None


def enregistrer_pointages_groupe(user, project, quantites, request=None, medias=None):
    """Point d'entrée unique de la saisie : crée UNE pièce de comptage numérotée regroupant
    toutes les quantités soumises en une fois (« Enregistrer tout »). Un seul lot non validé
    peut exister par projet à la fois (RG nouvelle) — la pièce en cours doit être validée
    avant toute nouvelle saisie sur ce projet, quel que soit l'article/composant visé.
    `quantites` : dict {clé: quantité (str ou Decimal)} — clé = decomposition_pk, ou
    "decomposition_pk:poseur_pk" quand l'article a 2+ poseurs (RG « split par poseur »,
    total toujours partagé : voir pose_service.recap_pose).
    `medias` (optionnel) : dict {clé: [fichiers]} — mêmes clés que `quantites`. Preuve
    photo/vidéo jointe à la ligne de pointage créée pour ce composant ; ignoré pour une clé
    sans quantité saisie (pas de ligne à laquelle les rattacher).
    `request` (optionnel) : sert uniquement à construire un lien absolu dans l'email envoyé
    au chef de projet quand le saisisseur est un coordinateur délégué (voir plus bas) — sans
    lui, le lien reste relatif.
    Retourne la PosePieceComptage créée (avec ses lignes). Tout ou rien (transaction atomique).
    """
    from django.db import transaction

    from .models_pose import (
        PoseArticleDecomposition, PosePieceComptage, PosePieceComptageLigne,
        PosePieceComptageMedia, Poseur,
    )

    if not peut_saisir(user, project):
        raise PointageWorkflowError("Vous n'êtes pas autorisé à saisir un pointage sur ce projet.")

    en_attente = piece_en_attente(project)
    if en_attente is not None:
        raise PointageWorkflowError(
            f"La pièce de comptage {en_attente.numero} de ce projet est en attente de validation "
            "— elle doit être validée avant toute nouvelle saisie."
        )

    a_traiter = {}
    for cle, valeur in quantites.items():
        if str(valeur).strip() == '':
            continue
        a_traiter[_parse_cle_saisie(cle)] = valeur
    if not a_traiter:
        raise PointageWorkflowError('Aucune quantité saisie.')

    decomposition_pks = {dpk for dpk, _ in a_traiter}
    decompositions = {
        d.pk: d for d in PoseArticleDecomposition.objects.filter(
            pk__in=decomposition_pks, article__project=project,
        ).select_related('article').prefetch_related('pointages')
    }
    poseur_pks = {ppk for _, ppk in a_traiter if ppk is not None}
    poseurs = {p.pk: p for p in Poseur.objects.filter(pk__in=poseur_pks)}

    totaux_courants = {}
    erreurs = []
    for (decomposition_pk, poseur_pk), valeur in a_traiter.items():
        decomposition = decompositions.get(decomposition_pk)
        if decomposition is None:
            continue
        increment = _valider_quantite(valeur)
        if decomposition_pk not in totaux_courants:
            totaux_courants[decomposition_pk] = sum(
                (f.quantite_posee for f in decomposition.pointages.all()), Decimal('0'),
            )
        quantite_actuelle = totaux_courants[decomposition_pk]
        if quantite_actuelle + increment > decomposition.article.quantite:
            disponible = decomposition.article.quantite - quantite_actuelle
            erreurs.append(
                f"{decomposition.article.code} — {decomposition.libelle_composant} : "
                f"il reste {disponible} {decomposition.article.unite} à poser sur cet article "
                f"(déjà posé {quantite_actuelle} au total tous poseurs confondus), vous avez saisi {increment}."
            )
        else:
            totaux_courants[decomposition_pk] = quantite_actuelle + increment
    if erreurs:
        raise PointageWorkflowError(
            "Saisie refusée — la quantité posée ne peut pas dépasser la quantité prévue de l'article :\n"
            + "\n".join(erreurs)
        )

    medias_a_traiter = {}
    for cle, fichiers in (medias or {}).items():
        fichiers = [f for f in (fichiers or []) if f]
        if not fichiers:
            continue
        medias_a_traiter[_parse_cle_saisie(cle)] = fichiers
    for fichiers in medias_a_traiter.values():
        for fichier in fichiers:
            if _type_media(fichier) is None:
                raise PointageWorkflowError(
                    f"« {fichier.name} » n'est ni une photo ni une vidéo reconnue."
                )

    with transaction.atomic():
        piece = PosePieceComptage.objects.create(project=project, saisi_par=user)
        for (decomposition_pk, poseur_pk), valeur in a_traiter.items():
            decomposition = decompositions.get(decomposition_pk)
            if decomposition is None:
                continue
            poseur = poseurs.get(poseur_pk) if poseur_pk is not None else None
            _appliquer_quantite(user, decomposition, poseur, valeur)
            ligne = PosePieceComptageLigne.objects.create(
                piece=piece, decomposition=decomposition, poseur=poseur,
                quantite_saisie=_valider_quantite(valeur),
            )
            for fichier in medias_a_traiter.get((decomposition_pk, poseur_pk), []):
                PosePieceComptageMedia.objects.create(
                    ligne=ligne, fichier=fichier, type_media=_type_media(fichier), uploaded_par=user,
                )

    _notifier_dg_pose(
        sender=user,
        title=f'Pièce de comptage {piece.numero} à valider',
        message=f'{project.reference} — {project.name} : nouvelle pièce de comptage soumise par '
                 f'{user.get_full_name() or user.username}, en attente de validation.',
        linked_obj=piece,
    )
    if getattr(user, 'role', None) == 'CONDUCTEUR_POSE':
        _notifier_chef_projet_email(user, project, piece, request)
    return piece


def _notifier_chef_projet_email(coordinateur, project, piece, request=None):
    """Un coordinateur de la pose ne fait qu'exécuter le pointage sur délégation (RG-17) : le
    chef de projet, responsable réel du projet, doit être alerté par email dès qu'une pièce de
    comptage est soumise en son nom, avec un lien direct vers l'écran de validation."""
    import logging

    from django.core.mail import send_mail
    from django.urls import reverse

    chef = project.chef_de_projet
    if not chef or not chef.email:
        return

    chemin = reverse('projects:pose_gestion_pointage_composant', args=[project.pk])
    lien = request.build_absolute_uri(chemin) if request is not None else chemin

    sujet = f'Pointage à valider — {project.reference} — {piece.numero}'
    message = (
        f'Bonjour {chef.first_name or chef.get_full_name() or chef.username},\n\n'
        f'{coordinateur.get_full_name() or coordinateur.username} a soumis la pièce de comptage '
        f'{piece.numero} sur le projet {project.reference} — {project.name}, en attente de votre '
        f'validation.\n\n'
        f'Voir le pointage : {lien}\n\n'
        f'— HOPE, Gestion de la pose (Bois&Co)'
    )
    try:
        send_mail(sujet, message, None, [chef.email], fail_silently=False)
    except Exception:
        logging.getLogger(__name__).warning(
            "Échec de l'envoi de l'email de notification pointage (%s) au chef de projet %s",
            piece.numero, chef.email, exc_info=True,
        )


def enregistrer_quantite(user, decomposition, quantite):
    """Saisie ponctuelle d'un seul composant (fiche partagée) — crée sa propre pièce de
    comptage à une ligne (voir enregistrer_pointages_groupe)."""
    from .models_pose import PosePointageComposant

    project = decomposition.article.project
    enregistrer_pointages_groupe(user, project, {str(decomposition.pk): quantite})
    return PosePointageComposant.objects.get(decomposition=decomposition, poseur=None)


def peut_valider_piece(user, piece) -> bool:
    """RG-25 : le saisisseur de la pièce ne peut jamais la valider lui-même."""
    if piece.saisi_par_id == user.id:
        return False
    if _est_supervision(user):
        return True
    if getattr(user, 'role', None) == 'CHEF_PROJET_POSE':
        return piece.project.chef_de_projet_id == user.id
    return False


def _fiche_de_ligne(ligne):
    """Résout la fiche (PosePointageComposant) exacte visée par une ligne de pièce de
    comptage — identifiée par (decomposition, poseur), poseur pouvant être None (fiche
    partagée)."""
    from .models_pose import PosePointageComposant

    return PosePointageComposant.objects.filter(
        decomposition_id=ligne.decomposition_id, poseur_id=ligne.poseur_id,
    ).first()


def valider_piece(user, piece):
    """Valide une pièce de comptage : toutes ses lignes (fiches encore BROUILLON) passent à
    VALIDÉ, et le projet est débloqué pour une nouvelle saisie."""
    from django.db import transaction

    from .models_pose import PosePieceComptage

    if piece.statut != PosePieceComptage.Statut.EN_ATTENTE:
        raise PointageWorkflowError(f"Cette pièce est déjà « {piece.get_statut_display()} ».")
    if not peut_valider_piece(user, piece):
        raise PointageWorkflowError(
            "Vous n'êtes pas autorisé à valider cette pièce, ou vous en êtes le saisisseur (RG-25)."
        )

    with transaction.atomic():
        for ligne in piece.lignes.select_related('decomposition'):
            fiche = _fiche_de_ligne(ligne)
            if fiche is not None and fiche.statut == fiche.Statut.BROUILLON:
                valider_pointage(user, fiche)

        piece.statut = PosePieceComptage.Statut.VALIDE
        piece.valide_par = user
        piece.date_validation = timezone.now()
        piece.save()
    return piece


def refuser_piece(user, piece, type_refus, motif_categorie='', motif=''):
    """Rejet définitif ou demande de révision d'une pièce de comptage (RG-25 : jamais par son
    saisisseur). Dans les deux cas, les incréments de quantité qu'elle portait sont annulés —
    chaque fiche concernée revient à sa quantité précédemment validée (BROUILLON si elle
    n'avait encore jamais été validée) — et le projet est débloqué immédiatement pour une
    nouvelle saisie. La pièce reste visible, marquée « Refusée », avec son motif, pour
    traçabilité."""
    from django.db import transaction

    from .models_pose import PosePieceComptage, PosePointageAudit, PosePointageComposant

    if piece.statut != PosePieceComptage.Statut.EN_ATTENTE:
        raise PointageWorkflowError(f"Cette pièce est déjà « {piece.get_statut_display()} ».")
    if not peut_valider_piece(user, piece):
        raise PointageWorkflowError(
            "Vous n'êtes pas autorisé à traiter cette pièce, ou vous en êtes le saisisseur (RG-25)."
        )
    if type_refus not in (PosePieceComptage.TypeRefus.REJET, PosePieceComptage.TypeRefus.REVISION):
        raise PointageWorkflowError('Type de refus invalide.')
    if type_refus == PosePieceComptage.TypeRefus.REVISION and not motif_categorie:
        raise PointageWorkflowError('Un motif est obligatoire pour une demande de révision.')

    with transaction.atomic():
        for ligne in piece.lignes.select_related('decomposition'):
            fiche = _fiche_de_ligne(ligne)
            if fiche is None:
                continue
            ancienne_valeur = str(fiche.quantite_posee)
            nouvelle_quantite = fiche.quantite_posee - ligne.quantite_saisie
            if nouvelle_quantite < 0:
                nouvelle_quantite = Decimal('0')
            fiche.quantite_posee = nouvelle_quantite
            fiche.statut = (
                PosePointageComposant.Statut.VALIDE if nouvelle_quantite > 0
                else PosePointageComposant.Statut.BROUILLON
            )
            fiche.save()
            PosePointageAudit.objects.create(
                fiche=fiche, acteur=user, action=PosePointageAudit.Action.ANNULATION,
                ancienne_valeur=ancienne_valeur, nouvelle_valeur=str(nouvelle_quantite),
                motif=motif or dict(PosePieceComptage.MotifRevision.choices).get(motif_categorie, ''),
            )

        piece.statut = PosePieceComptage.Statut.REFUSEE
        piece.type_refus = type_refus
        piece.motif_categorie = motif_categorie
        piece.motif_refus = motif
        piece.refuse_par = user
        piece.date_refus = timezone.now()
        piece.save()
    return piece


def valider_pointage(user, fiche):
    """RG-18/RG-25 : BROUILLON → VALIDÉ."""
    from .models_pose import PosePointageAudit, PosePointageComposant

    if fiche.statut != PosePointageComposant.Statut.BROUILLON:
        raise PointageWorkflowError(f"Cette fiche est déjà « {fiche.get_statut_display()} ».")
    if not peut_valider(user, fiche):
        raise PointageWorkflowError(
            "Vous n'êtes pas autorisé à valider cette fiche, ou vous en êtes le saisisseur (RG-25)."
        )

    fiche.statut = PosePointageComposant.Statut.VALIDE
    fiche.valide_par = user
    fiche.date_validation = timezone.now()
    fiche.save()

    PosePointageAudit.objects.create(
        fiche=fiche, acteur=user, action=PosePointageAudit.Action.VALIDATION,
        ancienne_valeur='BROUILLON', nouvelle_valeur='VALIDE',
    )
    return fiche


def _appliquer_paiement(user, fiche, montant_regle):
    """Mutation bas niveau, sans contrôle RBAC (fait par l'appelant) : incrémente
    quantite_payee du montant réglé et bascule la fiche en PAYÉ si le solde tombe à zéro.
    Utilisé à la fois par `marquer_paye` (règlement direct par un chef/superviseur) et par
    `creer_recu_paiement` (règlement matérialisé par un reçu de Trésorerie)."""
    from .models_pose import PosePointageAudit, PosePointageComposant

    solde_impaye = fiche.quantite_posee - fiche.quantite_payee
    if montant_regle > solde_impaye:
        raise PointageWorkflowError(
            f"Ce pointage ne peut pas être payé pour plus que son solde impayé ({solde_impaye})."
        )

    ancienne_valeur = str(fiche.quantite_payee)
    fiche.quantite_payee = fiche.quantite_payee + montant_regle
    fiche.paye = True
    if fiche.quantite_payee >= fiche.quantite_posee:
        fiche.statut = PosePointageComposant.Statut.PAYE
    fiche.save(update_fields=['quantite_payee', 'paye', 'statut', 'updated_at'])

    PosePointageAudit.objects.create(
        fiche=fiche, acteur=user, action=PosePointageAudit.Action.PAIEMENT,
        ancienne_valeur=ancienne_valeur, nouvelle_valeur=str(fiche.quantite_payee),
        motif=f'Réglé : {montant_regle}',
    )
    return fiche


def marquer_paye(user, fiche, quantite=None):
    """RG-26 : marque tout ou partie d'un pointage comme payé — le poseur a été réglé sur cette
    quantité. `quantite` : delta réglé par ce paiement (par défaut, tout ce qui reste non
    payé). Le règlement s'ajoute à quantite_payee, il ne fige jamais la fiche : poser davantage
    ensuite reste possible (voir _appliquer_quantite) — seul le solde impayé change, jamais le
    montant déjà réglé. Le statut de la fiche n'est pas vérifié ici : le solde impayé
    (quantite_posee - quantite_payee) peut légitimement rester à régler même si la fiche a
    depuis évolué (nouveau brouillon en cours sur un incrément plus récent, par exemple) — la
    seule vraie protection est de ne jamais régler plus que ce solde. Le statut ne passe à
    PAYÉ que lorsque tout ce qui est posé a été réglé ; sinon il reste inchangé, avec un reste
    à payer."""
    project = fiche.decomposition.article.project
    if not peut_marquer_paye(user, project):
        raise PointageWorkflowError("Vous n'êtes pas autorisé à marquer ce pointage comme payé.")

    solde_impaye = fiche.quantite_posee - fiche.quantite_payee
    montant_regle = _valider_quantite(quantite) if quantite is not None else solde_impaye
    return _appliquer_paiement(user, fiche, montant_regle)


def demander_modification(user, fiche, motif, nouvelle_quantite=None):
    """RG-20/RG-21 : demande de modification d'une fiche VALIDÉ (→ Directeur) ou PAYÉ (→ dérogation DG/Admin)."""
    from .models_pose import PoseDemandeModification, PosePointageAudit, PosePointageComposant

    project = fiche.decomposition.article.project
    if not projets_visibles_pointage(user).filter(pk=project.pk).exists():
        raise PointageWorkflowError("Vous n'avez pas accès à ce projet.")
    if not motif or not motif.strip():
        raise PointageWorkflowError('Le motif est obligatoire.')
    if fiche.demandes_modification.filter(statut=PoseDemandeModification.Statut.EN_ATTENTE).exists():
        raise PointageWorkflowError('Une demande est déjà en attente pour cette fiche.')

    if fiche.paye or fiche.statut == PosePointageComposant.Statut.PAYE:
        type_demande = PoseDemandeModification.TypeDemande.DEROGATION_DG
    elif fiche.statut == PosePointageComposant.Statut.VALIDE:
        type_demande = PoseDemandeModification.TypeDemande.VALIDATION_DIRECTEUR
    else:
        raise PointageWorkflowError('Une fiche en brouillon se modifie directement, sans demande.')

    demande = PoseDemandeModification.objects.create(
        fiche=fiche, type_demande=type_demande, demandeur=user,
        motif=motif.strip(), nouvelle_quantite=nouvelle_quantite,
    )

    if type_demande == PoseDemandeModification.TypeDemande.DEROGATION_DG:
        fiche.verrou_modification = True
        fiche.save(update_fields=['verrou_modification', 'updated_at'])
        action = PosePointageAudit.Action.DEMANDE_DEROGATION
    else:
        action = PosePointageAudit.Action.DEMANDE_MODIFICATION

    PosePointageAudit.objects.create(fiche=fiche, acteur=user, action=action, motif=motif.strip())

    _notifier_dg_pose(
        sender=user,
        title=(
            'Demande de dérogation à traiter' if type_demande == PoseDemandeModification.TypeDemande.DEROGATION_DG
            else 'Demande de modification à traiter'
        ),
        message=f'{project.reference} — {fiche.decomposition.article.code} : '
                 f'{fiche.decomposition.libelle_composant} — motif : {motif.strip()}',
        linked_obj=demande,
    )
    return demande


def approuver_modification(user, demande):
    """RG-20 : l'Administrateur approuve la réouverture d'une fiche VALIDÉ non payée."""
    from .models_pose import PoseDemandeModification, PosePointageAudit, PosePointageComposant

    if demande.type_demande != PoseDemandeModification.TypeDemande.VALIDATION_DIRECTEUR:
        raise PointageWorkflowError("Cette demande n'est pas une modification post-validation.")
    if demande.statut != PoseDemandeModification.Statut.EN_ATTENTE:
        raise PointageWorkflowError(f"Cette demande est déjà « {demande.get_statut_display()} ».")
    if not peut_approuver_modification(user):
        raise PointageWorkflowError("Seul l'Administrateur peut approuver cette demande.")

    demande.statut = PoseDemandeModification.Statut.APPROUVE
    demande.approbateur = user
    demande.date_traitement = timezone.now()
    demande.save()

    fiche = demande.fiche
    ancienne_valeur = fiche.statut
    fiche.statut = PosePointageComposant.Statut.BROUILLON
    fiche.save(update_fields=['statut', 'updated_at'])

    PosePointageAudit.objects.create(
        fiche=fiche, acteur=user, action=PosePointageAudit.Action.APPROBATION_MODIFICATION,
        ancienne_valeur=ancienne_valeur, nouvelle_valeur=PosePointageComposant.Statut.BROUILLON,
        motif=demande.motif,
    )
    return demande


def accorder_derogation(user, demande):
    """RG-21 : la DG ou l'Administrateur (un seul suffit) accorde la dérogation sur une fiche PAYÉ."""
    from .models_pose import PoseDemandeModification, PosePointageAudit, PosePointageComposant

    if demande.type_demande != PoseDemandeModification.TypeDemande.DEROGATION_DG:
        raise PointageWorkflowError("Cette demande n'est pas une dérogation de paiement.")
    if demande.statut != PoseDemandeModification.Statut.EN_ATTENTE:
        raise PointageWorkflowError(f"Cette demande est déjà « {demande.get_statut_display()} ».")
    if not peut_accorder_derogation(user):
        raise PointageWorkflowError('Seuls Directeur/DG/Admin peuvent accorder une dérogation.')

    demande.statut = PoseDemandeModification.Statut.APPROUVE
    demande.approbateur = user
    demande.date_traitement = timezone.now()
    demande.save()

    fiche = demande.fiche
    fiche.verrou_modification = False
    fiche.statut = PosePointageComposant.Statut.BROUILLON
    fiche.save(update_fields=['verrou_modification', 'statut', 'updated_at'])

    PosePointageAudit.objects.create(
        fiche=fiche, acteur=user, action=PosePointageAudit.Action.DEROGATION_ACCORDEE,
        ancienne_valeur='PAYE', nouvelle_valeur='BROUILLON', motif=demande.motif,
    )
    return demande


def refuser_demande(user, demande, motif_refus=''):
    """Refus d'une demande de modification ou de dérogation (complète le circuit à côté
    d'approuver_modification/accorder_derogation, non listé explicitement mais nécessaire
    pour que la file d'attente soit utilisable : sans refus, une demande rejetée resterait
    bloquée indéfiniment EN_ATTENTE)."""
    from .models_pose import PoseDemandeModification, PosePointageAudit

    if demande.statut != PoseDemandeModification.Statut.EN_ATTENTE:
        raise PointageWorkflowError(f"Cette demande est déjà « {demande.get_statut_display()} ».")

    if demande.type_demande == PoseDemandeModification.TypeDemande.VALIDATION_DIRECTEUR:
        if not peut_approuver_modification(user):
            raise PointageWorkflowError("Seul l'Administrateur peut traiter cette demande.")
    else:
        if not peut_accorder_derogation(user):
            raise PointageWorkflowError('Seuls Directeur/DG/Admin peuvent traiter cette demande.')

    demande.statut = PoseDemandeModification.Statut.REFUSE
    demande.approbateur = user
    demande.date_traitement = timezone.now()
    demande.save()

    fiche = demande.fiche
    if demande.type_demande == PoseDemandeModification.TypeDemande.DEROGATION_DG:
        fiche.verrou_modification = False
        fiche.save(update_fields=['verrou_modification', 'updated_at'])

    PosePointageAudit.objects.create(
        fiche=fiche, acteur=user, action=PosePointageAudit.Action.REFUS_MODIFICATION,
        motif=motif_refus or '',
    )
    return demande


def deleguer_projet(user, project, conducteur, date_debut=None, date_fin=None):
    """RG-16 : le chef de projet (ou la supervision) délègue la saisie à un conducteur de travaux.
    Non listée explicitement dans les signatures du plan mais nécessaire pour exploiter PoseDelegation."""
    from .models_pose import PoseDelegation

    if not peut_gerer_delegation(user, project):
        raise PointageWorkflowError('Vous ne pouvez pas déléguer ce projet.')
    if getattr(conducteur, 'role', None) != 'CONDUCTEUR_POSE':
        raise PointageWorkflowError("L'utilisateur choisi n'a pas le rôle Conducteur de travaux.")

    delegation, _ = PoseDelegation.objects.update_or_create(
        project=project, conducteur_delegue=conducteur,
        defaults={
            'chef_delegant': user, 'actif': True,
            'date_debut': date_debut, 'date_fin': date_fin,
        },
    )
    return delegation


def revoquer_delegation(user, delegation):
    if not peut_gerer_delegation(user, delegation.project):
        raise PointageWorkflowError('Vous ne pouvez pas gérer cette délégation.')
    delegation.actif = False
    delegation.save(update_fields=['actif'])
    return delegation


def peut_creer_demande_paiement(user) -> bool:
    """Création d'une demande de paiement globale (tous projets d'un poseur) — réservée à la
    supervision pose (DG_POSE/Directeur/Admin), seule à avoir la visibilité sur l'ensemble des
    projets, potentiellement gérés par des chefs de projet différents."""
    return _est_supervision(user)


def peut_valider_demande_paiement(user, demande) -> bool:
    """RG-25/RG nouvelle : jamais le demandeur. Le Responsable de la pose (DG_POSE) ne fait
    qu'effectuer/soumettre la demande — il ne la valide jamais, y compris celle d'un pair
    DG_POSE : seule la Direction Générale (DIRECTEUR) valide."""
    if demande.demandeur_id == user.id:
        return False
    return bool(user.is_superuser or getattr(user, 'role', None) == 'DIRECTEUR')


def peut_gerer_brouillon_demande(user, demande) -> bool:
    """Ajout/retrait de lignes, soumission — uniquement tant que la demande est « En cours »,
    et seulement par la supervision (même droit que la création)."""
    from .models_pose import PoseDemandePaiement

    return demande.statut == PoseDemandePaiement.Statut.BROUILLON and peut_creer_demande_paiement(user)


def fiches_engagees_ids():
    """Fiches déjà incluses dans une demande de paiement active (en cours, soumise, ou validée
    mais pas encore réglée par un reçu de Trésorerie) — à exclure des listes de sélection pour
    ne jamais engager deux fois le même pointage."""
    from .models_pose import PoseDemandePaiement, PoseDemandePaiementLigne

    return set(
        PoseDemandePaiementLigne.objects.filter(
            Q(demande__statut__in=(PoseDemandePaiement.Statut.BROUILLON, PoseDemandePaiement.Statut.EN_ATTENTE))
            | Q(demande__statut=PoseDemandePaiement.Statut.VALIDEE, recu__isnull=True)
        ).values_list('fiche_id', flat=True)
    )


def obtenir_ou_creer_brouillon(user):
    """Reprend le brouillon (« En cours ») le plus récent de cet utilisateur, ou en crée un
    nouveau — une demande de paiement se construit progressivement avant d'être soumise."""
    from .models_pose import PoseDemandePaiement

    if not peut_creer_demande_paiement(user):
        raise PointageWorkflowError("Vous n'êtes pas autorisé à créer une demande de paiement.")

    brouillon = PoseDemandePaiement.objects.filter(
        demandeur=user, statut=PoseDemandePaiement.Statut.BROUILLON,
    ).order_by('-date_creation').first()
    if brouillon is not None:
        return brouillon
    return PoseDemandePaiement.objects.create(demandeur=user)


def ajouter_lignes_demande(user, demande, poseur, fiche_ids):
    """Ajoute à une demande « En cours » une sélection de pointages validés-non-payés d'UN
    poseur (tous projets confondus). Une demande peut ainsi regrouper plusieurs poseurs, en
    répétant l'opération. Une fiche déjà engagée ailleurs (autre brouillon ou demande soumise)
    ne peut pas être ajoutée deux fois."""
    from django.db import transaction

    from .models_pose import PoseDemandePaiementLigne
    from .pose_service import releve_global_poseur

    if not peut_gerer_brouillon_demande(user, demande):
        raise PointageWorkflowError("Cette demande n'est plus modifiable (déjà soumise/traitée).")
    if not fiche_ids:
        raise PointageWorkflowError('Sélectionnez au moins une ligne à ajouter.')
    fiche_ids = {int(pk) for pk in fiche_ids}

    deja_engagees = fiches_engagees_ids()
    releve = releve_global_poseur(poseur, exclure_fiche_ids=deja_engagees)
    lignes_selectionnees = [ligne for ligne in releve['a_payer'] if ligne['fiche'].pk in fiche_ids]
    if not lignes_selectionnees:
        raise PointageWorkflowError(
            'Aucune des lignes sélectionnées n\'est disponible (déjà payée ou déjà engagée dans une autre demande).'
        )

    with transaction.atomic():
        PoseDemandePaiementLigne.objects.bulk_create([
            PoseDemandePaiementLigne(
                demande=demande, fiche=ligne['fiche'], poseur=poseur,
                quantite=ligne['quantite'], montant=ligne['montant'],
            )
            for ligne in lignes_selectionnees
        ])
        demande.montant_total = demande.lignes.aggregate(total=Sum('montant'))['total'] or Decimal('0')
        demande.save(update_fields=['montant_total'])
    return demande


def retirer_ligne_demande(user, demande, ligne_pk):
    """Retire une ligne d'une demande « En cours »."""
    if not peut_gerer_brouillon_demande(user, demande):
        raise PointageWorkflowError("Cette demande n'est plus modifiable (déjà soumise/traitée).")

    ligne = demande.lignes.filter(pk=ligne_pk).first()
    if ligne is None:
        raise PointageWorkflowError('Ligne introuvable sur cette demande.')

    ligne.delete()
    demande.montant_total = demande.lignes.aggregate(total=Sum('montant'))['total'] or Decimal('0')
    demande.save(update_fields=['montant_total'])
    return demande


def soumettre_demande_paiement(user, demande):
    """Fait passer une demande « En cours » → « Soumise à la validation » : elle devient
    visible dans la file de la DG et n'est plus modifiable."""
    from .models_pose import PoseDemandePaiement

    if demande.statut != PoseDemandePaiement.Statut.BROUILLON:
        raise PointageWorkflowError(f"Cette demande est déjà « {demande.get_statut_display()} ».")
    if not peut_creer_demande_paiement(user):
        raise PointageWorkflowError("Vous n'êtes pas autorisé à soumettre cette demande.")
    if not demande.lignes.exists():
        raise PointageWorkflowError('Ajoutez au moins une ligne avant de soumettre la demande.')

    demande.statut = PoseDemandePaiement.Statut.EN_ATTENTE
    demande.date_soumission = timezone.now()
    demande.save(update_fields=['statut', 'date_soumission'])

    _notifier_dg_pose(
        sender=user,
        title=f'Demande de paiement {demande.numero} à valider',
        message=f'{demande.montant_total} MAD soumis par {user.get_full_name() or user.username}.',
        linked_obj=demande,
    )
    return demande


def valider_demande_paiement(user, demande):
    """La DG approuve la demande (RG-26) : ceci autorise le règlement, mais ne le déclenche
    plus automatiquement — le paiement effectif des poseurs est un processus distinct, propre
    à la Trésorerie, matérialisé par un reçu de paiement (voir `creer_recu_paiement`). Tant
    qu'aucun reçu n'a été émis pour ses lignes, une demande Validée reste « non payée »."""
    from .models_pose import PoseDemandePaiement

    if demande.statut != PoseDemandePaiement.Statut.EN_ATTENTE:
        raise PointageWorkflowError(f"Cette demande est déjà « {demande.get_statut_display()} ».")
    if not peut_valider_demande_paiement(user, demande):
        raise PointageWorkflowError(
            "Vous n'êtes pas autorisé à valider cette demande, ou vous en êtes le demandeur (RG-25)."
        )

    demande.statut = PoseDemandePaiement.Statut.VALIDEE
    demande.valide_par = user
    demande.date_validation = timezone.now()
    demande.save()
    return demande


def refuser_demande_paiement(user, demande, motif=''):
    """Refus d'une demande de paiement — les pointages liés restent VALIDÉ (non payés),
    disponibles pour une future demande."""
    from .models_pose import PoseDemandePaiement

    if demande.statut != PoseDemandePaiement.Statut.EN_ATTENTE:
        raise PointageWorkflowError(f"Cette demande est déjà « {demande.get_statut_display()} ».")
    if not peut_valider_demande_paiement(user, demande):
        raise PointageWorkflowError(
            "Vous n'êtes pas autorisé à traiter cette demande, ou vous en êtes le demandeur (RG-25)."
        )

    demande.statut = PoseDemandePaiement.Statut.REFUSEE
    demande.valide_par = user
    demande.date_validation = timezone.now()
    demande.motif_refus = motif
    demande.save()
    return demande


# ── Reçus de paiement (règlement effectif — Trésorerie) ──────────────────────────────────

def peut_gerer_tresorerie_pose(user) -> bool:
    """Émission des reçus de paiement — matérialisation du règlement effectif des poseurs :
    réservée au Financier (rôle FINANCE), seul habilité à éditer un reçu de paiement.
    Ni la Trésorerie Pose, ni le Responsable de la pose, ni la Direction Générale n'émettent
    eux-mêmes de reçu — une fois la demande validée par la DG, le dossier bascule entièrement
    côté Finance."""
    return bool(user.is_superuser or getattr(user, 'role', None) == 'FINANCE')


def lignes_validees_non_payees(poseur=None):
    """Lignes de demandes Validées dont le règlement effectif n'a pas encore été matérialisé
    par un reçu de Trésorerie — le vivier dans lequel un reçu de paiement est composé."""
    from .models_pose import PoseDemandePaiement, PoseDemandePaiementLigne

    qs = PoseDemandePaiementLigne.objects.filter(
        demande__statut=PoseDemandePaiement.Statut.VALIDEE, recu__isnull=True,
    ).select_related('poseur', 'demande', 'fiche__decomposition__article__project')
    if poseur is not None:
        qs = qs.filter(poseur=poseur)
    return qs.order_by('poseur__nom', 'demande__date_creation')


def creer_recu_paiement(user, ligne_ids, date_recu=None, remis_par=None):
    """Émet un reçu de paiement Trésorerie pour la sélection de lignes fournie (une ou
    plusieurs demandes Validées, un ou plusieurs poseurs). C'est cette étape — et elle seule —
    qui règle effectivement les pointages liés (RG-26) : chaque fiche est réglée pour
    exactement le delta que portait sa ligne, plafonné à son solde impayé courant."""
    from django.db import transaction

    from .models_pose import PoseDemandePaiement, PoseRecuPaiement

    if not peut_gerer_tresorerie_pose(user):
        raise PointageWorkflowError("Vous n'êtes pas autorisé à émettre un reçu de paiement.")
    if not ligne_ids:
        raise PointageWorkflowError('Sélectionnez au moins une ligne à régler.')
    ligne_ids = {int(pk) for pk in ligne_ids}

    lignes = list(
        lignes_validees_non_payees().filter(pk__in=ligne_ids).select_related('fiche')
    )
    if not lignes:
        raise PointageWorkflowError(
            "Aucune des lignes sélectionnées n'est disponible (déjà réglée, ou demande non validée)."
        )

    with transaction.atomic():
        recu = PoseRecuPaiement.objects.create(
            date_recu=date_recu or timezone.localdate(),
            cree_par=user, remis_par=remis_par or user,
        )
        total = Decimal('0')
        for ligne in lignes:
            fiche = ligne.fiche
            solde_impaye = fiche.quantite_posee - fiche.quantite_payee
            montant_a_regler = min(ligne.quantite, solde_impaye)
            if montant_a_regler > 0:
                _appliquer_paiement(user, fiche, montant_a_regler)
            ligne.recu = recu
            ligne.save(update_fields=['recu'])
            total += ligne.montant
        recu.montant_total = total
        recu.save(update_fields=['montant_total'])
    return recu
