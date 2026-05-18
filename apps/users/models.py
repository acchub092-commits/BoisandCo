from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Utilisateur Bois&Co.
    Étend AbstractUser avec un rôle métier et des infos de contact.
    Les modèles détaillés sont générés à l'étape 4.
    """

    class Role(models.TextChoices):
        ADMIN      = 'ADMIN',      'Administrateur'
        DIRECTEUR  = 'DIRECTEUR',  'Directeur Général (DG)'
        MANAGER    = 'MANAGER',    'Directeur Commercial (DC)'
        ESTIMATEUR = 'ESTIMATEUR', 'Méthodes / Estimateur'
        COMMERCIAL = 'COMMERCIAL', 'Commercial'
        ADV        = 'ADV',        'ADV'
        ATELIER    = 'ATELIER',    'Usine'
        CHAUFFEUR  = 'CHAUFFEUR',  'Logistique'
        POSEUR     = 'POSEUR',     'Poseur'
        FINANCE    = 'FINANCE',    'Finance'
        SAV        = 'SAV',        'SAV'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.MANAGER,
        verbose_name='Rôle',
    )
    phone = models.CharField(max_length=20, blank=True, verbose_name='Téléphone')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    is_active_employee = models.BooleanField(default=True, verbose_name='Employé actif')

    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f'{self.get_full_name() or self.username} ({self.get_role_display()})'

    @property
    def is_manager_or_above(self):
        return self.is_superuser or self.role in (self.Role.DIRECTEUR, self.Role.MANAGER)

    @property
    def can_assign_tasks(self):
        return self.is_superuser or self.role in (self.Role.DIRECTEUR, self.Role.MANAGER, self.Role.ESTIMATEUR)
