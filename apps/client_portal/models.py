"""
Portail client — accès sécurisé par token UUID sans compte utilisateur.
URL : /suivi/<token>/
"""
import uuid
from django.db import models
from django.urls import reverse
from django.utils import timezone


class ClientToken(models.Model):
    """
    Token d'accès unique lié à un projet.
    Permet au client de suivre l'avancement sans créer de compte.
    """
    project = models.OneToOneField(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='client_token',
        verbose_name='Projet',
    )
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name='Token',
    )
    is_active = models.BooleanField(default=True, verbose_name='Actif')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Expiration',
        help_text='Laisser vide pour ne pas expirer.',
    )
    last_accessed = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Dernier accès',
    )
    access_count = models.PositiveIntegerField(
        default=0, verbose_name='Nb accès',
    )

    # Visibilité — champs du projet visibles par le client
    show_phases = models.BooleanField(default=True, verbose_name='Afficher les phases')
    show_tasks = models.BooleanField(default=False, verbose_name='Afficher les tâches')
    show_documents = models.BooleanField(default=True, verbose_name='Afficher les documents')

    class Meta:
        verbose_name = 'Token client'
        verbose_name_plural = 'Tokens clients'

    def __str__(self):
        return f'Token {self.project.reference} ({self.token})'

    def get_absolute_url(self):
        return reverse('client_portal:portal', kwargs={'token': str(self.token)})

    @property
    def is_valid(self):
        """True si le token est actif et non expiré."""
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    def record_access(self):
        """Enregistre un accès (appelé à chaque visite du portail)."""
        self.last_accessed = timezone.now()
        self.access_count += 1
        self.save(update_fields=['last_accessed', 'access_count'])

    def regenerate(self):
        """Génère un nouveau token (révoque l'ancien)."""
        self.token = uuid.uuid4()
        self.save(update_fields=['token'])
