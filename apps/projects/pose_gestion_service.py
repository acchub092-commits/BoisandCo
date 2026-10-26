"""
Service — module Gestion de la pose (CDC Nisrine ALAMI, v1.0, 20/07/2026).
RBAC + import bordereau .xlsx. Formules et règles de gestion (RG-xx) viendront
au fil des étapes suivantes du workflow, ajoutées ici au même endroit.
"""
import re
from decimal import Decimal, InvalidOperation

import openpyxl

ROLES_CREATION_PROJET_POSE = ('DIRECTEUR', 'MANAGER', 'ADMIN', 'DG_POSE')


def peut_creer_projet_pose(user) -> bool:
    """Création/suppression d'un nouveau projet de pose : DG, DC ou superuser (ADMIN).

    Ne pas utiliser pour la simple création (voir peut_initier_projet_pose) : ce contrôle,
    plus large, autorise aussi la suppression de N'IMPORTE QUEL projet de pose.
    """
    if user.is_superuser:
        return True
    return getattr(user, 'role', None) in ROLES_CREATION_PROJET_POSE


def peut_initier_projet_pose(user) -> bool:
    """Création d'un projet de pose : DG/DC/Admin, ou un chef de projet pose créant son propre projet."""
    if peut_creer_projet_pose(user):
        return True
    return getattr(user, 'role', None) == 'CHEF_PROJET_POSE'


def peut_gerer_projet_pose(user, project) -> bool:
    """Accès complet à la gestion pose d'un projet donné : DG, DC, ou chef de projet du projet (RG-08/RG-09)."""
    if user.is_superuser:
        return True
    if getattr(user, 'role', None) in ROLES_CREATION_PROJET_POSE:
        return True
    return project.chef_de_projet_id == user.id


def peut_valider_prix_pose(user) -> bool:
    """Validation des prix de pose et des bons de règlement : DG, Administrateur, ou DG Pose (superuser inclus)."""
    if user.is_superuser:
        return True
    return getattr(user, 'role', None) in ('DIRECTEUR', 'ADMIN', 'DG_POSE')


def peut_editer_bon_reglement(user) -> bool:
    """Édition/impression d'un bon de règlement validé : DG, Admin, Finance, ou Trésorerie Pose (superuser inclus)."""
    if user.is_superuser:
        return True
    return getattr(user, 'role', None) in ('DIRECTEUR', 'ADMIN', 'FINANCE', 'TRESO_POSE')


def peut_gerer_referentiel_poseurs(user) -> bool:
    """Création/édition du référentiel Poseur : DG, DC, ou tout chef de projet en cours (au moins un projet)."""
    if user.is_superuser:
        return True
    if getattr(user, 'role', None) in ROLES_CREATION_PROJET_POSE:
        return True
    from .models import Project
    return Project.objects.filter(chef_de_projet_id=user.id).exists()


def definir_prix_de_pose(article, prix, frais_logistique=None) -> None:
    """RG-02 : toute saisie/modification du prix de pose remet l'article en attente de validation DG.
    `frais_logistique` (optionnel) : coût logistique unitaire saisi en même temps, ajouté au budget
    engagé de la pose (jamais au règlement du poseur)."""
    article.prix_de_pose = prix
    article.frais_logistique_pose = frais_logistique
    article.statut_validation = article.StatutValidation.EN_ATTENTE
    article.motif_refus = ''
    article.save(update_fields=[
        'prix_de_pose', 'frais_logistique_pose', 'statut_validation', 'motif_refus', 'updated_at',
    ])


class PointageError(Exception):
    """Violation d'une règle de gestion (RG-xx) lors de la création/mise à jour d'un lot."""
    pass


def reviser_prix_de_pose(article, nouveau_prix, user):
    """DG révise le prix de pose au lieu de refuser : le nouveau prix est directement validé (pointable)."""
    try:
        nouveau_prix = Decimal(str(nouveau_prix).replace(',', '.'))
    except InvalidOperation:
        raise PointageError('Prix révisé invalide.')
    if nouveau_prix <= 0:
        raise PointageError('Le prix révisé doit être positif.')

    article.prix_de_pose = nouveau_prix
    article.statut_validation = article.StatutValidation.VALIDE
    article.motif_refus = ''
    article.save(update_fields=['prix_de_pose', 'statut_validation', 'motif_refus', 'updated_at'])
    return article


def _valider_avancement(pourcentage) -> int:
    try:
        pourcentage = int(pourcentage)
    except (TypeError, ValueError):
        raise PointageError("L'avancement doit être un nombre entier.")
    if pourcentage <= 0 or pourcentage > 100 or pourcentage % 10 != 0:
        raise PointageError("L'avancement doit être un multiple de 10, compris entre 10 et 100.")
    return pourcentage


def creer_lot(article, poseur, quantite, pourcentage_initial, date, user):
    """Étape 4 — création d'un nouveau lot pour un couple article/poseur affecté."""
    from .models_pose import Affectation, Lot

    if article.statut_validation != article.StatutValidation.VALIDE:
        raise PointageError(  # RG-01
            "Le prix de pose de cet article n'a pas encore été validé par le DG."
        )
    if not Affectation.objects.filter(article=article, poseur=poseur).exists():
        raise PointageError('Ce poseur n\'est pas affecté à cet article.')

    try:
        quantite = Decimal(str(quantite).replace(',', '.'))
    except InvalidOperation:
        raise PointageError('Quantité de lot invalide.')
    if quantite <= 0:
        raise PointageError('La quantité du lot doit être positive.')
    if quantite > article.quantite_disponible:
        raise PointageError(  # contrôle bloquant du dépassement de quantité prévue
            f'Quantité demandée ({quantite}) supérieure à la quantité encore disponible '
            f'sur cet article ({article.quantite_disponible}).'
        )

    pourcentage_initial = _valider_avancement(pourcentage_initial)

    lot = Lot.objects.create(article=article, poseur=poseur, quantite=quantite, pourcentage=0, created_by=user)
    enregistrer_pointage(lot, pourcentage_initial, date, user)
    return lot


def enregistrer_pointage(lot, nouveau_pourcentage, date, user):
    """Étape 4 — mise à jour (pointage) d'un lot existant. RG-04 à RG-07."""
    from .models_pose import Pointage

    article = lot.article
    if article.statut_validation != article.StatutValidation.VALIDE:
        raise PointageError("Le prix de pose de cet article n'a pas encore été validé par le DG.")  # RG-01
    if lot.is_cloture:
        raise PointageError('Ce lot est déjà clôturé à 100 %.')

    nouveau_pourcentage = _valider_avancement(nouveau_pourcentage)
    if nouveau_pourcentage <= lot.pourcentage:
        raise PointageError(  # RG-04 : % croissant uniquement
            f"L'avancement ne peut que progresser (actuellement {lot.pourcentage} %)."
        )

    prix = article.prix_de_pose or Decimal('0')
    delta_pct = nouveau_pourcentage - lot.pourcentage
    quantite_effective = (lot.quantite * delta_pct / 100).quantize(Decimal('0.01'))
    montant = (quantite_effective * prix).quantize(Decimal('0.01'))

    if article.quantite_terminee + quantite_effective > article.quantite:
        raise PointageError('Ce pointage dépasserait la quantité prévue de l\'article (RG-06).')

    plafond_lot = (lot.quantite * prix).quantize(Decimal('0.01'))
    if lot.montant_verse + montant > plafond_lot:
        raise PointageError('Ce pointage dépasserait le montant maximum autorisé pour ce lot (RG-07).')

    iso = date.isocalendar()
    pointage = Pointage.objects.create(
        lot=lot, article=article, poseur=lot.poseur, project=article.project,
        date=date, semaine=iso[1], annee=iso[0],
        quantite=lot.quantite, pourcentage=nouveau_pourcentage,
        quantite_effective=quantite_effective, montant=montant,
        created_by=user,
    )
    lot.pourcentage = nouveau_pourcentage
    lot.save(update_fields=['pourcentage', 'updated_at'])
    return pointage


def lignes_reglement_semaine(project, semaine, annee):
    """Étape 5 — une ligne par poseur ayant pointé cette semaine : dû, versé, reste, statut.

    « versé » compte tout versement espèce non rejeté (RG-04..RG-10), que la Trésorerie
    l'ait déjà confirmé ou non — la confirmation Trésorerie (RG-15) n'intervient qu'après
    validation DG du bon et n'affecte jamais le dû/versé/reste ; voir verse_confirme_tresorerie.
    """
    from django.db.models import Sum

    from .models_pose import BonReglement, Paiement, Pointage, Poseur

    poseur_ids = Pointage.objects.filter(
        project=project, semaine=semaine, annee=annee,
    ).values_list('poseur_id', flat=True).distinct()

    lignes = []
    for poseur in Poseur.objects.filter(pk__in=poseur_ids).order_by('nom'):
        du = Pointage.objects.filter(
            project=project, poseur=poseur, semaine=semaine, annee=annee,
        ).aggregate(total=Sum('montant'))['total'] or Decimal('0')
        verse = Paiement.objects.filter(
            project=project, poseur=poseur, semaine=semaine, annee=annee,
        ).exclude(statut=Paiement.Statut.REJETE).aggregate(total=Sum('montant_verse'))['total'] or Decimal('0')
        verse_confirme_tresorerie = Paiement.objects.filter(
            project=project, poseur=poseur, semaine=semaine, annee=annee, statut=Paiement.Statut.APPROUVE,
        ).aggregate(total=Sum('montant_verse'))['total'] or Decimal('0')
        reste = du - verse
        if verse <= 0:
            statut = 'En attente'
        elif reste > 0:
            statut = 'Partiel'
        else:
            statut = 'Soldé'
        bon = BonReglement.objects.filter(
            project=project, poseur=poseur, semaine=semaine, annee=annee,
        ).first()
        lignes.append({
            'poseur': poseur, 'du': du, 'verse': verse, 'reste': reste, 'statut': statut,
            'verse_confirme_tresorerie': verse_confirme_tresorerie,
            'bon': bon,
        })
    return lignes


def verser_paiement(project, poseur, semaine, annee, montant, date, user):
    """RG-10 : le montant versé (approuvé + en attente) à un poseur ne peut jamais dépasser le montant dû
    de la semaine. RG-15 : le versement espèce est enregistré en attente d'approbation Trésorerie —
    voir approuver_paiement."""
    from django.db.models import Sum

    from .models_pose import Paiement, Pointage

    try:
        montant = Decimal(str(montant).replace(',', '.'))
    except InvalidOperation:
        raise PointageError('Montant de versement invalide.')
    if montant <= 0:
        raise PointageError('Le montant du versement doit être positif.')

    du = Pointage.objects.filter(
        project=project, poseur=poseur, semaine=semaine, annee=annee,
    ).aggregate(total=Sum('montant'))['total'] or Decimal('0')
    deja_verse_ou_attente = Paiement.objects.filter(
        project=project, poseur=poseur, semaine=semaine, annee=annee,
    ).exclude(statut=Paiement.Statut.REJETE).aggregate(total=Sum('montant_verse'))['total'] or Decimal('0')

    if deja_verse_ou_attente + montant > du:
        raise PointageError(  # RG-10
            f'Ce versement dépasserait le montant dû de la semaine — '
            f'reste à payer : {du - deja_verse_ou_attente}.'
        )

    paiement = Paiement.objects.create(
        project=project, poseur=poseur, semaine=semaine, annee=annee,
        montant_verse=montant, date=date, created_by=user,
        statut=Paiement.Statut.EN_ATTENTE,
    )
    _reinitialiser_bon_si_existant(project, poseur, semaine, annee)  # RG-14
    return paiement


def approuver_paiement(paiement, user):
    """RG-15 : la Trésorerie ne peut confirmer un versement espèce qu'une fois le bon de règlement
    du triplet validé par la DG (RG-16) — la confirmation Trésorerie est une formalisation finale,
    elle ne modifie jamais le dû/versé/reste (déjà acquis dès la soumission par le chef)."""
    from django.utils import timezone

    from .models_pose import BonReglement, Paiement

    if paiement.statut != Paiement.Statut.EN_ATTENTE:
        raise PointageError(f'Ce versement est déjà « {paiement.get_statut_display()} ».')

    bon = BonReglement.objects.filter(
        project=paiement.project, poseur=paiement.poseur, semaine=paiement.semaine, annee=paiement.annee,
    ).first()
    if not bon or bon.statut != BonReglement.Statut.VALIDE_DG:
        raise PointageError(  # RG-16
            "Ce versement ne peut pas être confirmé par la Trésorerie tant que le bon de règlement "
            "de ce poseur pour cette semaine n'a pas été validé par la DG."
        )

    paiement.statut = Paiement.Statut.APPROUVE
    paiement.approuve_par = user
    paiement.approuve_le = timezone.now()
    paiement.save(update_fields=['statut', 'approuve_par', 'approuve_le'])
    return paiement


def rejeter_paiement(paiement, motif, user):
    """La Trésorerie rejette un versement espèce erroné — reste tracé, ne compte jamais dans le versé."""
    from .models_pose import Paiement

    if paiement.statut != Paiement.Statut.EN_ATTENTE:
        raise PointageError(f'Ce versement est déjà « {paiement.get_statut_display()} ».')

    paiement.statut = Paiement.Statut.REJETE
    paiement.motif_rejet = (motif or '').strip()
    paiement.approuve_par = user
    from django.utils import timezone
    paiement.approuve_le = timezone.now()
    paiement.save(update_fields=['statut', 'motif_rejet', 'approuve_par', 'approuve_le'])
    return paiement


def _reinitialiser_bon_si_existant(project, poseur, semaine, annee) -> None:
    """RG-14 : tout nouveau versement sur le triplet remet le bon de règlement en EN_ATTENTE."""
    from .models_pose import BonReglement

    BonReglement.objects.filter(
        project=project, poseur=poseur, semaine=semaine, annee=annee,
    ).exclude(statut=BonReglement.Statut.EN_ATTENTE).update(
        statut=BonReglement.Statut.EN_ATTENTE,
        approuve_par_chef=None, approuve_chef_le=None,
        valide_par_dg=None, valide_dg_le=None,
    )


def solder_poseur_semaine(project, poseur, semaine, annee, date, user):
    """Verse automatiquement le reliquat exact pour solder ce poseur sur cette semaine."""
    ligne = next(
        (l for l in lignes_reglement_semaine(project, semaine, annee) if l['poseur'].pk == poseur.pk),
        None,
    )
    if not ligne or ligne['reste'] <= 0:
        raise PointageError('Rien à solder pour ce poseur cette semaine.')
    return verser_paiement(project, poseur, semaine, annee, ligne['reste'], date, user)


def solder_projet_semaine(project, semaine, annee, date, user):
    """Solde tous les poseurs ayant un reste à payer, pour ce projet et cette semaine."""
    paiements = []
    for ligne in lignes_reglement_semaine(project, semaine, annee):
        if ligne['reste'] > 0:
            paiements.append(verser_paiement(project, ligne['poseur'], semaine, annee, ligne['reste'], date, user))
    return paiements


def approuver_bon_chef(project, poseur, semaine, annee, user):
    """Approbation préalable du chef de projet — condition requise avant la validation DG (RG-13)."""
    from django.db.models import Sum
    from django.utils import timezone

    from .models_pose import BonReglement, Paiement

    verse = Paiement.objects.filter(
        project=project, poseur=poseur, semaine=semaine, annee=annee,
    ).exclude(statut=Paiement.Statut.REJETE).aggregate(total=Sum('montant_verse'))['total'] or Decimal('0')
    if verse <= 0:
        raise PointageError('Aucun versement enregistré pour ce poseur cette semaine — rien à approuver.')

    bon, _ = BonReglement.objects.get_or_create(
        project=project, poseur=poseur, semaine=semaine, annee=annee,
    )
    if bon.statut != BonReglement.Statut.EN_ATTENTE:
        raise PointageError(f'Ce bon est déjà « {bon.get_statut_display()} ».')

    bon.statut = BonReglement.Statut.APPROUVE_CHEF
    bon.approuve_par_chef = user
    bon.approuve_chef_le = timezone.now()
    bon.save(update_fields=['statut', 'approuve_par_chef', 'approuve_chef_le', 'updated_at'])
    return bon


def valider_bon_dg(bon, user):
    """Validation DG — nécessite l'approbation préalable du chef de projet (RG-13)."""
    from django.utils import timezone

    from .models_pose import BonReglement

    if bon.statut == BonReglement.Statut.EN_ATTENTE:
        raise PointageError("Ce bon doit d'abord être approuvé par le chef de projet.")
    if bon.statut == BonReglement.Statut.VALIDE_DG:
        raise PointageError('Ce bon est déjà validé.')

    bon.statut = BonReglement.Statut.VALIDE_DG
    bon.valide_par_dg = user
    bon.valide_dg_le = timezone.now()
    bon.save(update_fields=['statut', 'valide_par_dg', 'valide_dg_le', 'updated_at'])
    return bon


def projets_pipeline_pose(user):
    """RG-08/RG-09 : chef de projet → ses projets de pose (+ ceux délégués à lui comme
    coordinateur — RG-17) ; DG/DC/superuser → tous."""
    from django.db.models import Q
    from django.utils import timezone

    from .models import Project

    qs = Project.objects.filter(pose_meta__isnull=False).select_related('pose_meta').order_by('-created_at')
    if user.is_superuser or getattr(user, 'role', None) in ROLES_CREATION_PROJET_POSE:
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

    return qs.filter(Q(chef_de_projet_id=user.id) | Q(pk__in=list(delegues_ids))).distinct()


def pipeline_kpis(project) -> dict:
    """Étape 6 — indicateurs Pipeline/Pilotage, tous calculés (jamais stockés), sauf cumul_attachement (RG-12).

    L'avancement et le montant payé sont calculés à partir du pointage par composant
    (PoseArticleDecomposition/PosePointageComposant — module actuel), pas de l'ancien
    système par lot/zone (Lot/Pointage), qui n'est plus alimenté en usage réel.
    """
    from .models_pose import PosePointageComposant
    from .pose_service import montant_article, montant_composant

    centimes = Decimal('0.01')
    articles = list(project.pose_articles.prefetch_related('decompositions__pointages'))
    montant_ht_total = sum((a.prix_total_ht for a in articles), Decimal('0'))
    budget_de_pose_total = sum(
        (a.budget_de_pose * a.quantite for a in articles), Decimal('0'),
    ).quantize(centimes)

    montant_prevu_total = sum(
        ((a.prix_de_pose or Decimal('0')) * a.quantite for a in articles), Decimal('0'),
    ).quantize(centimes)
    montant_realise_total = sum((montant_article(a) for a in articles), Decimal('0'))

    montant_paye_poseurs = Decimal('0')
    for article in articles:
        prix = article.prix_de_pose or Decimal('0')
        for decomposition in article.decompositions.filter(actif=True):
            for fiche in decomposition.pointages.all():
                if fiche.statut == PosePointageComposant.Statut.PAYE:
                    montant_paye_poseurs += montant_composant(decomposition, fiche.quantite_posee, prix)

    budget_restant = budget_de_pose_total - montant_paye_poseurs
    depassement = max(Decimal('0'), montant_paye_poseurs - budget_de_pose_total)  # RG-11 : signalé, non bloquant

    avancement_physique = (
        round(float(montant_realise_total) * 100 / float(montant_prevu_total), 1) if montant_prevu_total else 0
    )

    meta = getattr(project, 'pose_meta', None)
    cumul_attachement = meta.cumul_attachement if meta else Decimal('0')  # RG-12 : saisi, jamais déduit
    avancement_attachement = (
        round(float(cumul_attachement) * 100 / float(montant_ht_total), 1) if montant_ht_total else 0
    )

    return {
        'montant_ht_total': montant_ht_total,
        'budget_de_pose_total': budget_de_pose_total,
        'montant_paye_poseurs': montant_paye_poseurs,
        'budget_restant': budget_restant,
        'depassement': depassement,
        'avancement_physique': avancement_physique,
        'cumul_attachement': cumul_attachement,
        'avancement_attachement': avancement_attachement,
    }


def definir_cumul_attachement(project, montant, user):
    """RG-12 : le cumul attachement est une donnée saisie manuellement, jamais déduite des pointages."""
    from .models_pose import PoseProjetMeta

    try:
        montant = Decimal(str(montant).replace(',', '.'))
    except InvalidOperation:
        raise PointageError('Montant de cumul attachement invalide.')
    if montant < 0:
        raise PointageError('Le cumul attachement ne peut pas être négatif.')

    meta = getattr(project, 'pose_meta', None)
    if meta is None:
        raise PointageError("Ce projet n'a pas de métadonnées de pose (region/commercial) — anomalie.")
    meta.cumul_attachement = montant
    meta.save(update_fields=['cumul_attachement', 'updated_at'])
    return meta


class BordereauImportError(Exception):
    pass


_COLUMN_ALIASES = {
    'CODE': 'code',
    'DESIGNATION DES ARTICLES': 'designation',
    'UNITE': 'unite',
    'QTE': 'quantite',
    'PRIX UNITAIRE HT': 'prix_unitaire_ht',
    'PRIX TOTAL HT': 'prix_total_ht',
    'BUDGET DE POSE': 'budget_de_pose',
    'DECOMPOSITION': 'libelle_composant',
    'DECOMPOSITION PRIX %': 'poids_prix',
}
# Clé d'alias sans aucun espace (ex. 'DECOMPOSITIONPRIX%') pour tolérer les en-têtes
# du fichier source où l'espace avant/dans le libellé peut être absent ou différent.
_COLUMN_ALIASES_SANS_ESPACE = {
    re.sub(r'\s+', '', cle): valeur for cle, valeur in _COLUMN_ALIASES.items()
}


def _normalise(txt) -> str:
    return re.sub(r'\s+', ' ', str(txt or '').strip().upper())


def _cle_colonne(txt):
    """Résout un en-tête de colonne vers son champ, insensible aux espaces (RG-07)."""
    sans_espace = re.sub(r'\s+', '', str(txt or '').strip().upper())
    return _COLUMN_ALIASES_SANS_ESPACE.get(sans_espace)


def _to_decimal(value) -> Decimal:
    if value in (None, ''):
        return Decimal('0')
    try:
        return Decimal(str(value).replace(' ', '').replace(',', '.'))
    except InvalidOperation:
        return Decimal('0')


def _normaliser_poids(value) -> Decimal:
    """RG-05 : poids_prix ∈ ]0,1]. Normalise 50 (nombre brut) ou "50%" en 0.5 ; 0.5 reste 0.5."""
    if value in (None, ''):
        return Decimal('0')
    texte = str(value).strip().replace('%', '').replace(',', '.')
    try:
        poids = Decimal(texte)
    except InvalidOperation:
        return Decimal('0')
    if poids > 1:
        poids = poids / Decimal('100')
    return poids


def importer_bordereau(project, fichier):
    """
    Importe un bordereau .xlsx (1ère feuille) et crée les Articles du projet, avec leur
    décomposition en composants pondérés le cas échéant (RG-07) :
    - une ligne avec CODE/DESIGNATION renseignés = nouvel article courant ;
    - une ligne avec CODE/DESIGNATION vides et DECOMPOSITION renseigné = composant de
      l'article courant (RG-01, RG-05).
    En-tête auto-détecté ; lignes 'TOTAL ...' ignorées.
    RG-04/RG-14 : si un seul article a une décomposition dont Σ des poids ≠ 100 %, tout
    l'import est rejeté (BordereauImportError listant les articles en cause) — le fichier
    source doit être corrigé et réimporté en entier (aucun article n'est créé).
    Retourne (nb_articles_crees, nb_lignes_ignorees).
    """
    from .models_pose import Article, PoseArticleDecomposition
    from .pose_service import valider_somme_poids

    try:
        wb = openpyxl.load_workbook(fichier, data_only=False)
    except Exception as exc:
        raise BordereauImportError(f'Fichier .xlsx illisible : {exc}')

    sheet = wb.worksheets[0]

    header_row_idx = None
    col_map = {}
    for row in sheet.iter_rows(min_row=1, max_row=min(30, sheet.max_row)):
        found = {}
        for cell in row:
            champ = _cle_colonne(cell.value)
            if champ:
                found[champ] = cell.column
        if 'code' in found and 'designation' in found:
            header_row_idx = row[0].row
            col_map = found
            break

    if header_row_idx is None:
        raise BordereauImportError(
            "En-tête introuvable : le fichier doit contenir les colonnes "
            "CODE et DESIGNATION DES ARTICLES."
        )

    nb_crees = 0
    nb_ignorees = 0
    article_courant = None
    ordre_composant = 0
    articles_avec_decomposition = []

    for row in sheet.iter_rows(min_row=header_row_idx + 1, max_row=sheet.max_row):
        def get(field):
            col = col_map.get(field)
            return row[col - 1].value if col else None

        code = get('code')
        designation = get('designation')

        if not code and not designation:
            libelle_composant = str(get('libelle_composant') or '').strip()
            if libelle_composant and article_courant is not None:
                ordre_composant += 1
                PoseArticleDecomposition.objects.create(
                    article=article_courant,
                    libelle_composant=libelle_composant,
                    poids_prix=_normaliser_poids(get('poids_prix')),
                    ordre=ordre_composant,
                )
                if article_courant not in articles_avec_decomposition:
                    articles_avec_decomposition.append(article_courant)
            else:
                nb_ignorees += 1
            continue

        if 'TOTAL' in _normalise(designation) or 'TOTAL' in _normalise(code):
            nb_ignorees += 1
            continue

        article_courant = Article.objects.create(
            project=project,
            code=str(code or '').strip(),
            designation=str(designation or '').strip(),
            unite=str(get('unite') or '').strip(),
            quantite=_to_decimal(get('quantite')),
            prix_unitaire_ht=_to_decimal(get('prix_unitaire_ht')),
            prix_total_ht=_to_decimal(get('prix_total_ht')),
            budget_de_pose=_to_decimal(get('budget_de_pose')),
        )
        ordre_composant = 0
        nb_crees += 1

    if nb_crees == 0:
        raise BordereauImportError('Aucun article valide trouvé dans le fichier.')

    erreurs_somme = []
    for article in articles_avec_decomposition:
        is_valid, somme, ecart = valider_somme_poids(article)
        if not is_valid:
            erreurs_somme.append(
                f"Article {article.code} : Σ des poids de décomposition = {somme * 100} % "
                f"(écart {ecart * 100} %)"
            )

    if erreurs_somme:
        raise BordereauImportError(
            "Import annulé — la décomposition de certains articles ne fait pas 100 % : "
            + ' ; '.join(erreurs_somme)
            + '. Corrigez le fichier et réimportez.'
        )

    return nb_crees, nb_ignorees
