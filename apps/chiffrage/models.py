"""
Module Gestion du Chiffrage / Devis Client — Bois&Co
"""
import os
from django.db import models
from django.conf import settings
from django.utils import timezone


def chiffrage_file_path(instance, filename):
    return os.path.join('chiffrage', str(instance.demande_id), filename)


def message_file_path(instance, filename):
    return os.path.join('chiffrage', 'messages', filename)


class DemandeChiffrage(models.Model):

    class Statut(models.TextChoices):
        EN_ATTENTE   = 'EN_ATTENTE',   'En attente de validation DC'
        VALIDEE_DC   = 'VALIDEE_DC',   'Validée — En attente Méthodes'
        REJETEE      = 'REJETEE',      'Rejetée — À corriger'
        RETOURNEE    = 'RETOURNEE',    'Retournée pour complétion'
        EN_CHIFFRAGE = 'EN_CHIFFRAGE', 'En cours de chiffrage'
        SOUMIS_DG    = 'SOUMIS_DG',   'Soumis à la DG'
        REVISION_DG  = 'REVISION_DG',  'En révision — Retour DG'
        DEVIS_VALIDE = 'DEVIS_VALIDE', 'Devis validé'
        TRANSMIS     = 'TRANSMIS',     'Transmis au client'
        ACCEPTE      = 'ACCEPTE',      'Accepté par le client'
        REFUSE_CLI   = 'REFUSE_CLI',   'Refusé par le client'
        ARCHIVE      = 'ARCHIVE',      'Archivé'

    class Urgence(models.TextChoices):
        STANDARD = 'STANDARD', 'Standard'
        URGENT   = 'URGENT',   'Urgent'
        CRITIQUE = 'CRITIQUE', 'Critique'

    class Jalon(models.TextChoices):
        ANALYSE  = 'ANALYSE',  'Analyse en cours'
        CHIFFRAGE = 'CHIFFRAGE', 'Chiffrage en cours'
        REVISION  = 'REVISION',  'En révision interne'

    # Référence auto
    reference = models.CharField(max_length=30, unique=True, blank=True, verbose_name='Référence')

    # Informations générales
    client_nom          = models.CharField(max_length=200, verbose_name='Nom du client')
    client_ref_affaire  = models.CharField(max_length=100, blank=True, verbose_name='Référence affaire')
    description         = models.TextField(verbose_name='Description commerciale')
    delai_souhaite      = models.DateField(null=True, blank=True, verbose_name='Délai souhaité')
    urgence             = models.CharField(max_length=10, choices=Urgence.choices,
                                           default=Urgence.STANDARD, verbose_name='Urgence')

    # Détails techniques
    finitions            = models.TextField(blank=True, verbose_name='Finitions souhaitées')
    kits_references      = models.TextField(blank=True, verbose_name='Kits / références produits')
    quantites_estimees   = models.TextField(blank=True, verbose_name='Quantités estimées')
    contraintes_techniques = models.TextField(blank=True, verbose_name='Contraintes techniques')
    commentaires         = models.TextField(blank=True, verbose_name='Commentaires libres')

    # Workflow
    statut = models.CharField(max_length=20, choices=Statut.choices,
                               default=Statut.EN_ATTENTE, verbose_name='Statut')
    jalon  = models.CharField(max_length=20, choices=Jalon.choices,
                               blank=True, verbose_name='Jalon Méthodes')

    # Acteurs
    commercial = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='chiffrages_soumis', verbose_name='Commercial',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='chiffrages_assignes', verbose_name='Chiffreur assigné',
    )
    validated_by_dc = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='chiffrages_valides_dc', verbose_name='Validé par DC',
    )
    validated_by_dg = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='chiffrages_valides_dg', verbose_name='Validé par DG',
    )

    # Lien CRM (opportunité d'origine)
    lead = models.ForeignKey(
        'crm.Lead', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='chiffrages', verbose_name='Opportunité CRM',
    )

    # Résultat financier (rempli par Méthodes, visible commercial qu'après validation DG)
    montant_ht = models.DecimalField(max_digits=14, decimal_places=2,
                                     null=True, blank=True, verbose_name='Montant HT (MAD)')

    # Timestamps
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)
    validated_dc_at    = models.DateTimeField(null=True, blank=True)
    validated_dg_at    = models.DateTimeField(null=True, blank=True)
    transmis_client_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Demande de chiffrage'
        verbose_name_plural = 'Demandes de chiffrage'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['statut']),
            models.Index(fields=['commercial']),
            models.Index(fields=['urgence']),
        ]

    def __str__(self):
        return f'{self.reference} — {self.client_nom}'

    def save(self, *args, **kwargs):
        if not self.reference:
            year = timezone.now().year
            count = DemandeChiffrage.objects.filter(
                reference__startswith=f'CHF-{year}-'
            ).count()
            self.reference = f'CHF-{year}-{count + 1:03d}'
        super().save(*args, **kwargs)

    @property
    def is_retard(self):
        if not self.delai_souhaite:
            return False
        closed = {
            self.Statut.DEVIS_VALIDE, self.Statut.TRANSMIS,
            self.Statut.ACCEPTE, self.Statut.REFUSE_CLI, self.Statut.ARCHIVE,
        }
        if self.statut in closed:
            return False
        return timezone.now().date() > self.delai_souhaite

    @property
    def can_commercial_edit(self):
        return self.statut in (
            self.Statut.EN_ATTENTE,
            self.Statut.REJETEE,
            self.Statut.RETOURNEE,
        )

    @property
    def montant_visible_commercial(self):
        """Le montant n'est visible par le commercial qu'après validation DG."""
        return self.statut in (
            self.Statut.DEVIS_VALIDE, self.Statut.TRANSMIS,
            self.Statut.ACCEPTE, self.Statut.REFUSE_CLI,
        )

    def get_statut_color(self):
        colors = {
            'EN_ATTENTE':   'amber',
            'VALIDEE_DC':   'blue',
            'REJETEE':      'red',
            'RETOURNEE':    'orange',
            'EN_CHIFFRAGE': 'indigo',
            'SOUMIS_DG':    'purple',
            'REVISION_DG':  'orange',
            'DEVIS_VALIDE': 'foret',
            'TRANSMIS':     'foret',
            'ACCEPTE':      'foret',
            'REFUSE_CLI':   'red',
            'ARCHIVE':      'ardoise',
        }
        return colors.get(self.statut, 'ardoise')


class FichierChiffrage(models.Model):
    """Fichier joint à une demande (plan, fiche technique, devis…)."""

    demande     = models.ForeignKey(DemandeChiffrage, on_delete=models.CASCADE,
                                    related_name='fichiers')
    fichier     = models.FileField(upload_to=chiffrage_file_path)
    nom         = models.CharField(max_length=255)
    version     = models.CharField(max_length=20, default='1.0')
    taille      = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, related_name='chiffrage_fichiers')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_internal = models.BooleanField(default=False,
                                      verbose_name='Interne (invisible commercial)')
    is_devis    = models.BooleanField(default=False,
                                      verbose_name='Fichier devis final')

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.nom} v{self.version}'

    def save(self, *args, **kwargs):
        if self.fichier and not self.taille:
            self.taille = self.fichier.size
        super().save(*args, **kwargs)

    @property
    def taille_human(self):
        s = self.taille
        for unit in ['o', 'Ko', 'Mo', 'Go']:
            if s < 1024:
                return f'{s:.1f} {unit}'
            s /= 1024
        return f'{s:.1f} To'

    @property
    def ext(self):
        return os.path.splitext(self.fichier.name)[1].lower().lstrip('.') if self.fichier else ''


class MessageFil(models.Model):
    """Message dans le fil de discussion d'une demande."""

    demande     = models.ForeignKey(DemandeChiffrage, on_delete=models.CASCADE,
                                    related_name='messages')
    auteur      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, related_name='chiffrage_messages')
    contenu     = models.TextField()
    fichier     = models.FileField(upload_to=message_file_path, null=True, blank=True)
    nom_fichier = models.CharField(max_length=255, blank=True)
    is_internal = models.BooleanField(default=False,
                                      verbose_name='Note interne (invisible commercial)')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Msg {self.pk} — {self.demande.reference}'


class HistoriqueAction(models.Model):
    """Traçabilité immuable — chaque action sur une demande."""

    demande        = models.ForeignKey(DemandeChiffrage, on_delete=models.CASCADE,
                                       related_name='historique')
    auteur         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                       null=True, related_name='chiffrage_historique')
    action         = models.CharField(max_length=150)
    detail         = models.TextField(blank=True)
    ancien_statut  = models.CharField(max_length=20, blank=True)
    nouveau_statut = models.CharField(max_length=20, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def save(self, *args, **kwargs):
        if self.pk:
            return  # immuable
        super().save(*args, **kwargs)

    def __str__(self):
        return f'[{self.created_at:%d/%m %H:%M}] {self.action}'


class DemandeModification(models.Model):
    """Demande de modification soumise par le commercial en cours de chiffrage."""

    class Statut(models.TextChoices):
        EN_ATTENTE = 'EN_ATTENTE', "En attente d'arbitrage"
        ACCEPTEE   = 'ACCEPTEE',   'Acceptée'
        REFUSEE    = 'REFUSEE',    'Refusée'

    demande       = models.ForeignKey(DemandeChiffrage, on_delete=models.CASCADE,
                                      related_name='demandes_modification')
    soumis_par    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                      null=True, related_name='modifications_soumises')
    nature        = models.TextField(verbose_name='Nature de la modification')
    justification = models.TextField(verbose_name='Justification')
    urgence       = models.CharField(max_length=10,
                                     choices=DemandeChiffrage.Urgence.choices,
                                     default=DemandeChiffrage.Urgence.STANDARD)
    statut        = models.CharField(max_length=10, choices=Statut.choices,
                                     default=Statut.EN_ATTENTE)
    traite_par    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                      null=True, blank=True,
                                      related_name='modifications_traitees')
    motif_refus   = models.TextField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    traite_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
