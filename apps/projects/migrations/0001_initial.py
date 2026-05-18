import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('users', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── Gabarits ────────────────────────────────────────────────

        migrations.CreateModel(
            name='ProjectTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Nom du gabarit')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('is_active', models.BooleanField(default=True, verbose_name='Actif')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_templates',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Créé par',
                )),
            ],
            options={
                'verbose_name': 'Gabarit de projet',
                'verbose_name_plural': 'Gabarits de projet',
                'ordering': ['name'],
            },
        ),

        migrations.CreateModel(
            name='PhaseTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Nom de la phase')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')),
                ('estimated_days', models.PositiveIntegerField(default=0, verbose_name='Durée estimée (jours)')),
                ('template', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='phase_templates',
                    to='projects.projecttemplate',
                    verbose_name='Gabarit',
                )),
            ],
            options={
                'verbose_name': 'Phase type',
                'verbose_name_plural': 'Phases types',
                'ordering': ['order'],
            },
        ),

        migrations.CreateModel(
            name='TaskTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Nom de la tâche')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')),
                ('required_role', models.CharField(
                    choices=[
                        ('ANY', "N'importe quel rôle"),
                        ('DIRECTEUR', 'Directeur'),
                        ('MANAGER', 'Manager'),
                        ('ESTIMATEUR', 'Estimateur'),
                        ('ATELIER', 'Atelier'),
                        ('CHAUFFEUR', 'Chauffeur'),
                        ('POSEUR', 'Poseur'),
                    ],
                    default='ANY',
                    max_length=20,
                    verbose_name='Rôle requis',
                )),
                ('estimated_hours', models.DecimalField(
                    decimal_places=2, default=0, max_digits=6,
                    verbose_name='Heures estimées',
                )),
                ('phase', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='task_templates',
                    to='projects.phasetemplate',
                    verbose_name='Phase type',
                )),
            ],
            options={
                'verbose_name': 'Tâche type',
                'verbose_name_plural': 'Tâches types',
                'ordering': ['order'],
            },
        ),

        # ── Projet ──────────────────────────────────────────────────

        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(
                    help_text='Généré automatiquement (ex: BC-2024-001)',
                    max_length=20,
                    unique=True,
                    verbose_name='Référence',
                )),
                ('name', models.CharField(max_length=300, verbose_name='Intitulé du projet')),
                ('status', models.CharField(
                    choices=[
                        ('AVANT_VENTE', 'Avant-vente'),
                        ('ETUDE', 'Étude'),
                        ('PRODUCTION', 'Production'),
                        ('LOGISTIQUE', 'Logistique'),
                        ('POSE', 'Pose'),
                        ('CLOTURE', 'Clôture'),
                    ],
                    default='AVANT_VENTE',
                    max_length=20,
                    verbose_name='Statut',
                )),
                ('client_name', models.CharField(max_length=200, verbose_name='Nom du client')),
                ('client_email', models.EmailField(blank=True, verbose_name='Email client')),
                ('client_phone', models.CharField(blank=True, max_length=20, verbose_name='Tél. client')),
                ('address', models.TextField(blank=True, verbose_name='Adresse chantier')),
                ('start_date', models.DateField(blank=True, null=True, verbose_name='Date début')),
                ('end_date', models.DateField(blank=True, null=True, verbose_name='Date fin prévue')),
                ('actual_end_date', models.DateField(blank=True, null=True, verbose_name='Date fin réelle')),
                ('budget', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12,
                    null=True, verbose_name='Budget (€)',
                )),
                ('notes', models.TextField(blank=True, verbose_name='Notes internes')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_projects',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Créé par',
                )),
                ('estimator', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='estimated_projects',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Estimateur',
                )),
                ('manager', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='managed_projects',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Manager',
                )),
                ('template', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='projects',
                    to='projects.projecttemplate',
                    verbose_name='Gabarit utilisé',
                )),
            ],
            options={
                'verbose_name': 'Projet',
                'verbose_name_plural': 'Projets',
                'ordering': ['-created_at'],
            },
        ),

        migrations.AddIndex(
            model_name='project',
            index=models.Index(fields=['status'], name='projects_pr_status_idx'),
        ),
        migrations.AddIndex(
            model_name='project',
            index=models.Index(fields=['reference'], name='projects_pr_ref_idx'),
        ),
        migrations.AddIndex(
            model_name='project',
            index=models.Index(fields=['manager'], name='projects_pr_manager_idx'),
        ),

        # ── Phase ───────────────────────────────────────────────────

        migrations.CreateModel(
            name='Phase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Nom de la phase')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')),
                ('estimated_days', models.PositiveIntegerField(default=0, verbose_name='Durée estimée (jours)')),
                ('is_active', models.BooleanField(default=False, verbose_name='Phase active')),
                ('is_completed', models.BooleanField(default=False, verbose_name='Phase terminée')),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='phases',
                    to='projects.project',
                    verbose_name='Projet',
                )),
            ],
            options={
                'verbose_name': 'Phase',
                'verbose_name_plural': 'Phases',
                'ordering': ['order'],
            },
        ),

        migrations.AlterUniqueTogether(
            name='phase',
            unique_together={('project', 'order')},
        ),

        # ── Tâche ───────────────────────────────────────────────────

        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Nom de la tâche')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')),
                ('status', models.CharField(
                    choices=[
                        ('EN_ATTENTE', 'En attente'),
                        ('ACTIVE', 'Active'),
                        ('EN_COURS', 'En cours'),
                        ('TERMINEE', 'Terminée'),
                        ('BLOQUEE', 'Bloquée'),
                    ],
                    default='EN_ATTENTE',
                    max_length=20,
                    verbose_name='Statut',
                )),
                ('progress', models.PositiveSmallIntegerField(
                    default=0,
                    help_text='0–100. Quand 100 → déclenche la tâche suivante (workflow domino).',
                    verbose_name='Avancement (%)',
                )),
                ('required_role', models.CharField(
                    choices=[
                        ('ANY', "N'importe quel rôle"),
                        ('DIRECTEUR', 'Directeur'),
                        ('MANAGER', 'Manager'),
                        ('ESTIMATEUR', 'Estimateur'),
                        ('ATELIER', 'Atelier'),
                        ('CHAUFFEUR', 'Chauffeur'),
                        ('POSEUR', 'Poseur'),
                    ],
                    default='ANY',
                    max_length=20,
                    verbose_name='Rôle requis',
                )),
                ('estimated_hours', models.DecimalField(
                    decimal_places=2, default=0, max_digits=6,
                    verbose_name='Heures estimées',
                )),
                ('actual_hours', models.DecimalField(
                    decimal_places=2, default=0, max_digits=6,
                    verbose_name='Heures réelles',
                )),
                ('due_date', models.DateField(blank=True, null=True, verbose_name='Échéance')),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, verbose_name='Notes')),
                ('phase', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='tasks',
                    to='projects.phase',
                    verbose_name='Phase',
                )),
            ],
            options={
                'verbose_name': 'Tâche',
                'verbose_name_plural': 'Tâches',
                'ordering': ['order'],
            },
        ),

        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['status'], name='projects_ta_status_idx'),
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['phase', 'order'], name='projects_ta_phase_order_idx'),
        ),

        # ── Affectation ─────────────────────────────────────────────

        migrations.CreateModel(
            name='TaskAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('is_primary', models.BooleanField(default=True, verbose_name='Responsable principal')),
                ('assigned_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='given_assignments',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Affecté par',
                )),
                ('task', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='assignments',
                    to='projects.task',
                    verbose_name='Tâche',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='task_assignments',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Utilisateur',
                )),
            ],
            options={
                'verbose_name': 'Affectation',
                'verbose_name_plural': 'Affectations',
                'ordering': ['-is_primary', 'assigned_at'],
            },
        ),

        migrations.AlterUniqueTogether(
            name='taskassignment',
            unique_together={('task', 'user')},
        ),
    ]
