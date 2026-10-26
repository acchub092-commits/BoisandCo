"""
Module « Gestion de la pose » (CDC Nisrine ALAMI, v1.0, 20/07/2026).
Extension strictement additive de apps.projects — aucun modèle existant modifié.
Importé en fin de apps/projects/models.py pour être détecté par Django.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from .models import Project


def poseur_scan_cin_upload_path(instance, filename):
    """media/poseurs/<cin>/cin_<filename>"""
    import os
    return os.path.join('poseurs', instance.cin or 'divers', filename)


def pose_pointage_media_upload_path(instance, filename):
    """media/pose_pointage/<project_pk>/<piece_pk>/<filename>"""
    import os
    return os.path.join(
        'pose_pointage', str(instance.ligne.piece.project_id), str(instance.ligne.piece_id), filename,
    )


class Poseur(models.Model):
    """Poseur pouvant être affecté à des articles (module Gestion de la pose)."""

    nom = models.CharField(max_length=150, verbose_name='Nom')
    cin = models.CharField(max_length=20, unique=True, verbose_name='CIN')
    scan_cin = models.FileField(
        upload_to=poseur_scan_cin_upload_path,
        null=True, blank=True,
        verbose_name='Scan de la CIN',
    )
    is_active = models.BooleanField(default=True, verbose_name='Actif')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Poseur'
        verbose_name_plural = 'Poseurs'
        ordering = ['nom']

    def __str__(self):
        return f'{self.nom} ({self.cin})'


class Article(models.Model):
    """Article d'un bordereau de pose, rattaché à un Projet."""

    class StatutValidation(models.TextChoices):
        EN_ATTENTE = 'EN_ATTENTE', 'En attente'
        VALIDE = 'VALIDE', 'Validé'
        REFUSE = 'REFUSE', 'Refusé'

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name='pose_articles', verbose_name='Projet',
    )
    code = models.CharField(max_length=50, verbose_name='Code')
    designation = models.CharField(max_length=300, verbose_name='Désignation des articles')
    unite = models.CharField(max_length=20, verbose_name='Unité')
    quantite = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Quantité prévue')
    prix_unitaire_ht = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Prix unitaire HT')
    prix_total_ht = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='Prix total HT')
    budget_de_pose = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Budget de pose (indicatif)',
    )
    prix_de_pose = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Prix de pose (saisi par le chef de projet)',
    )
    frais_logistique_pose = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Frais de logistique pose (par unité)',
        help_text="Coût logistique unitaire (transport, manutention…), multiplié par la quantité "
                   "de l'article et ajouté au budget engagé de la pose — distinct du prix de pose "
                   "versé au poseur, jamais inclus dans son règlement.",
    )
    statut_validation = models.CharField(
        max_length=20, choices=StatutValidation.choices,
        default=StatutValidation.EN_ATTENTE, verbose_name='Statut de validation',
    )
    motif_refus = models.TextField(blank=True, verbose_name='Motif de refus')
    poseurs = models.ManyToManyField(
        Poseur, through='Affectation', related_name='articles',
        blank=True, verbose_name='Poseurs affectés',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Article (pose)'
        verbose_name_plural = 'Articles (pose)'
        ordering = ['project', 'code']
        indexes = [
            models.Index(fields=['project', 'statut_validation']),
        ]

    def __str__(self):
        return f'{self.code} — {self.designation}'

    @property
    def quantite_reservee_lots(self):
        """Somme des quantités déjà affectées à des lots (ouverts ou clôturés)."""
        return self.lots.aggregate(total=Sum('quantite'))['total'] or Decimal('0')

    @property
    def quantite_disponible(self):
        """Quantité restant à répartir en nouveaux lots — contrôle du dépassement à la création d'un lot."""
        return self.quantite - self.quantite_reservee_lots

    @property
    def quantite_terminee(self):
        """RG-06 : somme des quantités effectivement posées (Σ quantité_lot × %/100)."""
        return sum((lot.quantite_effective for lot in self.lots.all()), Decimal('0'))

    @property
    def avancement_percent(self):
        if not self.quantite:
            return 0
        return round(float(self.quantite_terminee) * 100 / float(self.quantite), 1)


class Affectation(models.Model):
    """Table de liaison Article ↔ Poseur. Suppression du Poseur → retrait auto (CASCADE)."""

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='affectations')
    poseur = models.ForeignKey(Poseur, on_delete=models.CASCADE, related_name='affectations')
    affecte_le = models.DateTimeField(auto_now_add=True)
    affecte_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Affecté par',
    )

    class Meta:
        verbose_name = 'Affectation'
        verbose_name_plural = 'Affectations'
        unique_together = [['article', 'poseur']]

    def __str__(self):
        return f'{self.poseur} → {self.article}'


class PoseProjetMeta(models.Model):
    """Métadonnées Gestion de la pose, satellite de Project (Project non modifié)."""

    project = models.OneToOneField(
        Project, on_delete=models.CASCADE,
        related_name='pose_meta', verbose_name='Projet',
    )
    region = models.CharField(max_length=100, verbose_name='Région')
    commercial = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pose_projets_commercial', verbose_name='Commercial',
    )
    cumul_attachement = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, blank=True,
        verbose_name='Cumul attachement (saisi, hebdomadaire)',
        help_text='RG-12 : donnée saisie manuellement, jamais déduite des pointages.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pose — méta projet'
        verbose_name_plural = 'Pose — méta projets'

    def __str__(self):
        return f'Pose meta — {self.project.reference}'


class Lot(models.Model):
    """Lot de pose : couple Article/Poseur, avancement par paliers de 10 % jusqu'à clôture à 100 %."""

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='lots', verbose_name='Article')
    poseur = models.ForeignKey(Poseur, on_delete=models.CASCADE, related_name='lots', verbose_name='Poseur')
    quantite = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Quantité du lot')
    pourcentage = models.PositiveSmallIntegerField(default=0, verbose_name='Avancement (%)')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Créé par',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Lot'
        verbose_name_plural = 'Lots'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.article.code} / {self.poseur.nom} — {self.pourcentage}%'

    @property
    def is_cloture(self):
        """RG-04/RG-05 : un lot est clôturé dès qu'il atteint 100 % — jamais stocké, toujours dérivé."""
        return self.pourcentage >= 100

    @property
    def quantite_effective(self):
        return (self.quantite * self.pourcentage / 100).quantize(Decimal('0.01'))

    @property
    def montant_verse(self):
        """Montant déjà versé sur ce lot à son avancement actuel (formule §6 CDC)."""
        prix = self.article.prix_de_pose or Decimal('0')
        return (self.quantite_effective * prix).quantize(Decimal('0.01'))


class Pointage(models.Model):
    """Pointage journalier — un enregistrement horodaté par incrément d'avancement (traçabilité RG-04/05)."""

    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name='pointages', verbose_name='Lot')
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='pointages', verbose_name='Article')
    poseur = models.ForeignKey(Poseur, on_delete=models.CASCADE, related_name='pointages', verbose_name='Poseur')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='pose_pointages', verbose_name='Projet')

    date = models.DateField(verbose_name='Date du pointage')
    semaine = models.PositiveSmallIntegerField(verbose_name='Semaine')
    annee = models.PositiveSmallIntegerField(verbose_name='Année')

    quantite = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Quantité du lot')
    pourcentage = models.PositiveSmallIntegerField(verbose_name='Nouvel avancement (%)')
    quantite_effective = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='Quantité effective (delta de ce pointage)',
    )
    montant = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Montant de ce pointage')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Saisi par',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pointage'
        verbose_name_plural = 'Pointages'
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['project', 'semaine', 'annee']),
        ]

    def __str__(self):
        return f'{self.article.code} / {self.poseur.nom} — {self.date} ({self.pourcentage}%)'


class Paiement(models.Model):
    """Versement espèce à un poseur, rattaché au triplet semaine/projet/poseur (Étape 5).

    Tout versement est en espèces et doit être approuvé par la Trésorerie avant
    de compter dans le « versé » du poseur — voir pose_gestion_service.approuver_paiement.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = 'EN_ATTENTE', "En attente d'approbation Trésorerie"
        APPROUVE = 'APPROUVE', 'Approuvé'
        REJETE = 'REJETE', 'Rejeté'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='pose_paiements', verbose_name='Projet')
    poseur = models.ForeignKey(Poseur, on_delete=models.CASCADE, related_name='paiements', verbose_name='Poseur')
    semaine = models.PositiveSmallIntegerField(verbose_name='Semaine')
    annee = models.PositiveSmallIntegerField(verbose_name='Année')
    montant_verse = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Montant versé')
    date = models.DateField(verbose_name='Date de versement')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE,
        verbose_name='Statut',
    )
    motif_rejet = models.TextField(blank=True, verbose_name='Motif de rejet')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Enregistré par',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approuve_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Approuvé par (Trésorerie)',
    )
    approuve_le = models.DateTimeField(null=True, blank=True, verbose_name='Approuvé le')

    class Meta:
        verbose_name = 'Paiement'
        verbose_name_plural = 'Paiements'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['project', 'poseur', 'semaine', 'annee']),
            models.Index(fields=['statut']),
        ]

    def __str__(self):
        return f'{self.poseur.nom} — S{self.semaine}/{self.annee} : {self.montant_verse} ({self.get_statut_display()})'


class BonReglement(models.Model):
    """Bon de règlement (émargement poseur), un par triplet projet/poseur/semaine.

    Circuit d'approbation avant édition/impression :
    EN_ATTENTE → APPROUVE_CHEF (chef de projet) → VALIDE_DG (DG, seul état éditable).
    Tout nouveau versement sur ce triplet remet le bon en EN_ATTENTE (voir pose_gestion_service).
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = 'EN_ATTENTE', 'En attente'
        APPROUVE_CHEF = 'APPROUVE_CHEF', 'Approuvé par le chef de projet'
        VALIDE_DG = 'VALIDE_DG', 'Validé par la DG'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='pose_bons_reglement', verbose_name='Projet')
    poseur = models.ForeignKey(Poseur, on_delete=models.CASCADE, related_name='bons_reglement', verbose_name='Poseur')
    semaine = models.PositiveSmallIntegerField(verbose_name='Semaine')
    annee = models.PositiveSmallIntegerField(verbose_name='Année')
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE, verbose_name='Statut')

    approuve_par_chef = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Approuvé par (chef de projet)',
    )
    approuve_chef_le = models.DateTimeField(null=True, blank=True, verbose_name='Approuvé le (chef)')
    valide_par_dg = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Validé par (DG)',
    )
    valide_dg_le = models.DateTimeField(null=True, blank=True, verbose_name='Validé le (DG)')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Bon de règlement'
        verbose_name_plural = 'Bons de règlement'
        unique_together = [['project', 'poseur', 'semaine', 'annee']]
        ordering = ['-annee', '-semaine']

    def __str__(self):
        return f'Bon — {self.poseur.nom} — S{self.semaine}/{self.annee} ({self.get_statut_display()})'


# ---------------------------------------------------------------------------
# Décomposition d'articles + pointage par composant avec workflow
# (extension additive — pointage total par composant pondéré, sans zone,
# distincte du pointage par lot/poseur ci-dessus).
# ---------------------------------------------------------------------------

class PoseArticleDecomposition(models.Model):
    """Composant pondéré d'un article (poids en part du prix) — RG-01, RG-04, RG-05."""

    article = models.ForeignKey(
        Article, on_delete=models.CASCADE,
        related_name='decompositions', verbose_name='Article',
    )
    libelle_composant = models.CharField(max_length=200, verbose_name='Composant')
    poids_prix = models.DecimalField(
        max_digits=5, decimal_places=4, verbose_name='Poids (part du prix)',
        help_text='Décimal entre 0 (exclu) et 1 (inclus) — ex. 0.5 = 50 %.',
    )
    ordre = models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Décomposition (composant de pose)'
        verbose_name_plural = 'Décompositions (composants de pose)'
        ordering = ['article', 'ordre']
        unique_together = [['article', 'libelle_composant']]

    def __str__(self):
        return f'{self.article.code} — {self.libelle_composant} ({self.poids_prix * 100} %)'


class PosePointageComposant(models.Model):
    """Fiche de pointage d'un composant, en quantité totale (RG-02) — machine à états BROUILLON→VALIDÉ→PAYÉ.

    Une fiche par (composant, poseur) — `poseur` reste vide (None) tant que l'article a au
    plus un seul poseur affecté (fiche partagée, comportement historique). Dès que l'article a
    2 poseurs ou plus, chaque poseur a sa propre fiche pour chaque composant : la quantité
    prévue de l'article reste un total partagé (Reste = quantité article − Σ quantités de
    TOUS les poseurs sur ce composant), il n'y a pas de quota individuel figé par poseur.
    """

    class Statut(models.TextChoices):
        BROUILLON = 'BROUILLON', 'Brouillon'
        VALIDE = 'VALIDE', 'Validé'
        PAYE = 'PAYE', 'Payé'

    decomposition = models.ForeignKey(
        PoseArticleDecomposition, on_delete=models.CASCADE,
        related_name='pointages', verbose_name='Composant',
    )
    poseur = models.ForeignKey(
        Poseur, on_delete=models.CASCADE, null=True, blank=True,
        related_name='+', verbose_name='Poseur',
        help_text='Vide = fiche partagée (article à un seul poseur ou non affecté).',
    )
    quantite_posee = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name='Quantité posée (totale)',
    )
    quantite_payee = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name='Quantité déjà payée',
        help_text=(
            "Part de la quantité posée déjà incluse dans une demande de paiement validée — "
            "le reste à payer se calcule toujours par différence (quantite_posee - quantite_payee), "
            "jamais figé, pour permettre un pointage progressif même après un premier paiement."
        ),
    )
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON, verbose_name='Statut',
    )
    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Saisi par',
    )
    date_saisie = models.DateTimeField(null=True, blank=True, verbose_name='Date de saisie')
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Validé par',
    )
    date_validation = models.DateTimeField(null=True, blank=True, verbose_name='Date de validation')
    paye = models.BooleanField(
        default=False, verbose_name='Payé',
        help_text="Flag interne (RG-26) — alimentation automatique à définir ultérieurement.",
    )
    verrou_modification = models.BooleanField(
        default=False, verbose_name='Verrouillé',
        help_text='Verrouillé tant qu\'une dérogation DG/Admin n\'a pas été accordée (fiche PAYÉ).',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pointage (composant)'
        verbose_name_plural = 'Pointages (composants)'
        indexes = [
            models.Index(fields=['statut']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['decomposition'], condition=models.Q(poseur__isnull=True),
                name='pose_pointage_unique_fiche_partagee',
            ),
            models.UniqueConstraint(
                fields=['decomposition', 'poseur'], condition=models.Q(poseur__isnull=False),
                name='pose_pointage_unique_par_poseur',
            ),
        ]

    def __str__(self):
        if self.poseur_id:
            return f'{self.decomposition} — {self.poseur} — {self.quantite_posee} ({self.get_statut_display()})'
        return f'{self.decomposition} — {self.quantite_posee} ({self.get_statut_display()})'


class PosePointageAudit(models.Model):
    """Trace immuable de chaque action sur une fiche de pointage — RG-19, RG-22. Jamais update/delete applicatif."""

    class Action(models.TextChoices):
        CREATION = 'CREATION', 'Création (saisie)'
        MODIFICATION = 'MODIFICATION', 'Quantité modifiée'
        VALIDATION = 'VALIDATION', 'Validation'
        DEMANDE_MODIFICATION = 'DEMANDE_MODIFICATION', 'Demande de modification'
        APPROBATION_MODIFICATION = 'APPROBATION_MODIFICATION', 'Modification approuvée (Directeur)'
        REFUS_MODIFICATION = 'REFUS_MODIFICATION', 'Modification refusée'
        DEMANDE_DEROGATION = 'DEMANDE_DEROGATION', 'Demande de dérogation'
        DEROGATION_ACCORDEE = 'DEROGATION_ACCORDEE', 'Dérogation accordée'
        DEROGATION_REFUSEE = 'DEROGATION_REFUSEE', 'Dérogation refusée'
        ANNULATION = 'ANNULATION', 'Quantité annulée (pièce refusée)'
        PAIEMENT = 'PAIEMENT', 'Marqué payé (poseur réglé)'

    fiche = models.ForeignKey(
        PosePointageComposant, on_delete=models.CASCADE,
        related_name='audits', verbose_name='Fiche',
    )
    acteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Acteur',
    )
    action = models.CharField(max_length=30, choices=Action.choices, verbose_name='Action')
    ancienne_valeur = models.CharField(max_length=255, blank=True, verbose_name='Ancienne valeur')
    nouvelle_valeur = models.CharField(max_length=255, blank=True, verbose_name='Nouvelle valeur')
    motif = models.TextField(blank=True, verbose_name='Motif')
    horodatage = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Audit de pointage'
        verbose_name_plural = 'Audits de pointage'
        ordering = ['-horodatage']

    def __str__(self):
        return f'{self.fiche} — {self.get_action_display()} — {self.horodatage:%d/%m/%Y %H:%M}'


class PoseDemandeModification(models.Model):
    """Demande de modification d'une fiche déjà validée ou payée — RG-20, RG-21."""

    class TypeDemande(models.TextChoices):
        VALIDATION_DIRECTEUR = 'VALIDATION_DIRECTEUR', 'Modification post-validation (Directeur)'
        DEROGATION_DG = 'DEROGATION_DG', 'Dérogation paiement (DG ou Admin)'

    class Statut(models.TextChoices):
        EN_ATTENTE = 'EN_ATTENTE', 'En attente'
        APPROUVE = 'APPROUVE', 'Approuvé'
        REFUSE = 'REFUSE', 'Refusé'

    fiche = models.ForeignKey(
        PosePointageComposant, on_delete=models.CASCADE,
        related_name='demandes_modification', verbose_name='Fiche',
    )
    type_demande = models.CharField(max_length=25, choices=TypeDemande.choices, verbose_name='Type de demande')
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE, verbose_name='Statut')
    demandeur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Demandeur',
    )
    motif = models.TextField(verbose_name='Motif')
    nouvelle_quantite = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Nouvelle quantité proposée',
    )
    approbateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Approuvé/refusé par',
    )
    date_traitement = models.DateTimeField(null=True, blank=True, verbose_name='Date de traitement')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Demande de modification (pointage)'
        verbose_name_plural = 'Demandes de modification (pointage)'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.fiche} — {self.get_type_demande_display()} ({self.get_statut_display()})'


class PoseDelegation(models.Model):
    """Délégation d'un projet par un chef de projet à un conducteur de travaux — RG-16, RG-17."""

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name='pose_delegations', verbose_name='Projet',
    )
    chef_delegant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='+', verbose_name='Chef délégant',
    )
    conducteur_delegue = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='+', verbose_name='Conducteur délégué',
    )
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_debut = models.DateField(null=True, blank=True, verbose_name='Date de début')
    date_fin = models.DateField(null=True, blank=True, verbose_name='Date de fin')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Délégation (pose)'
        verbose_name_plural = 'Délégations (pose)'
        unique_together = [['project', 'conducteur_delegue']]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.project.reference} — {self.chef_delegant} → {self.conducteur_delegue}'


class PosePieceComptage(models.Model):
    """Pièce de comptage — un lot de pointages soumis en une fois (« Enregistrer tout »).

    Un seul lot non validé peut exister par projet à la fois : tant que la pièce en cours
    n'est pas validée, aucune nouvelle saisie n'est autorisée sur ce projet (voir
    pose_workflow_service.piece_en_attente / enregistrer_pointages_groupe).
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = 'EN_ATTENTE', 'En attente de validation'
        VALIDE = 'VALIDE', 'Validée'
        REFUSEE = 'REFUSEE', 'Refusée'

    class TypeRefus(models.TextChoices):
        REJET = 'REJET', 'Rejet définitif'
        REVISION = 'REVISION', 'Demande de révision'

    class MotifRevision(models.TextChoices):
        ERREUR_DE_FRAPPE = 'ERREUR_DE_FRAPPE', 'Erreur de frappe'
        ANOMALIE_POINTAGE = 'ANOMALIE_POINTAGE', 'Anomalie de pointage'
        AUTRE = 'AUTRE', 'Autre'

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name='pose_pieces_comptage', verbose_name='Projet',
    )
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE, verbose_name='Statut',
    )
    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Saisi par',
    )
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name='Date de création')
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Validé par',
    )
    date_validation = models.DateTimeField(null=True, blank=True, verbose_name='Date de validation')
    type_refus = models.CharField(max_length=20, choices=TypeRefus.choices, blank=True, verbose_name='Type de refus')
    motif_categorie = models.CharField(
        max_length=30, choices=MotifRevision.choices, blank=True, verbose_name='Motif (catégorie)',
    )
    motif_refus = models.TextField(blank=True, verbose_name='Motif détaillé')
    refuse_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Refusé par',
    )
    date_refus = models.DateTimeField(null=True, blank=True, verbose_name='Date de refus')

    class Meta:
        verbose_name = 'Pièce de comptage'
        verbose_name_plural = 'Pièces de comptage'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['project', 'statut']),
        ]

    @property
    def numero(self) -> str:
        """Numéro séquentiel affiché — dérivé de la clé primaire (globale, jamais réutilisée)."""
        return f'PC-{self.pk:06d}'

    def __str__(self):
        return f'{self.numero} — {self.project.reference} ({self.get_statut_display()})'


class PosePieceComptageLigne(models.Model):
    """Ligne d'une pièce de comptage : quantité saisie pour un composant, à cet instant."""

    piece = models.ForeignKey(
        PosePieceComptage, on_delete=models.CASCADE,
        related_name='lignes', verbose_name='Pièce de comptage',
    )
    decomposition = models.ForeignKey(
        PoseArticleDecomposition, on_delete=models.CASCADE,
        related_name='+', verbose_name='Composant',
    )
    poseur = models.ForeignKey(
        Poseur, on_delete=models.CASCADE, null=True, blank=True,
        related_name='+', verbose_name='Poseur',
        help_text='Vide = fiche partagée (article à un seul poseur ou non affecté).',
    )
    quantite_saisie = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Quantité saisie')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ligne de pièce de comptage'
        verbose_name_plural = 'Lignes de pièce de comptage'
        ordering = ['id']

    def __str__(self):
        return f'{self.piece.numero} — {self.decomposition.libelle_composant} : {self.quantite_saisie}'


class PosePieceComptageMedia(models.Model):
    """Photo ou vidéo jointe à une ligne de pointage — preuve visuelle de l'avancement saisi,
    conservée telle quelle (jamais modifiée) avec la pièce de comptage correspondante."""

    class TypeMedia(models.TextChoices):
        PHOTO = 'PHOTO', 'Photo'
        VIDEO = 'VIDEO', 'Vidéo'

    ligne = models.ForeignKey(
        PosePieceComptageLigne, on_delete=models.CASCADE,
        related_name='medias', verbose_name='Ligne de pointage',
    )
    fichier = models.FileField(upload_to=pose_pointage_media_upload_path, verbose_name='Fichier')
    type_media = models.CharField(max_length=10, choices=TypeMedia.choices, verbose_name='Type')
    uploaded_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Ajouté par',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Photo/vidéo de pointage'
        verbose_name_plural = 'Photos/vidéos de pointage'
        ordering = ['id']

    def __str__(self):
        return f'{self.ligne} — {self.get_type_media_display()}'


class PoseDemandePaiement(models.Model):
    """Demande de paiement — document composé progressivement (« En cours »), regroupant le
    reste à payer sélectionné pour un ou plusieurs poseurs (chaque ligne porte son propre
    poseur), puis soumis à la DG pour validation (RG-26). Une fois validée, chaque pointage
    lié passe VALIDÉ → PAYÉ ; un refus (« Retournée ») laisse les pointages intacts, disponibles
    pour une prochaine demande."""

    class Statut(models.TextChoices):
        BROUILLON = 'BROUILLON', 'En cours'
        EN_ATTENTE = 'EN_ATTENTE', 'Soumise à la validation'
        VALIDEE = 'VALIDEE', 'Validée'
        REFUSEE = 'REFUSEE', 'Retournée'

    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON, verbose_name='Statut',
    )
    montant_total = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='Montant total')
    demandeur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Demandeur',
    )
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name='Date de création')
    date_soumission = models.DateTimeField(null=True, blank=True, verbose_name='Date de soumission à la DG')
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Traitée par',
    )
    date_validation = models.DateTimeField(null=True, blank=True, verbose_name='Date de traitement')
    motif_refus = models.TextField(blank=True, verbose_name='Motif de refus')
    nb_impressions = models.PositiveIntegerField(default=0, verbose_name="Nombre d'impressions")

    class Meta:
        verbose_name = 'Demande de paiement'
        verbose_name_plural = 'Demandes de paiement'
        ordering = ['-date_creation']

    @property
    def numero(self):
        """Numéro séquentiel affiché — dérivé de la clé primaire (globale, jamais réutilisée)."""
        return f'DP-{self.pk:06d}'

    def __str__(self):
        return f'{self.numero} ({self.get_statut_display()})'


class PoseDemandePaiementLigne(models.Model):
    """Une ligne = un pointage (PosePointageComposant) inclus dans la demande, avec le poseur
    et le montant figés au moment de l'ajout (traçabilité même si l'article change ensuite).
    Une demande peut regrouper des lignes de poseurs différents."""

    demande = models.ForeignKey(
        PoseDemandePaiement, on_delete=models.CASCADE,
        related_name='lignes', verbose_name='Demande de paiement',
    )
    fiche = models.ForeignKey(
        PosePointageComposant, on_delete=models.CASCADE,
        related_name='+', verbose_name='Pointage',
    )
    poseur = models.ForeignKey(
        Poseur, on_delete=models.CASCADE,
        related_name='+', verbose_name='Poseur',
    )
    quantite = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name='Quantité payée par cette ligne',
        help_text="Delta de quantité couvert par cette ligne — jamais la quantité totale de la fiche.",
    )
    montant = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='Montant')
    recu = models.ForeignKey(
        'PoseRecuPaiement', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lignes_payees', verbose_name='Reçu de paiement',
        help_text="Renseigné uniquement lorsque la Trésorerie a matérialisé le règlement effectif "
                   "de cette ligne par un reçu — une demande Validée n'est pas encore payée tant que "
                   "ce champ est vide.",
    )

    class Meta:
        verbose_name = 'Ligne de demande de paiement'
        verbose_name_plural = 'Lignes de demande de paiement'
        unique_together = [['demande', 'fiche']]

    def __str__(self):
        return f'{self.demande.numero} — {self.poseur.nom} — {self.fiche} : {self.montant}'


class PoseRecuPaiement(models.Model):
    """Reçu de paiement — matérialise le règlement effectif par la Trésorerie d'une sélection de
    lignes de demandes déjà Validées par le Responsable de la pose. La validation DG (RG-26)
    n'entraîne plus, à elle seule, le paiement : seule l'émission d'un reçu incrémente
    PosePointageComposant.quantite_payee. Un reçu regroupe librement des lignes de plusieurs
    poseurs et de plusieurs demandes (chaque poseur reçoit sa propre remise/signature à l'impression)."""

    date_recu = models.DateField(default=timezone.localdate, verbose_name='Date du reçu')
    montant_total = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='Montant total')
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Émis par',
    )
    remis_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Remis par (Trésorerie)',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    nb_impressions = models.PositiveIntegerField(default=0, verbose_name="Nombre d'impressions")

    class Meta:
        verbose_name = 'Reçu de paiement'
        verbose_name_plural = 'Reçus de paiement'
        ordering = ['-created_at']

    @property
    def numero(self):
        return f'REC-{self.pk:06d}'

    def __str__(self):
        return self.numero
