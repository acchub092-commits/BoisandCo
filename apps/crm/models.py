"""
Modèles CRM — Pipeline commercial Bois&Co.
Couvre les étapes 01 (Visite) → 07 (BC reçu) du cahier des charges.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


# Icônes SVG path par type d'activité (utilisées dans les templates)
ACTIVITY_ICONS = {
    'VISITE':  'M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z M15 11a3 3 0 11-6 0 3 3 0 016 0z',
    'APPEL':   'M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z',
    'REUNION': 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z',
    'DEMO':    'M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z',
    'RELANCE': 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15',
    'EMAIL':   'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z',
}


class Lead(models.Model):
    """
    Un lead représente une opportunité commerciale depuis le premier contact
    jusqu'à la signature du bon de commande (ou perte).
    """

    class Status(models.TextChoices):
        VISITE        = 'VISITE',        'Visite'
        OPPORTUNITE   = 'OPPORTUNITE',   'Opportunité'
        QUALIFICATION = 'QUALIFICATION', 'Qualification'
        CHIFFRAGE     = 'CHIFFRAGE',     'Chiffrage'
        OFFRE         = 'OFFRE',         'Offre envoyée'
        GAGNEE        = 'GAGNEE',        'Gagnée'
        PERDUE        = 'PERDUE',        'Perdue'

    # Ordre des colonnes pipeline (actif)
    PIPELINE_STAGES = [
        Status.VISITE, Status.OPPORTUNITE, Status.QUALIFICATION,
        Status.CHIFFRAGE, Status.OFFRE,
    ]

    class Potential(models.TextChoices):
        FAIBLE    = 'FAIBLE',    'Faible'
        MOYEN     = 'MOYEN',     'Moyen'
        IMPORTANT = 'IMPORTANT', 'Important'

    class Canal(models.TextChoices):
        APPEL_ENTRANT   = 'APPEL_ENTRANT',   'Appel entrant'
        PRESCRIPTION    = 'PRESCRIPTION',    'Prescription'
        SALON           = 'SALON',           'Salon / Expo'
        APPEL_OFFRE     = 'APPEL_OFFRE',     "Appel d'offre"
        RECOMMANDATION  = 'RECOMMANDATION',  'Recommandation'
        VISITE_TERRAIN  = 'VISITE_TERRAIN',  'Visite terrain'
        AUTRE           = 'AUTRE',           'Autre'

    class FluxType(models.TextChoices):
        COMMANDE = 'COMMANDE', 'Commande directe'
        MARCHE   = 'MARCHE',   'Marché (AO)'

    class Probability(models.TextChoices):
        LOW  = 'LOW',  '< 30 %'
        MED  = 'MED',  '30 – 70 %'
        HIGH = 'HIGH', '> 70 %'

    class LossReason(models.TextChoices):
        PRIX       = 'PRIX',       'Prix'
        DELAI      = 'DELAI',      'Délai'
        CONCURRENT = 'CONCURRENT', 'Concurrent retenu'
        ANNULE     = 'ANNULE',     'Projet annulé'
        TECHNIQUE  = 'TECHNIQUE',  'Faisabilité technique'
        AUTRE      = 'AUTRE',      'Autre'

    # ── Contact & identification ────────────────────────────────────
    contact_name = models.CharField('Contact', max_length=200)
    company      = models.CharField('Entreprise', max_length=200, blank=True)
    client_type  = models.CharField(
        'Type de client', max_length=100, blank=True,
        help_text='Promoteur, Hôtel, Particulier, Bureau...',
    )
    email = models.EmailField('Email', blank=True)
    phone = models.CharField('Téléphone', max_length=50, blank=True)

    # ── Projet ──────────────────────────────────────────────────────
    project_name = models.CharField('Nom du projet', max_length=200)
    location     = models.CharField('Localisation', max_length=200, blank=True)
    project_type = models.CharField(
        'Type de projet', max_length=100, blank=True,
        help_text='Résidentiel, Hôtel, Bureaux...',
    )
    products = models.CharField(
        'Produits concernés', max_length=300, blank=True,
        help_text='Portes, Placards, Cuisines...',
    )

    # ── Qualification commerciale ────────────────────────────────────
    potential     = models.CharField('Potentiel', max_length=20, choices=Potential.choices, default=Potential.MOYEN)
    canal_origine = models.CharField("Canal d'origine", max_length=30, choices=Canal.choices, blank=True)
    flux_type     = models.CharField('Type de flux', max_length=20, choices=FluxType.choices, blank=True)

    # ── Statut & relance ────────────────────────────────────────────
    status              = models.CharField('Statut', max_length=20, choices=Status.choices, default=Status.VISITE)
    next_followup_date  = models.DateField('Prochaine relance', null=True, blank=True)

    # ── Opportunité (étape 02) ───────────────────────────────────────
    budget_mad      = models.DecimalField('Budget (MAD)', max_digits=14, decimal_places=2, null=True, blank=True)
    nb_logements    = models.IntegerField('Nb logements / unités', null=True, blank=True)
    start_date_est  = models.DateField('Début estimé', null=True, blank=True)
    end_date_est    = models.DateField('Fin estimée', null=True, blank=True)
    probability     = models.CharField('Probabilité', max_length=10, choices=Probability.choices, blank=True)
    competitor      = models.CharField('Concurrent(s)', max_length=300, blank=True)
    strategic_comment = models.TextField('Commentaire stratégique', blank=True)

    # ── Offre commerciale (étape 06) ─────────────────────────────────
    offer_amount_ht   = models.DecimalField('Montant offre HT (MAD)', max_digits=14, decimal_places=2, null=True, blank=True)
    offer_sent_date   = models.DateField("Date d'envoi", null=True, blank=True)
    offer_validity_days = models.IntegerField('Validité (jours)', default=30)

    # ── Résultat ────────────────────────────────────────────────────
    loss_reason = models.CharField('Motif perte', max_length=20, choices=LossReason.choices, blank=True)
    loss_notes  = models.TextField('Notes perte', blank=True)

    # ── Assignation ─────────────────────────────────────────────────
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_leads', verbose_name='Assigné à',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='created_leads', verbose_name='Créé par',
    )

    # ── Workflow validation (DC valide les leads créés par les commerciaux) ──
    class WorkflowStatus(models.TextChoices):
        DRAFT              = 'DRAFT',              'Brouillon'
        PENDING_VALIDATION = 'PENDING_VALIDATION', 'En attente de validation'
        VALIDATED          = 'VALIDATED',          'Validée'

    class Source(models.TextChoices):
        DIRECTOR_ASSIGNED  = 'DIRECTOR_ASSIGNED',  'Assignée par le DC'
        COMMERCIAL_CREATED = 'COMMERCIAL_CREATED', 'Créée par commercial'

    workflow_status = models.CharField(
        'Statut workflow', max_length=30,
        choices=WorkflowStatus.choices, default=WorkflowStatus.VALIDATED,
    )
    source = models.CharField(
        'Source', max_length=30,
        choices=Source.choices, default=Source.DIRECTOR_ASSIGNED,
    )
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='validated_leads', verbose_name='Validé par',
    )
    validated_at = models.DateTimeField('Validé le', null=True, blank=True)

    # ── Détails besoins ──────────────────────────────────────────────
    detailed_needs   = models.TextField('Besoins détaillés', blank=True)
    technical_notes  = models.TextField('Notes techniques', blank=True)

    # ── Lien vers projet (quand gagné) ───────────────────────────────
    project = models.OneToOneField(
        'projects.Project',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lead', verbose_name='Dossier projet',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Lead'
        verbose_name_plural = 'Leads'
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.project_name} — {self.contact_name}'

    @property
    def is_active(self):
        return self.status not in (self.Status.GAGNEE, self.Status.PERDUE)

    @property
    def potential_color(self):
        return {
            self.Potential.FAIBLE:    'bg-ardoise-100 text-ardoise-600',
            self.Potential.MOYEN:     'bg-bois-100 text-bois-700',
            self.Potential.IMPORTANT: 'bg-foret-100 text-foret-700',
        }.get(self.potential, '')

    @property
    def offer_expiry_date(self):
        if self.offer_sent_date and self.offer_validity_days:
            from datetime import timedelta
            return self.offer_sent_date + timedelta(days=self.offer_validity_days)
        return None

    @property
    def is_offer_expired(self):
        exp = self.offer_expiry_date
        return exp and exp < timezone.now().date()


class LeadNote(models.Model):
    """Note / historique d'échange sur un lead."""
    lead       = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='notes')
    author     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    text       = models.TextField('Note')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Note lead'

    def __str__(self):
        return f'{self.lead} — {self.created_at:%d/%m/%Y}'


class Activity(models.Model):
    """
    Activité commerciale planifiée ou réalisée, liée à une opportunité.
    Sert de base à l'agenda partagé des commerciaux.
    """

    class Type(models.TextChoices):
        VISITE  = 'VISITE',  'Visite terrain'
        APPEL   = 'APPEL',   'Appel téléphonique'
        REUNION = 'REUNION', 'Réunion'
        DEMO    = 'DEMO',    'Démonstration'
        RELANCE = 'RELANCE', 'Relance'
        EMAIL   = 'EMAIL',   'Email'

    class Status(models.TextChoices):
        PLANIFIE = 'PLANIFIE', 'Planifié'
        REALISE  = 'REALISE',  'Réalisé'
        ANNULE   = 'ANNULE',   'Annulé'

    # Couleurs Tailwind par type
    TYPE_COLORS = {
        'VISITE':  ('bg-foret-100',  'text-foret-700',  'border-foret-200'),
        'APPEL':   ('bg-blue-100',   'text-blue-700',   'border-blue-200'),
        'REUNION': ('bg-purple-100', 'text-purple-700', 'border-purple-200'),
        'DEMO':    ('bg-bois-100',   'text-bois-700',   'border-bois-200'),
        'RELANCE': ('bg-amber-100',  'text-amber-700',  'border-amber-200'),
        'EMAIL':   ('bg-ardoise-100','text-ardoise-600','border-ardoise-200'),
    }

    lead          = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name='activities',
        null=True, blank=True, verbose_name='Opportunité',
    )
    activity_type = models.CharField(
        max_length=20, choices=Type.choices, verbose_name='Type',
    )
    subject       = models.CharField(max_length=200, verbose_name='Objet')
    planned_at    = models.DateTimeField(verbose_name='Date / heure prévue')
    duration_min  = models.PositiveSmallIntegerField(
        default=60, verbose_name='Durée (min)',
    )
    location      = models.CharField(max_length=200, blank=True, verbose_name='Lieu')
    assigned_to   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='crm_activities', verbose_name='Commercial',
    )
    status        = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.PLANIFIE, verbose_name='Statut',
    )
    compte_rendu  = models.TextField(blank=True, verbose_name='Compte rendu')
    created_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='created_crm_activities',
    )
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Activité CRM'
        verbose_name_plural = 'Activités CRM'
        ordering = ['planned_at']

    def __str__(self):
        return f'[{self.get_activity_type_display()}] {self.subject} — {self.planned_at:%d/%m/%Y}'

    @property
    def is_overdue(self):
        return (
            self.status == self.Status.PLANIFIE
            and self.planned_at < timezone.now()
        )

    @property
    def type_colors(self):
        return self.TYPE_COLORS.get(self.activity_type, ('bg-ardoise-100', 'text-ardoise-600', 'border-ardoise-200'))

    @property
    def icon_path(self):
        return ACTIVITY_ICONS.get(self.activity_type, '')


# ─────────────────────────────────────────────────────────────────────────────
# Rendez-vous / Appointment
# ─────────────────────────────────────────────────────────────────────────────

def appointment_document_path(instance, filename):
    import os, uuid
    ext = os.path.splitext(filename)[1].lower()
    return f'crm/appointments/{instance.appointment.lead_id}/{uuid.uuid4().hex}{ext}'


def lead_document_path(instance, filename):
    import os, uuid
    ext = os.path.splitext(filename)[1].lower()
    return f'crm/documents/{instance.lead_id}/{uuid.uuid4().hex}{ext}'


class Appointment(models.Model):
    """
    Rendez-vous structuré lié à un lead (opportunité).
    Plus riche que Activity : participants M2M, compte rendu, pièces jointes.
    """

    class AppointmentType(models.TextChoices):
        DECOUVERTE  = 'DECOUVERTE',  'Découverte'
        TECHNIQUE   = 'TECHNIQUE',   'Technique'
        PROPOSITION = 'PROPOSITION', 'Présentation offre'
        SUIVI       = 'SUIVI',       'Suivi'
        VISITE      = 'VISITE',      'Visite chantier'

    class Status(models.TextChoices):
        PLANIFIE   = 'PLANIFIE',   'Planifié'
        REALISE    = 'REALISE',    'Réalisé'
        ANNULE     = 'ANNULE',     'Annulé'
        REPORTE    = 'REPORTE',    'Reporté'

    lead             = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name='appointments',
        verbose_name='Opportunité',
    )
    title            = models.CharField('Titre', max_length=200)
    appointment_type = models.CharField(
        'Type', max_length=20, choices=AppointmentType.choices,
        default=AppointmentType.DECOUVERTE,
    )
    scheduled_at     = models.DateTimeField('Date / heure')
    duration_minutes = models.PositiveSmallIntegerField('Durée (min)', default=60)
    location         = models.CharField('Lieu', max_length=300, blank=True)
    attendees        = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True,
        related_name='crm_appointments', verbose_name='Participants',
    )
    status           = models.CharField(
        'Statut', max_length=20, choices=Status.choices, default=Status.PLANIFIE,
    )
    report           = models.TextField('Compte rendu', blank=True)
    report_written_at = models.DateTimeField('Compte rendu rédigé le', null=True, blank=True)
    created_by       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='created_appointments',
    )
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Rendez-vous'
        verbose_name_plural = 'Rendez-vous'
        ordering            = ['-scheduled_at']

    def __str__(self):
        return f'{self.get_appointment_type_display()} — {self.lead} ({self.scheduled_at:%d/%m/%Y})'

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('crm:appointment_detail', kwargs={'pk': self.pk})

    @property
    def is_overdue(self):
        return self.status == self.Status.PLANIFIE and self.scheduled_at < timezone.now()

    @property
    def status_color(self):
        return {
            self.Status.PLANIFIE: 'bg-blue-100 text-blue-700',
            self.Status.REALISE:  'bg-foret-100 text-foret-700',
            self.Status.ANNULE:   'bg-ardoise-100 text-ardoise-500',
            self.Status.REPORTE:  'bg-amber-100 text-amber-700',
        }.get(self.status, '')

    @property
    def type_icon(self):
        return {
            self.AppointmentType.DECOUVERTE:  'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z',
            self.AppointmentType.TECHNIQUE:   'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z',
            self.AppointmentType.PROPOSITION: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
            self.AppointmentType.SUIVI:       'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4',
            self.AppointmentType.VISITE:      'M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z M15 11a3 3 0 11-6 0 3 3 0 016 0z',
        }.get(self.appointment_type, '')


# ─────────────────────────────────────────────────────────────────────────────
# Documents liés aux leads / RDV
# ─────────────────────────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.jpg', '.jpeg', '.png', '.dwg', '.dxf'}
MAX_UPLOAD_SIZE    = 20 * 1024 * 1024  # 20 MB


class LeadDocument(models.Model):
    """Pièce jointe liée à une opportunité (plan, photo chantier, CdC, CR…)."""

    class DocType(models.TextChoices):
        PLAN          = 'PLAN',          'Plan'
        TECH_SPEC     = 'TECH_SPEC',     'Cahier des charges'
        PHOTO         = 'PHOTO',         'Photo chantier'
        MEETING_REPORT = 'MEETING_REPORT', 'Compte rendu'
        OFFRE         = 'OFFRE',         'Offre commerciale'
        OTHER         = 'OTHER',         'Autre'

    lead         = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name='documents',
        verbose_name='Opportunité',
    )
    appointment  = models.ForeignKey(
        Appointment, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='documents', verbose_name='RDV associé',
    )
    doc_type     = models.CharField(
        'Type', max_length=20, choices=DocType.choices, default=DocType.OTHER,
    )
    title        = models.CharField('Titre', max_length=200)
    description  = models.TextField('Description', blank=True)
    file         = models.FileField('Fichier', upload_to=lead_document_path)
    uploaded_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='uploaded_crm_docs',
    )
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Document lead'
        verbose_name_plural = 'Documents leads'
        ordering            = ['-created_at']

    def __str__(self):
        return f'{self.get_doc_type_display()} — {self.title}'

    @property
    def extension(self):
        import os
        return os.path.splitext(self.file.name)[1].lower() if self.file else ''

    @property
    def is_image(self):
        return self.extension in ('.jpg', '.jpeg', '.png', '.webp')

    @property
    def icon(self):
        icons = {
            '.pdf':  'M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z',
            '.dwg':  'M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7',
            '.docx': 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
            '.xlsx': 'M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z',
        }
        return icons.get(self.extension, 'M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13')


# ─────────────────────────────────────────────────────────────────────────────
# Journal d'activité structuré (log immuable)
# ─────────────────────────────────────────────────────────────────────────────

class LeadActivityLog(models.Model):
    """
    Journal d'événements immuable sur un lead.
    Distinct de Activity (agenda) : enregistre les actions système (validation,
    assignation, changement de statut, notes manuelles).
    """

    class LogType(models.TextChoices):
        NOTE           = 'NOTE',           'Note'
        APPEL          = 'APPEL',          'Appel'
        EMAIL          = 'EMAIL',          'Email'
        STATUS_CHANGE  = 'STATUS_CHANGE',  'Changement statut'
        ASSIGNMENT     = 'ASSIGNMENT',     'Attribution'
        VALIDATION     = 'VALIDATION',     'Validation'
        DOCUMENT_ADDED = 'DOCUMENT_ADDED', 'Document ajouté'
        RDV_ADDED      = 'RDV_ADDED',      'RDV planifié'
        RDV_DONE       = 'RDV_DONE',       'RDV réalisé'

    lead         = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name='activity_logs',
        verbose_name='Lead',
    )
    log_type     = models.CharField('Type', max_length=20, choices=LogType.choices)
    content      = models.TextField('Contenu')
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='crm_log_entries',
    )
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Log activité lead'
        verbose_name_plural = 'Logs activité leads'
        ordering            = ['-created_at']

    def __str__(self):
        return f'[{self.get_log_type_display()}] {self.lead} — {self.created_at:%d/%m/%Y}'

    @property
    def icon_color(self):
        return {
            self.LogType.NOTE:           ('text-ardoise-500',  'bg-ardoise-100'),
            self.LogType.APPEL:          ('text-blue-600',     'bg-blue-100'),
            self.LogType.EMAIL:          ('text-indigo-600',   'bg-indigo-100'),
            self.LogType.STATUS_CHANGE:  ('text-amber-600',    'bg-amber-100'),
            self.LogType.ASSIGNMENT:     ('text-purple-600',   'bg-purple-100'),
            self.LogType.VALIDATION:     ('text-foret-600',    'bg-foret-100'),
            self.LogType.DOCUMENT_ADDED: ('text-bois-600',     'bg-bois-100'),
            self.LogType.RDV_ADDED:      ('text-blue-600',     'bg-blue-100'),
            self.LogType.RDV_DONE:       ('text-foret-600',    'bg-foret-100'),
        }.get(self.log_type, ('text-ardoise-500', 'bg-ardoise-100'))
