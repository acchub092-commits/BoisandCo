"""
GED — Gestion Électronique de Documents.
Arborescence automatique : media/projets/<reference>/<categorie>/<fichier>
"""
import os
from django.db import models
from django.conf import settings
from django.utils.text import slugify


def document_upload_path(instance, filename):
    """
    Construit le chemin de stockage automatique :
    projets/BC-2024-001/plans/plan_facade_v2.pdf
    """
    project_ref = instance.project.reference if instance.project else 'sans-projet'
    category_slug = slugify(instance.category.name) if instance.category else 'divers'
    return os.path.join('projets', project_ref, category_slug, filename)


class DocumentCategory(models.Model):
    """
    Catégorie de documents avec arborescence parent/enfant.
    Exemples : Plans > Plans façade, Devis, PV de réception…
    """
    name = models.CharField(max_length=100, verbose_name='Nom')
    slug = models.SlugField(max_length=100, unique=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='children',
        verbose_name='Catégorie parente',
    )
    icon = models.CharField(
        max_length=50, blank=True,
        help_text='Nom d\'icône (ex: folder, file-text)',
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'Catégorie de document'
        verbose_name_plural = 'Catégories de documents'
        ordering = ['order', 'name']

    def __str__(self):
        if self.parent:
            return f'{self.parent.name} › {self.name}'
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def full_path(self):
        """Chemin complet avec ancêtres."""
        parts = [self.name]
        parent = self.parent
        while parent:
            parts.insert(0, parent.name)
            parent = parent.parent
        return ' / '.join(parts)


class Document(models.Model):
    """Document attaché à un projet avec versionnage et métadonnées."""

    class FileType(models.TextChoices):
        PDF    = 'pdf',   'PDF'
        WORD   = 'word',  'Word'
        EXCEL  = 'excel', 'Excel'
        IMAGE  = 'image', 'Image'
        CAD    = 'cad',   'CAO/DAO'
        OTHER  = 'other', 'Autre'

    # Rattachement
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='Projet',
    )
    category = models.ForeignKey(
        DocumentCategory,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='documents',
        verbose_name='Catégorie',
    )

    # Fichier
    name = models.CharField(max_length=255, verbose_name='Nom du document')
    file = models.FileField(
        upload_to=document_upload_path,
        verbose_name='Fichier',
    )
    file_size = models.PositiveIntegerField(
        default=0, verbose_name='Taille (octets)',
    )
    file_type = models.CharField(
        max_length=10,
        choices=FileType.choices,
        default=FileType.OTHER,
        verbose_name='Type de fichier',
    )

    # Versionnage
    version = models.CharField(
        max_length=20, default='1.0',
        verbose_name='Version',
    )
    is_latest = models.BooleanField(
        default=True,
        verbose_name='Version courante',
    )
    previous_version = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='next_versions',
        verbose_name='Version précédente',
    )

    # Méta
    description = models.TextField(blank=True, verbose_name='Description')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_documents',
        verbose_name='Déposé par',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['project', 'category']),
            models.Index(fields=['is_latest']),
        ]

    def __str__(self):
        return f'{self.name} (v{self.version})'

    def save(self, *args, **kwargs):
        # Calcul automatique de la taille et du type
        if self.file and not self.file_size:
            self.file_size = self.file.size
        if self.file and not self.file_type:
            self.file_type = self._detect_file_type()
        super().save(*args, **kwargs)

    def _detect_file_type(self):
        ext = os.path.splitext(self.file.name)[1].lower()
        mapping = {
            '.pdf':  self.FileType.PDF,
            '.doc':  self.FileType.WORD,
            '.docx': self.FileType.WORD,
            '.xls':  self.FileType.EXCEL,
            '.xlsx': self.FileType.EXCEL,
            '.png':  self.FileType.IMAGE,
            '.jpg':  self.FileType.IMAGE,
            '.jpeg': self.FileType.IMAGE,
            '.dwg':  self.FileType.CAD,
            '.dxf':  self.FileType.CAD,
        }
        return mapping.get(ext, self.FileType.OTHER)

    @property
    def file_size_human(self):
        """Taille lisible (ex: 2.4 Mo)."""
        size = self.file_size
        for unit in ['o', 'Ko', 'Mo', 'Go']:
            if size < 1024:
                return f'{size:.1f} {unit}'
            size /= 1024
        return f'{size:.1f} To'
