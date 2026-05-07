import django.contrib.auth.models
import django.contrib.auth.validators
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID',
                )),
                # AbstractBaseUser
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(
                    blank=True, null=True, verbose_name='last login',
                )),
                # PermissionsMixin
                ('is_superuser', models.BooleanField(
                    default=False,
                    help_text='Designates that this user has all permissions without explicitly assigning them.',
                    verbose_name='superuser status',
                )),
                # AbstractUser
                ('username', models.CharField(
                    error_messages={'unique': 'A user with that username already exists.'},
                    help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.',
                    max_length=150,
                    unique=True,
                    validators=[django.contrib.auth.validators.UnicodeUsernameValidator()],
                    verbose_name='username',
                )),
                ('first_name', models.CharField(
                    blank=True, max_length=150, verbose_name='first name',
                )),
                ('last_name', models.CharField(
                    blank=True, max_length=150, verbose_name='last name',
                )),
                ('email', models.EmailField(
                    blank=True, max_length=254, verbose_name='email address',
                )),
                ('is_staff', models.BooleanField(
                    default=False,
                    help_text='Designates whether the user can log into this admin site.',
                    verbose_name='staff status',
                )),
                ('is_active', models.BooleanField(
                    default=True,
                    help_text='Designates whether this user should be treated as active.',
                    verbose_name='active',
                )),
                ('date_joined', models.DateTimeField(
                    default=django.utils.timezone.now, verbose_name='date joined',
                )),
                # Champs personnalisés Bois&Co
                ('role', models.CharField(
                    choices=[
                        ('DIRECTEUR', 'Directeur'),
                        ('MANAGER', 'Manager'),
                        ('ESTIMATEUR', 'Estimateur'),
                        ('ATELIER', 'Atelier'),
                        ('CHAUFFEUR', 'Chauffeur'),
                        ('POSEUR', 'Poseur'),
                    ],
                    default='MANAGER',
                    max_length=20,
                    verbose_name='Rôle',
                )),
                ('phone', models.CharField(
                    blank=True, max_length=20, verbose_name='Téléphone',
                )),
                ('avatar', models.ImageField(
                    blank=True, null=True,
                    upload_to='avatars/',
                    verbose_name='avatar',
                )),
                ('is_active_employee', models.BooleanField(
                    default=True, verbose_name='Employé actif',
                )),
                # Relations M2M héritées
                ('groups', models.ManyToManyField(
                    blank=True,
                    help_text='The groups this user belongs to.',
                    related_name='user_set',
                    related_query_name='user',
                    to='auth.group',
                    verbose_name='groups',
                )),
                ('user_permissions', models.ManyToManyField(
                    blank=True,
                    help_text='Specific permissions for this user.',
                    related_name='user_set',
                    related_query_name='user',
                    to='auth.permission',
                    verbose_name='user permissions',
                )),
            ],
            options={
                'verbose_name': 'Utilisateur',
                'verbose_name_plural': 'Utilisateurs',
                'ordering': ['last_name', 'first_name'],
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
    ]
