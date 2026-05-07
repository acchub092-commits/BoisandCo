import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(
                    choices=[
                        ('TASK_ASSIGNED',  'Tâche affectée'),
                        ('TASK_ACTIVATED', 'Tâche activée'),
                        ('TASK_COMPLETED', 'Tâche terminée'),
                        ('TASK_OVERDUE',   'Tâche en retard'),
                        ('PHASE_STARTED',  'Phase démarrée'),
                        ('PHASE_DONE',     'Phase terminée'),
                        ('PROJECT_UPDATE', 'Mise à jour projet'),
                        ('DOCUMENT_ADDED', 'Document ajouté'),
                        ('MENTION',        'Mention'),
                    ],
                    max_length=30,
                    verbose_name='Type',
                )),
                ('title', models.CharField(max_length=200, verbose_name='Titre')),
                ('message', models.TextField(verbose_name='Message')),
                ('is_read', models.BooleanField(default=False, verbose_name='Lu')),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('object_id', models.PositiveIntegerField(blank=True, null=True)),
                ('content_type', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='contenttypes.contenttype',
                )),
                ('recipient', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notifications',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Destinataire',
                )),
                ('sender', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='sent_notifications',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Émetteur',
                )),
            ],
            options={
                'verbose_name': 'Notification',
                'verbose_name_plural': 'Notifications',
                'ordering': ['-created_at'],
            },
        ),

        migrations.AddIndex(
            model_name='notification',
            index=models.Index(
                fields=['recipient', 'is_read'],
                name='notif_recipient_read_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(
                fields=['created_at'],
                name='notif_created_at_idx',
            ),
        ),
    ]
