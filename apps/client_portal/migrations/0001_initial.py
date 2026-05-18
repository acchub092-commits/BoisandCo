import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('projects', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClientToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(
                    default=uuid.uuid4,
                    editable=False,
                    unique=True,
                    verbose_name='Token',
                )),
                ('is_active', models.BooleanField(default=True, verbose_name='Actif')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(
                    blank=True, null=True,
                    help_text='Laisser vide pour ne pas expirer.',
                    verbose_name='Expiration',
                )),
                ('last_accessed', models.DateTimeField(
                    blank=True, null=True, verbose_name='Dernier accès',
                )),
                ('access_count', models.PositiveIntegerField(default=0, verbose_name='Nb accès')),
                ('show_phases', models.BooleanField(default=True, verbose_name='Afficher les phases')),
                ('show_tasks', models.BooleanField(default=False, verbose_name='Afficher les tâches')),
                ('show_documents', models.BooleanField(default=True, verbose_name='Afficher les documents')),
                ('project', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='client_token',
                    to='projects.project',
                    verbose_name='Projet',
                )),
            ],
            options={
                'verbose_name': 'Token client',
                'verbose_name_plural': 'Tokens clients',
            },
        ),
    ]
