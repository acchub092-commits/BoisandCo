"""
Modèles de l'app projects.
Hiérarchie : ProjectTemplate → Project → Phase → Task → TaskAssignment
             Project → ProjectMember (équipe)
             Task    → TaskComment   (commentaires + pièces jointes)
"""
import os
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# Séquençage standard Bois&Co (18 étapes — source : Gantt interne avril 2026)
# (numero, partie, nom, owner_label, estimated_days)
# ---------------------------------------------------------------------------
ETAPES_BOISANDCO = [
    (1,  'A', 'Visites commerciales',        'Commercial',       3),
    (2,  'A', 'Création opportunité',         'Commercial',       2),
    (3,  'A', 'Qualification du projet',      'DC + Commercial',  3),
    (4,  'A', 'Etude & chiffrage',            'BE',              14),
    (5,  'A', "Validation de l'offre",        'BE + DG',          3),
    (6,  'A', "Envoi de l'offre",             'Commercial',       2),
    (7,  'A', 'Réception bon de commande',    'ADV',              7),
    (8,  'B', 'Création dossier projet',      'ADV',              3),
    (9,  'B', 'Etudes techniques',            'BE Méthodes',     14),
    (10, 'B', 'Lancement production',         'Production',       7),
    (11, 'B', 'Contrôle qualité',            'Production',       5),
    (12, 'B', 'Livraison chantier',           'Logistique',       3),
    (13, 'B', 'Installation & pose',          'Equipe pose',     14),
    (14, 'B', 'Décompte chantier',            'Pose + ADV',       5),
    (15, 'C', 'Facturation',                  'ADV + Finance',    7),
    (16, 'C', 'Réception finale / clôture',  'ADV + Pose',       3),
    (17, 'C', 'SAV',                          'Pose',            30),
    (18, 'C', 'Clôture & archivage',          'ADV',              2),
]

PARTIE_LABELS = {
    'A': 'Pipeline commercial',
    'B': 'Gestion de projet',
    'C': 'Facturation & SAV',
}

# ---------------------------------------------------------------------------
# Gabarits (templates réutilisables)
# ---------------------------------------------------------------------------

class ProjectTemplate(models.Model):
    """Gabarit de projet réutilisable — définit phases et tâches types."""

    name = models.CharField(max_length=200, verbose_name='Nom du gabarit')
    description = models.TextField(blank=True, verbose_name='Description')
    is_active = models.BooleanField(default=True, verbose_name='Actif')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_templates',
        verbose_name='Créé par',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Gabarit de projet'
        verbose_name_plural = 'Gabarits de projet'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def phases_count(self):
        return self.phase_templates.count()

    @property
    def tasks_count(self):
        return sum(p.task_templates.count() for p in self.phase_templates.all())


class PhaseTemplate(models.Model):
    """Phase type appartenant à un gabarit."""

    template = models.ForeignKey(
        ProjectTemplate,
        on_delete=models.CASCADE,
        related_name='phase_templates',
        verbose_name='Gabarit',
    )
    name = models.CharField(max_length=200, verbose_name='Nom de la phase')
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')
    estimated_days = models.PositiveIntegerField(
        default=0, verbose_name='Durée estimée (jours)'
    )
    partie = models.CharField(max_length=1, blank=True, verbose_name='Partie (A/B/C)')
    owner_label = models.CharField(max_length=100, blank=True, verbose_name='Responsable')

    class Meta:
        verbose_name = 'Phase type'
        verbose_name_plural = 'Phases types'
        ordering = ['order']

    def __str__(self):
        return f'{self.template.name} › {self.name}'


class TaskTemplate(models.Model):
    """Tâche type appartenant à une phase type."""

    class RequiredRole(models.TextChoices):
        ANY = 'ANY', 'N\'importe quel rôle'
        DIRECTEUR = 'DIRECTEUR', 'Directeur'
        MANAGER = 'MANAGER', 'Manager'
        ESTIMATEUR = 'ESTIMATEUR', 'Estimateur'
        ATELIER = 'ATELIER', 'Atelier'
        CHAUFFEUR = 'CHAUFFEUR', 'Chauffeur'
        POSEUR = 'POSEUR', 'Poseur'

    phase = models.ForeignKey(
        PhaseTemplate,
        on_delete=models.CASCADE,
        related_name='task_templates',
        verbose_name='Phase type',
    )
    name = models.CharField(max_length=200, verbose_name='Nom de la tâche')
    description = models.TextField(blank=True, verbose_name='Description')
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')
    required_role = models.CharField(
        max_length=20,
        choices=RequiredRole.choices,
        default=RequiredRole.ANY,
        verbose_name='Rôle requis',
    )
    estimated_hours = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        verbose_name='Heures estimées',
    )

    class Meta:
        verbose_name = 'Tâche type'
        verbose_name_plural = 'Tâches types'
        ordering = ['order']

    def __str__(self):
        return f'{self.phase.name} › {self.name}'


# ---------------------------------------------------------------------------
# Projet
# ---------------------------------------------------------------------------

class Project(models.Model):
    """Projet Bois&Co avec cycle de vie complet."""

    class Status(models.TextChoices):
        AVANT_VENTE = 'AVANT_VENTE', 'Avant-vente'
        ETUDE       = 'ETUDE',       'Étude'
        PRODUCTION  = 'PRODUCTION',  'Production'
        LOGISTIQUE  = 'LOGISTIQUE',  'Logistique'
        POSE        = 'POSE',        'Pose'
        CLOTURE     = 'CLOTURE',     'Clôture'

    # Identité
    reference = models.CharField(
        max_length=20, unique=True, verbose_name='Référence',
        help_text='Généré automatiquement (ex: BC-2024-001)',
    )
    name = models.CharField(max_length=300, verbose_name='Intitulé du projet')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVANT_VENTE,
        verbose_name='Statut',
    )

    # Client
    client_name = models.CharField(max_length=200, verbose_name='Nom du client')
    client_email = models.EmailField(blank=True, verbose_name='Email client')
    client_phone = models.CharField(max_length=20, blank=True, verbose_name='Tél. client')
    address = models.TextField(blank=True, verbose_name='Adresse chantier')

    # Demande de chiffrage à l'origine du projet (auto-créé à la validation DG)
    demande_chiffrage = models.OneToOneField(
        'chiffrage.DemandeChiffrage',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='projet',
        verbose_name='Demande de chiffrage',
    )

    # Gabarit d'origine
    template = models.ForeignKey(
        ProjectTemplate,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='projects',
        verbose_name='Gabarit utilisé',
    )

    # Responsables
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='managed_projects',
        verbose_name='Manager',
    )
    estimator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='estimated_projects',
        verbose_name='Estimateur',
    )

    # Dates
    start_date = models.DateField(null=True, blank=True, verbose_name='Date début')
    end_date = models.DateField(null=True, blank=True, verbose_name='Date fin prévue')
    actual_end_date = models.DateField(null=True, blank=True, verbose_name='Date fin réelle')

    # Financier
    budget = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        verbose_name='Budget (MAD)',
    )

    # Document de commande initial (marché / bon de commande)
    initial_order = models.FileField(
        upload_to='projets/commandes/',
        blank=True, null=True,
        verbose_name='Commande / Marché initial',
        help_text='PDF, Word ou image du marché ou bon de commande signé.',
    )

    # Chef de projet
    chef_de_projet = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='projets_diriges',
        verbose_name='Chef de projet',
    )
    chef_designe_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='projets_designes',
        verbose_name='Désigné par',
    )
    chef_designe_le = models.DateTimeField(null=True, blank=True, verbose_name='Désigné le')
    chef_valide_par_admin = models.BooleanField(default=False, verbose_name='Validé par admin')
    chef_valide_le = models.DateTimeField(null=True, blank=True, verbose_name='Validé le')

    # Notes
    notes = models.TextField(blank=True, verbose_name='Notes internes')

    # Méta
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_projects',
        verbose_name='Créé par',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Projet'
        verbose_name_plural = 'Projets'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['reference']),
            models.Index(fields=['manager']),
        ]

    def __str__(self):
        return f'[{self.reference}] {self.name}'

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._generate_reference()
        super().save(*args, **kwargs)

    def _generate_reference(self):
        year = timezone.now().year
        last = (
            Project.objects.filter(reference__startswith=f'BC-{year}-')
            .order_by('reference')
            .values_list('reference', flat=True)
            .last()
        )
        if last:
            seq = int(last.split('-')[-1]) + 1
        else:
            seq = 1
        return f'BC-{year}-{seq:03d}'

    @property
    def progress(self):
        """Avancement global : moyenne de l'avancement de chaque phase."""
        phases = list(self.phases.values_list('progress', flat=True))
        if not phases:
            return 0
        return round(sum(phases) / len(phases))

    @property
    def is_closed(self):
        return self.status == self.Status.CLOTURE

    def create_from_template(self, template: ProjectTemplate):
        """Instancie phases et tâches depuis un gabarit."""
        phases_tmpl = list(template.phase_templates.order_by('order'))
        first_order = phases_tmpl[0].order if phases_tmpl else 0
        for pt in phases_tmpl:
            phase = Phase.objects.create(
                project=self,
                name=pt.name,
                order=pt.order,
                estimated_days=pt.estimated_days,
                partie=pt.partie,
                owner_label=pt.owner_label,
                is_active=(pt.order == first_order),
            )
            tasks_tmpl = list(pt.task_templates.order_by('order'))
            first_task = tasks_tmpl[0].order if tasks_tmpl else None
            for tt in tasks_tmpl:
                Task.objects.create(
                    phase=phase,
                    name=tt.name,
                    description=tt.description,
                    order=tt.order,
                    required_role=tt.required_role,
                    estimated_hours=tt.estimated_hours,
                    status=(
                        Task.Status.ACTIVE
                        if pt.order == first_order and tt.order == first_task
                        else Task.Status.EN_ATTENTE
                    ),
                )

    @classmethod
    def creer_depuis_chiffrage(cls, demande, validated_by):
        """Crée un projet avec le séquençage standard Bois&Co depuis une demande validée DG."""
        from datetime import timedelta
        project = cls.objects.create(
            name=f'{demande.client_nom} — {demande.reference}',
            client_name=demande.client_nom,
            status=cls.Status.ETUDE,
            manager=validated_by,
            budget=demande.montant_ht,
            demande_chiffrage=demande,
            created_by=validated_by,
        )
        start = timezone.now().date()
        for numero, partie, nom, owner, jours in ETAPES_BOISANDCO:
            end = start + timedelta(days=jours - 1)
            Phase.objects.create(
                project=project,
                name=nom,
                order=numero,
                partie=partie,
                owner_label=owner,
                estimated_days=jours,
                planned_start=start,
                planned_end=end,
                is_active=(numero == 1),
                is_completed=(numero <= 4),  # étapes 1-4 déjà réalisées via chiffrage
            )
            start = end + timedelta(days=1)
        return project


# ---------------------------------------------------------------------------
# Phase
# ---------------------------------------------------------------------------

class Phase(models.Model):
    """Phase d'un projet (ex: Conception, Fabrication, Pose…)."""

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='phases',
        verbose_name='Projet',
    )
    name = models.CharField(max_length=200, verbose_name='Nom de la phase')
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')
    estimated_days = models.PositiveIntegerField(
        default=0, verbose_name='Durée estimée (jours)'
    )
    partie = models.CharField(max_length=1, blank=True, verbose_name='Partie (A/B/C)')
    owner_label = models.CharField(max_length=100, blank=True, verbose_name='Responsable')
    planned_start = models.DateField(null=True, blank=True, verbose_name='Début prévu')
    planned_end = models.DateField(null=True, blank=True, verbose_name='Fin prévue')
    is_active = models.BooleanField(default=False, verbose_name='Phase active')
    is_completed = models.BooleanField(default=False, verbose_name='Phase terminée')
    progress = models.PositiveSmallIntegerField(default=0, verbose_name='Avancement (%)')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Phase'
        verbose_name_plural = 'Phases'
        ordering = ['order']
        unique_together = [['project', 'order']]

    def __str__(self):
        return f'{self.project.reference} › {self.name}'

    def activate(self):
        """Démarre cette phase."""
        if not self.is_active:
            self.is_active = True
            self.started_at = timezone.now()
            self.save(update_fields=['is_active', 'started_at'])
            # Activer la première tâche
            first_task = self.tasks.filter(
                status=Task.Status.EN_ATTENTE
            ).order_by('order').first()
            if first_task:
                first_task.activate()

    def complete(self):
        """Clôture cette phase et active la suivante."""
        self.is_completed = True
        self.is_active = False
        self.completed_at = timezone.now()
        self.save(update_fields=['is_completed', 'is_active', 'completed_at'])

        next_phase = Phase.objects.filter(
            project=self.project,
            order=self.order + 1,
            is_active=False,
            is_completed=False,
        ).first()
        if next_phase:
            next_phase.activate()


# ---------------------------------------------------------------------------
# Tâche
# ---------------------------------------------------------------------------

class Task(models.Model):
    """Tâche avec workflow domino : quand 100% → active la tâche suivante."""

    class Status(models.TextChoices):
        EN_ATTENTE = 'EN_ATTENTE', 'En attente'
        ACTIVE     = 'ACTIVE',     'Active'
        EN_COURS   = 'EN_COURS',   'En cours'
        TERMINEE   = 'TERMINEE',   'Terminée'
        BLOQUEE    = 'BLOQUEE',    'Bloquée'

    class RequiredRole(models.TextChoices):
        ANY        = 'ANY',        'N\'importe quel rôle'
        DIRECTEUR  = 'DIRECTEUR',  'Directeur'
        MANAGER    = 'MANAGER',    'Manager'
        ESTIMATEUR = 'ESTIMATEUR', 'Estimateur'
        ATELIER    = 'ATELIER',    'Atelier'
        CHAUFFEUR  = 'CHAUFFEUR',  'Chauffeur'
        POSEUR     = 'POSEUR',     'Poseur'

    phase = models.ForeignKey(
        Phase,
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name='Phase',
    )
    name = models.CharField(max_length=200, verbose_name='Nom de la tâche')
    description = models.TextField(blank=True, verbose_name='Description')
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.EN_ATTENTE,
        verbose_name='Statut',
    )
    progress = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Avancement (%)',
        help_text='0–100. Quand 100 → déclenche la tâche suivante (workflow domino).',
    )
    required_role = models.CharField(
        max_length=20,
        choices=RequiredRole.choices,
        default=RequiredRole.ANY,
        verbose_name='Rôle requis',
    )
    estimated_hours = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        verbose_name='Heures estimées',
    )
    actual_hours = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        verbose_name='Heures réelles',
    )
    due_date = models.DateField(null=True, blank=True, verbose_name='Échéance')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, verbose_name='Notes')

    class Meta:
        verbose_name = 'Tâche'
        verbose_name_plural = 'Tâches'
        ordering = ['order']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['phase', 'order']),
        ]

    def __str__(self):
        return f'{self.phase} › {self.name}'

    def activate(self):
        """Passe la tâche à ACTIVE."""
        self.status = self.Status.ACTIVE
        if not self.started_at:
            self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])

    def set_progress(self, value: int):
        """
        Met à jour l'avancement et déclenche le domino si 100%.
        Appeler cette méthode plutôt que de modifier `progress` directement.
        """
        self.progress = max(0, min(100, value))

        if self.progress == 100:
            self._complete_and_trigger_next()
        elif self.progress > 0 and self.status == self.Status.ACTIVE:
            self.status = self.Status.EN_COURS
            self.save(update_fields=['progress', 'status'])
        else:
            self.save(update_fields=['progress'])

    def _complete_and_trigger_next(self):
        """Clôture la tâche et active la suivante dans la phase (domino)."""
        self.status = self.Status.TERMINEE
        self.completed_at = timezone.now()
        self.save(update_fields=['progress', 'status', 'completed_at'])

        # Chercher la tâche suivante dans la même phase
        next_task = Task.objects.filter(
            phase=self.phase,
            order__gt=self.order,
            status=self.Status.EN_ATTENTE,
        ).order_by('order').first()

        if next_task:
            next_task.activate()
        else:
            # Plus de tâches dans la phase → vérifier si phase terminée
            remaining = Task.objects.filter(
                phase=self.phase,
            ).exclude(status=self.Status.TERMINEE).count()
            if remaining == 0:
                self.phase.complete()


# ---------------------------------------------------------------------------
# Affectation Smart Casting
# ---------------------------------------------------------------------------

class TaskAssignment(models.Model):
    """
    Affectation d'un utilisateur à une tâche (Smart Casting).
    Le système suggère automatiquement les utilisateurs selon le rôle requis.
    """

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name='Tâche',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='task_assignments',
        verbose_name='Utilisateur',
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='given_assignments',
        verbose_name='Affecté par',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_primary = models.BooleanField(
        default=True,
        verbose_name='Responsable principal',
    )

    class Meta:
        verbose_name = 'Affectation'
        verbose_name_plural = 'Affectations'
        unique_together = [['task', 'user']]
        ordering = ['-is_primary', 'assigned_at']

    def __str__(self):
        return f'{self.task.name} → {self.user}'


# ---------------------------------------------------------------------------
# Équipe projet
# ---------------------------------------------------------------------------

class ProjectMember(models.Model):
    """Membre de l'équipe affecté à un projet (en plus du manager/estimateur)."""

    class ProjectRole(models.TextChoices):
        ADMIN      = 'ADMIN',      'Admin projet'
        EDITEUR    = 'EDITEUR',    'Éditeur'
        VALIDATEUR = 'VALIDATEUR', 'Validateur'
        LECTEUR    = 'LECTEUR',    'Lecteur'

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='members',
        verbose_name='Projet',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_memberships',
        verbose_name='Utilisateur',
    )
    role = models.CharField(
        max_length=20,
        choices=ProjectRole.choices,
        default=ProjectRole.EDITEUR,
        verbose_name='Rôle sur le projet',
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='project_additions',
        verbose_name='Ajouté par',
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Membre projet'
        verbose_name_plural = 'Membres projet'
        unique_together = [['project', 'user']]
        ordering = ['user__last_name', 'user__first_name']

    def __str__(self):
        return f'{self.project.reference} ← {self.user} ({self.get_role_display()})'


# ---------------------------------------------------------------------------
# Commentaires de tâche
# ---------------------------------------------------------------------------

def task_attachment_path(instance, filename):
    """Stockage dans projets/<ref>/commentaires/<filename>."""
    ref = instance.task.phase.project.reference
    return os.path.join('projets', ref, 'commentaires', filename)


class TaskComment(models.Model):
    """Commentaire sur une tâche avec pièce jointe et/ou mémo vocal."""

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Tâche',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='task_comments',
        verbose_name='Auteur',
    )
    text = models.TextField(blank=True, verbose_name='Commentaire')
    attachment = models.FileField(
        upload_to=task_attachment_path,
        blank=True, null=True,
        verbose_name='Fichier joint',
    )
    audio = models.FileField(
        upload_to=task_attachment_path,
        blank=True, null=True,
        verbose_name='Mémo vocal',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Commentaire de tâche'
        verbose_name_plural = 'Commentaires de tâches'
        ordering = ['created_at']

    def __str__(self):
        return f'[{self.task}] {self.author} — {self.created_at:%d/%m/%Y %H:%M}'

    @property
    def attachment_basename(self):
        return os.path.basename(self.attachment.name) if self.attachment else None

    @property
    def audio_basename(self):
        return os.path.basename(self.audio.name) if self.audio else None


# ---------------------------------------------------------------------------
# Commentaires de phase (planning)
# ---------------------------------------------------------------------------

def phase_comment_path(instance, filename):
    """Stockage dans projets/<ref>/phases/<pk>/<filename>."""
    ref = instance.phase.project.reference
    return os.path.join('projets', ref, 'phases', str(instance.phase.pk), filename)


class PhaseComment(models.Model):
    """Commentaire sur une étape du planning (texte, pièce jointe, mémo vocal)."""

    phase = models.ForeignKey(
        Phase,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Phase',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='phase_comments',
        verbose_name='Auteur',
    )
    text = models.TextField(blank=True, verbose_name='Message')
    attachment = models.FileField(
        upload_to=phase_comment_path,
        blank=True, null=True,
        verbose_name='Pièce jointe',
    )
    audio = models.FileField(
        upload_to=phase_comment_path,
        blank=True, null=True,
        verbose_name='Mémo vocal',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Commentaire de phase'
        verbose_name_plural = 'Commentaires de phases'
        ordering = ['created_at']

    def __str__(self):
        return f'[{self.phase}] {self.author} — {self.created_at:%d/%m/%Y %H:%M}'

    @property
    def attachment_basename(self):
        return os.path.basename(self.attachment.name) if self.attachment else None

    @property
    def audio_basename(self):
        return os.path.basename(self.audio.name) if self.audio else None


# ---------------------------------------------------------------------------
# Chat projet (messagerie équipe)
# ---------------------------------------------------------------------------

def project_message_path(instance, filename):
    ref = instance.project.reference
    return os.path.join('projets', ref, 'chat', filename)


class ProjectMessage(models.Model):
    """Message de chat visible par toute l'équipe du projet."""

    project = models.ForeignKey(
        'Project',
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='Projet',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='project_messages',
        verbose_name='Auteur',
    )
    content = models.TextField(blank=True, verbose_name='Message')
    reply_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='replies',
        verbose_name='Réponse à',
    )
    attachment = models.FileField(
        upload_to=project_message_path,
        blank=True, null=True,
        verbose_name='Pièce jointe',
    )
    attachment_name = models.CharField(max_length=255, blank=True)
    audio = models.FileField(
        upload_to=project_message_path,
        blank=True, null=True,
        verbose_name='Mémo vocal',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Message projet'
        verbose_name_plural = 'Messages projet'

    def __str__(self):
        return f'[{self.project.reference}] {self.author} — {self.created_at:%d/%m %H:%M}'

    @property
    def attachment_basename(self):
        return os.path.basename(self.attachment.name) if self.attachment else None

    @property
    def audio_basename(self):
        return os.path.basename(self.audio.name) if self.audio else None


# ---------------------------------------------------------------------------
# Pose chantier
# ---------------------------------------------------------------------------

def pose_photo_path(instance, filename):
    ref = instance.project.reference
    return os.path.join('projets', ref, 'chantier', filename)


class InstallationPlan(models.Model):
    """Planning de pose associé à un projet."""

    project = models.OneToOneField(
        Project, on_delete=models.CASCADE,
        related_name='installation_plan', verbose_name='Projet',
    )
    chef_chantier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='chantiers_chef', verbose_name='Chef de chantier',
    )
    team_members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='pose_assignments', blank=True,
        verbose_name='Équipe de pose',
    )
    planned_start = models.DateField('Date début prévue', null=True, blank=True)
    planned_end   = models.DateField('Date fin prévue',   null=True, blank=True)
    notes         = models.TextField('Instructions chantier', blank=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Plan de pose'
        verbose_name_plural = 'Plans de pose'

    def __str__(self):
        return f'Pose — {self.project.reference}'


class InstallationReport(models.Model):
    """Rapport hebdomadaire de pose (avancement + incidents)."""

    project     = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name='installation_reports', verbose_name='Projet',
    )
    week_number = models.PositiveSmallIntegerField('Semaine')
    year        = models.PositiveSmallIntegerField('Année')
    date_report = models.DateField('Date du rapport', auto_now_add=True)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='pose_reports', verbose_name='Rédigé par',
    )

    progress_percent  = models.PositiveSmallIntegerField('Avancement (%)', default=0)
    notes             = models.TextField('Avancement / Travaux réalisés', blank=True)
    difficulties      = models.TextField('Difficultés rencontrées', blank=True)
    incident          = models.BooleanField('Incident signalé', default=False)
    incident_description = models.TextField('Description incident', blank=True)
    photo             = models.ImageField(
        'Photo chantier', upload_to=pose_photo_path, null=True, blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year', '-week_number']
        verbose_name = 'Rapport de pose'
        verbose_name_plural = 'Rapports de pose'
        unique_together = [['project', 'week_number', 'year']]

    def __str__(self):
        return f'{self.project.reference} — S{self.week_number}/{self.year}'


# ---------------------------------------------------------------------------
# Étapes projet (suivi chef de projet)
# ---------------------------------------------------------------------------

class ProjectStep(models.Model):
    """Étape de suivi gérée par le chef de projet."""

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='steps',
        verbose_name='Projet',
    )
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')
    name = models.CharField(max_length=200, verbose_name='Nom de l\'étape')
    description = models.TextField(blank=True, verbose_name='Description')
    responsables_roles = models.JSONField(
        default=list,
        verbose_name='Rôles responsables',
        help_text='Liste de codes de rôle ex: ["ADV","COMMERCIAL"]',
    )
    due_date = models.DateField(null=True, blank=True, verbose_name='Échéance')
    is_completed = models.BooleanField(default=False, verbose_name='Terminée')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Terminée le')
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='completed_steps',
        verbose_name='Terminée par',
    )

    class Meta:
        verbose_name = 'Étape projet'
        verbose_name_plural = 'Étapes projet'
        ordering = ['project', 'order']

    def __str__(self):
        return f'{self.project.reference} › {self.name}'


class StepComment(models.Model):
    """Commentaire sur une étape projet."""

    step = models.ForeignKey(
        ProjectStep,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Étape',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='step_comments',
        verbose_name='Auteur',
    )
    text = models.TextField(verbose_name='Commentaire')
    attachment = models.FileField(
        upload_to='projets/step_comments/',
        blank=True, null=True,
        verbose_name='Pièce jointe',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Commentaire d\'étape'
        verbose_name_plural = 'Commentaires d\'étapes'
        ordering = ['created_at']

    def __str__(self):
        return f'[{self.step}] {self.author} — {self.created_at:%d/%m/%Y}'


# ---------------------------------------------------------------------------
# Commentaires projet (fil de discussion global)
# ---------------------------------------------------------------------------

class ProjectComment(models.Model):
    """Commentaire global sur un projet (fil de discussion)."""

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='project_comments',
        verbose_name='Projet',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='project_comments_authored',
        verbose_name='Auteur',
    )
    text = models.TextField(verbose_name='Commentaire')
    attachment = models.FileField(
        upload_to='projets/comments/',
        blank=True, null=True,
        verbose_name='Pièce jointe',
    )
    audio = models.FileField(
        upload_to='projets/comments/',
        blank=True, null=True,
        verbose_name='Mémo vocal',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Commentaire projet'
        verbose_name_plural = 'Commentaires projet'
        ordering = ['created_at']

    def __str__(self):
        return f'[{self.project.reference}] {self.author} — {self.created_at:%d/%m/%Y}'
