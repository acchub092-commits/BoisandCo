import apps.documents.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('projects', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        migrations.CreateModel(
            name='DocumentCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Nom')),
                ('slug', models.SlugField(max_length=100, unique=True)),
                ('icon', models.CharField(
                    blank=True, max_length=50,
                    help_text="Nom d'icône (ex: folder, file-text)",
                )),
                ('order', models.PositiveSmallIntegerField(default=0)),
                ('parent', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='children',
                    to='documents.documentcategory',
                    verbose_name='Catégorie parente',
                )),
            ],
            options={
                'verbose_name': 'Catégorie de document',
                'verbose_name_plural': 'Catégories de documents',
                'ordering': ['order', 'name'],
            },
        ),

        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Nom du document')),
                ('file', models.FileField(
                    upload_to=apps.documents.models.document_upload_path,
                    verbose_name='Fichier',
                )),
                ('file_size', models.PositiveIntegerField(default=0, verbose_name='Taille (octets)')),
                ('file_type', models.CharField(
                    choices=[
                        ('pdf',   'PDF'),
                        ('word',  'Word'),
                        ('excel', 'Excel'),
                        ('image', 'Image'),
                        ('cad',   'CAO/DAO'),
                        ('other', 'Autre'),
                    ],
                    default='other',
                    max_length=10,
                    verbose_name='Type de fichier',
                )),
                ('version', models.CharField(default='1.0', max_length=20, verbose_name='Version')),
                ('is_latest', models.BooleanField(default=True, verbose_name='Version courante')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('category', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='documents',
                    to='documents.documentcategory',
                    verbose_name='Catégorie',
                )),
                ('previous_version', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='next_versions',
                    to='documents.document',
                    verbose_name='Version précédente',
                )),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='documents',
                    to='projects.project',
                    verbose_name='Projet',
                )),
                ('uploaded_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='uploaded_documents',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Déposé par',
                )),
            ],
            options={
                'verbose_name': 'Document',
                'verbose_name_plural': 'Documents',
                'ordering': ['-uploaded_at'],
            },
        ),

        migrations.AddIndex(
            model_name='document',
            index=models.Index(
                fields=['project', 'category'],
                name='documents_doc_proj_cat_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='document',
            index=models.Index(
                fields=['is_latest'],
                name='documents_doc_latest_idx',
            ),
        ),
    ]
