"""
Commande Django : crée toutes les données de démonstration Bois&Co.

Usage :
    python manage.py create_demo_data
    python manage.py create_demo_data --reset   (supprime avant de recréer)

Crée :
  - 6 utilisateurs (un par rôle) + 1 superuser
  - 2 gabarits de projet avec phases et tâches types
  - 4 projets à différents stades d'avancement
  - Phases, tâches, affectations cohérentes
  - Tokens portail client
  - 5 leads CRM à différentes étapes du pipeline
  - Activités, RDV et journal d'activité CRM
  - 3 demandes de chiffrage à différents stades
  - Notifications d'exemple
"""
import uuid
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class Command(BaseCommand):
    help = 'Crée les données de démonstration Bois&Co'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Supprime les données existantes avant de recréer',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self._reset()

        self.stdout.write('\n── Bois&Co : création des données de démo ──\n')

        users        = self._create_users()
        templates    = self._create_templates(users)
        projects     = self._create_projects(users, templates)
        leads        = self._create_crm_data(users)
        self._create_chiffrage_data(users, leads)
        self._create_notifications(users, projects)

        self.stdout.write(self.style.SUCCESS(
            '\n✓ Données de démo créées avec succès !\n'
            '\n  Identifiants de connexion :\n'
            '  ┌─────────────────────────────────────────────────────┐\n'
            '  │  Email                          Rôle      Mot passe │\n'
            '  │  admin@boisandco.fr             Directeur admin123   │\n'
            '  │  sophie.martin@boisandco.fr     Manager   demo123    │\n'
            '  │  pierre.dubois@boisandco.fr     Estimateur demo123   │\n'
            '  │  jean.moreau@boisandco.fr       Atelier   demo123    │\n'
            '  │  marc.leroy@boisandco.fr        Chauffeur  demo123   │\n'
            '  │  thomas.petit@boisandco.fr      Poseur    demo123    │\n'
            '  └─────────────────────────────────────────────────────┘\n'
        ))

    # ────────────────────────────────────────────────────────────
    # Reset
    # ────────────────────────────────────────────────────────────

    def _reset(self):
        from apps.projects.models import Project, ProjectTemplate
        from apps.notifications.models import Notification
        from apps.client_portal.models import ClientToken
        from apps.crm.models import Lead
        from apps.chiffrage.models import DemandeChiffrage

        self.stdout.write('  Suppression des données existantes…')
        ClientToken.objects.all().delete()
        Notification.objects.all().delete()
        Lead.objects.all().delete()
        DemandeChiffrage.objects.all().delete()
        Project.objects.all().delete()
        ProjectTemplate.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        self.stdout.write('  OK')

    # ────────────────────────────────────────────────────────────
    # Utilisateurs
    # ────────────────────────────────────────────────────────────

    def _create_users(self):
        self.stdout.write('\n[1/6] Utilisateurs…')

        # Superuser / Directeur
        admin, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@boisandco.fr',
                'first_name': 'Alexandre',
                'last_name': 'Bernard',
                'role': User.Role.DIRECTEUR,
                'is_staff': True,
                'is_superuser': True,
                'is_active_employee': True,
            },
        )
        admin.set_password('admin123')
        admin.save()

        specs = [
            ('sophie.martin',  'Sophie',  'Martin',  'sophie.martin@boisandco.fr',  User.Role.MANAGER),
            ('pierre.dubois',  'Pierre',  'Dubois',  'pierre.dubois@boisandco.fr',  User.Role.ESTIMATEUR),
            ('jean.moreau',    'Jean',    'Moreau',  'jean.moreau@boisandco.fr',    User.Role.ATELIER),
            ('marc.leroy',     'Marc',    'Leroy',   'marc.leroy@boisandco.fr',     User.Role.CHAUFFEUR),
            ('thomas.petit',   'Thomas',  'Petit',   'thomas.petit@boisandco.fr',   User.Role.POSEUR),
        ]

        users = {'admin': admin}
        for username, first, last, email, role in specs:
            u, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first,
                    'last_name': last,
                    'role': role,
                    'is_active_employee': True,
                },
            )
            if created:
                u.set_password('demo123')
                u.save()
            users[username] = u
            marker = '+ créé' if created else '  existant'
            self.stdout.write(f'    {marker} : {u.get_full_name()} ({u.get_role_display()})')

        return users

    # ────────────────────────────────────────────────────────────
    # Gabarits
    # ────────────────────────────────────────────────────────────

    def _create_templates(self, users):
        from apps.projects.models import ProjectTemplate, PhaseTemplate, TaskTemplate

        self.stdout.write('\n[2/6] Gabarits de projet…')

        # ── Gabarit 1 : Menuiserie Intérieure Standard ──
        t1, _ = ProjectTemplate.objects.get_or_create(
            name='Menuiserie Intérieure Standard',
            defaults={
                'description': 'Gabarit pour portes, fenêtres, dressings et rangements intérieurs.',
                'created_by': users['admin'],
            },
        )
        if not t1.phase_templates.exists():
            phases_t1 = [
                (0, 'Avant-projet',  5,  [
                    (0, 'Prise de mesures sur site',        'ESTIMATEUR', 3),
                    (1, 'Élaboration du devis',             'ESTIMATEUR', 4),
                    (2, 'Validation devis par le client',   'MANAGER',    1),
                ]),
                (1, 'Étude technique', 7, [
                    (0, 'Plans d\'exécution',               'ESTIMATEUR', 8),
                    (1, 'Validation plans client',          'MANAGER',    2),
                    (2, 'Commande matières premières',      'MANAGER',    1),
                ]),
                (2, 'Fabrication atelier', 12, [
                    (0, 'Débit – découpe panneaux',         'ATELIER',    6),
                    (1, 'Usinage et perçage',               'ATELIER',    4),
                    (2, 'Assemblage caissons',              'ATELIER',    8),
                    (3, 'Façades et finitions',             'ATELIER',    6),
                    (4, 'Quincaillerie et ferrures',        'ATELIER',    3),
                    (5, 'Contrôle qualité atelier',         'MANAGER',    2),
                ]),
                (3, 'Logistique', 2, [
                    (0, 'Préparation chargement',           'ATELIER',    2),
                    (1, 'Transport sur chantier',           'CHAUFFEUR',  3),
                ]),
                (4, 'Pose chantier', 5, [
                    (0, 'Installation et montage',          'POSEUR',     8),
                    (1, 'Réglages et ajustements',          'POSEUR',     4),
                    (2, 'Nettoyage et protection',          'POSEUR',     1),
                    (3, 'PV de réception signé client',     'MANAGER',    1),
                ]),
            ]
            for order, name, days, tasks in phases_t1:
                pt = PhaseTemplate.objects.create(
                    template=t1, name=name, order=order, estimated_days=days
                )
                for t_order, t_name, t_role, t_hours in tasks:
                    TaskTemplate.objects.create(
                        phase=pt, name=t_name, order=t_order,
                        required_role=t_role, estimated_hours=t_hours,
                    )

        # ── Gabarit 2 : Escalier Sur Mesure ──
        t2, _ = ProjectTemplate.objects.get_or_create(
            name='Escalier Sur Mesure',
            defaults={
                'description': 'Gabarit spécifique pour la conception et pose d\'escaliers.',
                'created_by': users['admin'],
            },
        )
        if not t2.phase_templates.exists():
            phases_t2 = [
                (0, 'Relevé et étude', 5, [
                    (0, 'Relevé cotes trémie et hauteur', 'ESTIMATEUR', 3),
                    (1, 'Calcul giration et tirage',      'ESTIMATEUR', 4),
                    (2, 'Devis et validation',            'MANAGER',    1),
                ]),
                (1, 'Fabrication escalier', 15, [
                    (0, 'Limons et marches — débit bois', 'ATELIER',    8),
                    (1, 'Usinage limons',                 'ATELIER',    6),
                    (2, 'Tournage ou fraisage balustres', 'ATELIER',    8),
                    (3, 'Pré-assemblage atelier',         'ATELIER',    4),
                    (4, 'Traitement et finition',         'ATELIER',    6),
                ]),
                (2, 'Transport et pose', 3, [
                    (0, 'Transport',                      'CHAUFFEUR',  3),
                    (1, 'Pose escalier',                  'POSEUR',    12),
                    (2, 'Pose rampe et garde-corps',      'POSEUR',     6),
                    (3, 'Réception et finitions',         'MANAGER',    2),
                ]),
            ]
            for order, name, days, tasks in phases_t2:
                pt = PhaseTemplate.objects.create(
                    template=t2, name=name, order=order, estimated_days=days
                )
                for t_order, t_name, t_role, t_hours in tasks:
                    TaskTemplate.objects.create(
                        phase=pt, name=t_name, order=t_order,
                        required_role=t_role, estimated_hours=t_hours,
                    )

        self.stdout.write(f'    + Gabarit "{t1.name}" ({t1.tasks_count} tâches)')
        self.stdout.write(f'    + Gabarit "{t2.name}" ({t2.tasks_count} tâches)')
        return {'menuiserie': t1, 'escalier': t2}

    # ────────────────────────────────────────────────────────────
    # Projets
    # ────────────────────────────────────────────────────────────

    def _create_projects(self, users, templates):
        from apps.projects.models import Project, Phase, Task, TaskAssignment
        from apps.client_portal.models import ClientToken

        self.stdout.write('\n[3/6] Projets…')
        now = timezone.now()
        today = now.date()
        projects = []

        # ── Projet 1 : Cuisine Durand — PRODUCTION ──────────────
        p1, created = Project.objects.get_or_create(
            name='Cuisine équipée — Résidence Durand',
            defaults={
                'client_name':  'Famille Durand',
                'client_email': 'durand.famille@email.fr',
                'client_phone': '06 12 34 56 78',
                'address':      '14 rue des Lilas, 69006 Lyon',
                'status':       Project.Status.PRODUCTION,
                'manager':      users['sophie.martin'],
                'estimator':    users['pierre.dubois'],
                'start_date':   today - timedelta(days=45),
                'end_date':     today + timedelta(days=30),
                'budget':       18500,
                'created_by':   users['admin'],
            },
        )
        if created:
            self._build_project_phases_p1(p1, users, now, today)
            ClientToken.objects.create(project=p1, show_tasks=True)
            self.stdout.write(f'    + [{p1.reference}] {p1.name} ({p1.get_status_display()})')
        projects.append(p1)

        # ── Projet 2 : Dressing Lambert — POSE ──────────────────
        p2, created = Project.objects.get_or_create(
            name='Dressing sur mesure — Appartement Lambert',
            defaults={
                'client_name':  'M. et Mme Lambert',
                'client_email': 'lambert.contact@email.fr',
                'client_phone': '06 98 76 54 32',
                'address':      '7 avenue Foch, 75016 Paris',
                'status':       Project.Status.POSE,
                'manager':      users['sophie.martin'],
                'estimator':    users['pierre.dubois'],
                'start_date':   today - timedelta(days=70),
                'end_date':     today + timedelta(days=7),
                'budget':       12300,
                'created_by':   users['sophie.martin'],
            },
        )
        if created:
            self._build_project_phases_p2(p2, users, now, today)
            ClientToken.objects.create(project=p2)
            self.stdout.write(f'    + [{p2.reference}] {p2.name} ({p2.get_status_display()})')
        projects.append(p2)

        # ── Projet 3 : Escalier Moreau — ETUDE ──────────────────
        p3, created = Project.objects.get_or_create(
            name='Escalier chêne massif — Maison Moreau',
            defaults={
                'client_name':  'M. Moreau',
                'client_email': 'a.moreau@email.fr',
                'client_phone': '07 11 22 33 44',
                'address':      '3 chemin des Pins, 33700 Mérignac',
                'status':       Project.Status.ETUDE,
                'manager':      users['admin'],
                'estimator':    users['pierre.dubois'],
                'start_date':   today - timedelta(days=10),
                'end_date':     today + timedelta(days=60),
                'budget':       9800,
                'created_by':   users['admin'],
            },
        )
        if created:
            self._build_project_phases_p3(p3, users, now, today)
            ClientToken.objects.create(project=p3)
            self.stdout.write(f'    + [{p3.reference}] {p3.name} ({p3.get_status_display()})')
        projects.append(p3)

        # ── Projet 4 : Bibliothèque Petit — AVANT_VENTE ─────────
        p4, created = Project.objects.get_or_create(
            name='Bibliothèque salon — Villa Petit',
            defaults={
                'client_name':  'M. Petit',
                'client_email': 'petit.villa@email.fr',
                'client_phone': '06 55 44 33 22',
                'address':      '22 rue du Parc, 31000 Toulouse',
                'status':       Project.Status.AVANT_VENTE,
                'manager':      users['sophie.martin'],
                'start_date':   None,
                'end_date':     today + timedelta(days=90),
                'budget':       None,
                'notes':        'Premier contact. Client souhaite un mur de bibliothèque en chêne naturel huilé. RDV prise de mesures à fixer.',
                'created_by':   users['sophie.martin'],
            },
        )
        if created:
            self.stdout.write(f'    + [{p4.reference}] {p4.name} ({p4.get_status_display()})')
        projects.append(p4)

        return projects

    # ── Constructeurs de phases/tâches ───────────────────────────

    def _build_project_phases_p1(self, project, users, now, today):
        """Cuisine Durand — PRODUCTION (phases 0 et 1 terminées, phase 2 en cours)."""
        from apps.projects.models import Phase, Task, TaskAssignment

        def phase(order, name, days, active=False, done=False, started_days_ago=None, done_days_ago=None):
            p = Phase.objects.create(
                project=project, name=name, order=order,
                estimated_days=days, is_active=active, is_completed=done,
                started_at=now - timedelta(days=started_days_ago) if started_days_ago else None,
                completed_at=now - timedelta(days=done_days_ago) if done_days_ago else None,
            )
            return p

        def task(ph, order, name, status, progress, role, est_h, due=None, act_h=0):
            t = Task.objects.create(
                phase=ph, name=name, order=order, status=status,
                progress=progress, required_role=role,
                estimated_hours=est_h, actual_hours=act_h,
                due_date=today + timedelta(days=due) if due is not None else None,
                started_at=now - timedelta(days=10) if status in (
                    Task.Status.EN_COURS, Task.Status.TERMINEE
                ) else None,
                completed_at=now - timedelta(days=3) if status == Task.Status.TERMINEE else None,
            )
            return t

        def assign(t, user, by, primary=True):
            TaskAssignment.objects.create(task=t, user=user, assigned_by=by, is_primary=primary)

        S, A = users['sophie.martin'], users['admin']
        P, J = users['pierre.dubois'], users['jean.moreau']
        T = users['thomas.petit']

        # Phase 0 — Avant-projet (terminée)
        ph0 = phase(0, 'Avant-projet', 5, done=True, started_days_ago=45, done_days_ago=38)
        t = task(ph0, 0, 'Prise de mesures sur site', Task.Status.TERMINEE, 100, 'ESTIMATEUR', 3, act_h=3.5)
        assign(t, P, S)
        t = task(ph0, 1, 'Élaboration du devis', Task.Status.TERMINEE, 100, 'ESTIMATEUR', 4, act_h=4)
        assign(t, P, S)
        t = task(ph0, 2, 'Validation devis par le client', Task.Status.TERMINEE, 100, 'MANAGER', 1, act_h=1)
        assign(t, S, A)

        # Phase 1 — Étude technique (terminée)
        ph1 = phase(1, 'Étude technique', 7, done=True, started_days_ago=38, done_days_ago=25)
        t = task(ph1, 0, "Plans d'exécution", Task.Status.TERMINEE, 100, 'ESTIMATEUR', 8, act_h=9)
        assign(t, P, S)
        t = task(ph1, 1, 'Validation plans client', Task.Status.TERMINEE, 100, 'MANAGER', 2, act_h=2)
        assign(t, S, A)
        t = task(ph1, 2, 'Commande matières premières', Task.Status.TERMINEE, 100, 'MANAGER', 1, act_h=1)
        assign(t, S, A)

        # Phase 2 — Fabrication atelier (active — en cours)
        ph2 = phase(2, 'Fabrication atelier', 12, active=True, started_days_ago=25)
        t = task(ph2, 0, 'Débit – découpe panneaux',   Task.Status.TERMINEE, 100, 'ATELIER', 6,  act_h=6.5)
        assign(t, J, S)
        t = task(ph2, 1, 'Usinage et perçage',          Task.Status.TERMINEE, 100, 'ATELIER', 4,  act_h=4)
        assign(t, J, S)
        t = task(ph2, 2, 'Assemblage caissons',         Task.Status.EN_COURS,  65, 'ATELIER', 8,  due=5, act_h=5)
        assign(t, J, S)
        t = task(ph2, 3, 'Façades et finitions',        Task.Status.EN_ATTENTE, 0, 'ATELIER', 6,  due=10)
        assign(t, J, S)
        t = task(ph2, 4, 'Quincaillerie et ferrures',   Task.Status.EN_ATTENTE, 0, 'ATELIER', 3,  due=13)
        assign(t, J, S)
        t = task(ph2, 5, 'Contrôle qualité atelier',    Task.Status.EN_ATTENTE, 0, 'MANAGER', 2,  due=15)
        assign(t, S, A)

        # Phase 3 — Logistique (en attente)
        ph3 = phase(3, 'Logistique', 2)
        task(ph3, 0, 'Préparation chargement', Task.Status.EN_ATTENTE, 0, 'ATELIER',    2, due=20)
        task(ph3, 1, 'Transport sur chantier', Task.Status.EN_ATTENTE, 0, 'CHAUFFEUR',  3, due=22)

        # Phase 4 — Pose (en attente)
        ph4 = phase(4, 'Pose chantier', 5)
        task(ph4, 0, 'Installation et montage',     Task.Status.EN_ATTENTE, 0, 'POSEUR',   8, due=25)
        task(ph4, 1, 'Réglages et ajustements',     Task.Status.EN_ATTENTE, 0, 'POSEUR',   4, due=28)
        task(ph4, 2, 'Nettoyage et protection',     Task.Status.EN_ATTENTE, 0, 'POSEUR',   1, due=28)
        task(ph4, 3, 'PV de réception signé client',Task.Status.EN_ATTENTE, 0, 'MANAGER',  1, due=29)

    def _build_project_phases_p2(self, project, users, now, today):
        """Dressing Lambert — POSE (phases 0-3 terminées, pose en cours)."""
        from apps.projects.models import Phase, Task, TaskAssignment

        S, A = users['sophie.martin'], users['admin']
        P, J = users['pierre.dubois'], users['jean.moreau']
        M, T = users['marc.leroy'], users['thomas.petit']

        def ph_done(order, name, days, ago_start, ago_end):
            return Phase.objects.create(
                project=project, name=name, order=order,
                estimated_days=days, is_active=False, is_completed=True,
                started_at=now - timedelta(days=ago_start),
                completed_at=now - timedelta(days=ago_end),
            )

        def t_done(ph, order, name, role, est_h):
            t = Task.objects.create(
                phase=ph, name=name, order=order,
                status=Task.Status.TERMINEE, progress=100,
                required_role=role, estimated_hours=est_h, actual_hours=est_h,
                completed_at=ph.completed_at,
            )
            return t

        # Phases 0–3 terminées
        ph0 = ph_done(0, 'Avant-projet',       5, 70, 63)
        t_done(ph0, 0, 'Prise de mesures',    'ESTIMATEUR', 2); t_done(ph0, 1, 'Devis', 'ESTIMATEUR', 3)
        ph1 = ph_done(1, 'Étude technique',    7, 63, 50)
        t_done(ph1, 0, 'Plans exécution',     'ESTIMATEUR', 6); t_done(ph1, 1, 'Validation', 'MANAGER', 1)
        ph2 = ph_done(2, 'Fabrication atelier',10, 50, 15)
        t_done(ph2, 0, 'Débit panneaux',      'ATELIER', 4); t_done(ph2, 1, 'Usinage', 'ATELIER', 3)
        t_done(ph2, 2, 'Assemblage',          'ATELIER', 6); t_done(ph2, 3, 'Finitions', 'ATELIER', 4)
        ph3 = ph_done(3, 'Logistique',         2, 15, 12)
        t3a = t_done(ph3, 0, 'Chargement',    'ATELIER', 2)
        t3b = t_done(ph3, 1, 'Transport',     'CHAUFFEUR', 2)
        TaskAssignment.objects.create(task=t3b, user=M, assigned_by=S)

        # Phase 4 — Pose (active, en cours)
        ph4 = Phase.objects.create(
            project=project, name='Pose chantier', order=4,
            estimated_days=3, is_active=True,
            started_at=now - timedelta(days=3),
        )
        t4a = Task.objects.create(phase=ph4, name='Installation dressing', order=0,
            status=Task.Status.TERMINEE, progress=100, required_role='POSEUR',
            estimated_hours=8, actual_hours=9, completed_at=now - timedelta(days=1))
        TaskAssignment.objects.create(task=t4a, user=T, assigned_by=S)
        t4b = Task.objects.create(phase=ph4, name='Réglages portes coulissantes', order=1,
            status=Task.Status.EN_COURS, progress=40, required_role='POSEUR',
            estimated_hours=3, due_date=today + timedelta(days=2))
        TaskAssignment.objects.create(task=t4b, user=T, assigned_by=S)
        t4c = Task.objects.create(phase=ph4, name='PV de réception', order=2,
            status=Task.Status.EN_ATTENTE, progress=0, required_role='MANAGER',
            estimated_hours=1, due_date=today + timedelta(days=3))
        TaskAssignment.objects.create(task=t4c, user=S, assigned_by=A)

    def _build_project_phases_p3(self, project, users, now, today):
        """Escalier Moreau — ETUDE (phase 0 en cours)."""
        from apps.projects.models import Phase, Task, TaskAssignment

        A, S, P = users['admin'], users['sophie.martin'], users['pierre.dubois']

        ph0 = Phase.objects.create(
            project=project, name='Relevé et étude', order=0,
            estimated_days=5, is_active=True,
            started_at=now - timedelta(days=5),
        )
        t0 = Task.objects.create(phase=ph0, name="Relevé cotes trémie et hauteur", order=0,
            status=Task.Status.TERMINEE, progress=100, required_role='ESTIMATEUR',
            estimated_hours=3, actual_hours=3.5, completed_at=now - timedelta(days=3))
        TaskAssignment.objects.create(task=t0, user=P, assigned_by=S)
        t1 = Task.objects.create(phase=ph0, name="Calcul giration et tirage", order=1,
            status=Task.Status.EN_COURS, progress=50, required_role='ESTIMATEUR',
            estimated_hours=4, due_date=today + timedelta(days=3))
        TaskAssignment.objects.create(task=t1, user=P, assigned_by=S)
        t2 = Task.objects.create(phase=ph0, name="Devis et validation", order=2,
            status=Task.Status.EN_ATTENTE, progress=0, required_role='MANAGER',
            estimated_hours=1, due_date=today + timedelta(days=7))
        TaskAssignment.objects.create(task=t2, user=S, assigned_by=A)

        # Phases suivantes créées mais inactives
        Phase.objects.create(project=project, name='Fabrication escalier', order=1, estimated_days=15)
        Phase.objects.create(project=project, name='Transport et pose', order=2, estimated_days=3)

    # ────────────────────────────────────────────────────────────
    # CRM
    # ────────────────────────────────────────────────────────────

    def _create_crm_data(self, users):
        from apps.crm.models import Lead, Activity, Appointment, LeadActivityLog

        self.stdout.write('\n[4/6] Leads CRM…')
        now   = timezone.now()
        today = now.date()
        A     = users['admin']
        S     = users['sophie.martin']

        leads = {}

        # ── Lead 1 : Hôtel Aziz — OFFRE ───────────────────────────
        l1, created = Lead.objects.get_or_create(
            project_name='Menuiserie Hôtel Aziz',
            defaults={
                'contact_name':        'M. Khalid Aziz',
                'company':             'Groupe Aziz Hospitality',
                'client_type':         'Hôtelier',
                'email':               'k.aziz@groupeaziz.ma',
                'phone':               '06 61 11 22 33',
                'location':            'Marrakech — Zone Guéliz',
                'project_type':        'Hôtel 5 étoiles',
                'products':            'Portes chambres, Cuisines, Dressings suite',
                'status':              Lead.Status.OFFRE,
                'potential':           Lead.Potential.IMPORTANT,
                'canal_origine':       Lead.Canal.PRESCRIPTION,
                'flux_type':           Lead.FluxType.MARCHE,
                'probability':         Lead.Probability.HIGH,
                'budget_mad':          2_500_000,
                'nb_logements':        120,
                'start_date_est':      today + timedelta(days=60),
                'end_date_est':        today + timedelta(days=300),
                'offer_amount_ht':     2_350_000,
                'offer_sent_date':     today - timedelta(days=5),
                'offer_validity_days': 45,
                'strategic_comment':   'Référence hôtelière clé pour notre développement Marrakech.',
                'competitor':          'Menuiserie Al Baraka',
                'workflow_status':     Lead.WorkflowStatus.VALIDATED,
                'source':              Lead.Source.DIRECTOR_ASSIGNED,
                'assigned_to':         S,
                'created_by':          A,
                'validated_by':        A,
                'validated_at':        now - timedelta(days=30),
            },
        )
        leads['aziz'] = l1
        if created:
            LeadActivityLog.objects.create(
                lead=l1, log_type=LeadActivityLog.LogType.ASSIGNMENT,
                content=f'Lead assigné à {S.get_full_name()} par {A.get_full_name()}.',
                performed_by=A,
            )
            LeadActivityLog.objects.create(
                lead=l1, log_type=LeadActivityLog.LogType.STATUS_CHANGE,
                content='Passage en Offre envoyée. Offre de 2 350 000 MAD HT transmise.',
                performed_by=S,
            )
            # RDV à venir
            rdv1 = Appointment.objects.create(
                lead=l1, title='Présentation & négociation offre',
                appointment_type=Appointment.AppointmentType.PROPOSITION,
                scheduled_at=now + timedelta(days=2, hours=10),
                duration_minutes=90,
                location='Siège Groupe Aziz — Marrakech',
                status=Appointment.Status.PLANIFIE,
                created_by=S,
            )
            rdv1.attendees.set([S, A])
            LeadActivityLog.objects.create(
                lead=l1, log_type=LeadActivityLog.LogType.RDV_ADDED,
                content=f'RDV planifié : « {rdv1.title} » le {rdv1.scheduled_at:%d/%m/%Y à %H:%M}.',
                performed_by=S,
            )
            self.stdout.write(f'    + Lead : {l1}')

        # ── Lead 2 : Résidence Les Pins — CHIFFRAGE ────────────────
        l2, created = Lead.objects.get_or_create(
            project_name='Résidence Les Pins — Aïn Sebaa',
            defaults={
                'contact_name':    'Mme Fatima Benali',
                'company':         'Promoteur Benali Immobilier',
                'client_type':     'Promoteur',
                'email':           'f.benali@benali-immo.ma',
                'phone':           '06 72 33 44 55',
                'location':        'Casablanca — Aïn Sebaa',
                'project_type':    'Résidentiel',
                'products':        'Cuisines équipées, Dressings, Portes intérieures',
                'status':          Lead.Status.CHIFFRAGE,
                'potential':       Lead.Potential.MOYEN,
                'canal_origine':   Lead.Canal.RECOMMANDATION,
                'flux_type':       Lead.FluxType.MARCHE,
                'probability':     Lead.Probability.MED,
                'budget_mad':      850_000,
                'nb_logements':    48,
                'start_date_est':  today + timedelta(days=90),
                'workflow_status': Lead.WorkflowStatus.VALIDATED,
                'source':          Lead.Source.DIRECTOR_ASSIGNED,
                'assigned_to':     S,
                'created_by':      A,
                'validated_by':    A,
                'validated_at':    now - timedelta(days=20),
            },
        )
        leads['pins'] = l2
        if created:
            LeadActivityLog.objects.create(
                lead=l2, log_type=LeadActivityLog.LogType.ASSIGNMENT,
                content=f'Lead assigné à {S.get_full_name()}.',
                performed_by=A,
            )
            # RDV passé avec compte rendu
            rdv2 = Appointment.objects.create(
                lead=l2, title='Visite chantier et prise de mesures',
                appointment_type=Appointment.AppointmentType.VISITE,
                scheduled_at=now - timedelta(days=8),
                duration_minutes=120,
                location='Chantier Résidence Les Pins — Aïn Sebaa',
                status=Appointment.Status.REALISE,
                report='Visite effectuée. 48 logements T3/T4. Finitions souhaitées : laqué blanc mat. '
                       'Plans fournis par le promoteur. Chiffrage en cours sur la base de 48 cuisines standard.',
                report_written_at=now - timedelta(days=7),
                created_by=S,
            )
            rdv2.attendees.set([S])
            LeadActivityLog.objects.create(
                lead=l2, log_type=LeadActivityLog.LogType.RDV_DONE,
                content=f'Compte rendu rédigé pour le RDV « {rdv2.title} ».',
                performed_by=S,
            )
            # RDV de suivi à venir
            rdv2b = Appointment.objects.create(
                lead=l2, title='Remise chiffrage détaillé',
                appointment_type=Appointment.AppointmentType.PROPOSITION,
                scheduled_at=now + timedelta(days=4, hours=14),
                duration_minutes=60,
                location='Bureaux Benali Immobilier — Casablanca',
                status=Appointment.Status.PLANIFIE,
                created_by=S,
            )
            rdv2b.attendees.set([S])
            LeadActivityLog.objects.create(
                lead=l2, log_type=LeadActivityLog.LogType.RDV_ADDED,
                content=f'RDV planifié : « {rdv2b.title} » le {rdv2b.scheduled_at:%d/%m/%Y à %H:%M}.',
                performed_by=S,
            )
            self.stdout.write(f'    + Lead : {l2}')

        # ── Lead 3 : Complexe IBN Rochd — PENDING_VALIDATION ──────
        l3, created = Lead.objects.get_or_create(
            project_name='Complexe Scolaire Ibn Rochd',
            defaults={
                'contact_name':       'M. Hassan Tazi',
                'company':            'Fondation Ibn Rochd',
                'client_type':        'Établissement public',
                'email':              'h.tazi@fondation-ibnrochd.ma',
                'phone':              '05 22 77 88 99',
                'location':           'Casablanca — Hay Mohammadi',
                'project_type':       'Équipement public',
                'products':           'Portes coupe-feu, Bibliothèques, Mobilier salle de classe',
                'status':             Lead.Status.QUALIFICATION,
                'potential':          Lead.Potential.IMPORTANT,
                'canal_origine':      Lead.Canal.APPEL_OFFRE,
                'flux_type':          Lead.FluxType.MARCHE,
                'probability':        Lead.Probability.MED,
                'budget_mad':         1_200_000,
                'nb_logements':       1,
                'strategic_comment':  'Appel d\'offre public. Dossier technique à déposer avant fin du mois.',
                'workflow_status':    Lead.WorkflowStatus.PENDING_VALIDATION,
                'source':             Lead.Source.COMMERCIAL_CREATED,
                'assigned_to':        S,
                'created_by':         S,
            },
        )
        leads['ibnrochd'] = l3
        if created:
            LeadActivityLog.objects.create(
                lead=l3, log_type=LeadActivityLog.LogType.STATUS_CHANGE,
                content=f'Soumis à validation par {S.get_full_name()}.',
                performed_by=S,
            )
            self.stdout.write(f'    + Lead : {l3} (en attente validation)')

        # ── Lead 4 : Villa Bouhlal — VISITE ──────────────────────
        l4, created = Lead.objects.get_or_create(
            project_name='Rénovation Villa Bouhlal',
            defaults={
                'contact_name':    'M. Youssef Bouhlal',
                'company':         '',
                'client_type':     'Particulier',
                'email':           'y.bouhlal@gmail.com',
                'phone':           '06 50 60 70 80',
                'location':        'Mohammedia',
                'project_type':    'Résidentiel haut de gamme',
                'products':        'Cuisine, Dressing, Bibliothèque',
                'status':          Lead.Status.VISITE,
                'potential':       Lead.Potential.FAIBLE,
                'canal_origine':   Lead.Canal.APPEL_ENTRANT,
                'next_followup_date': today + timedelta(days=3),
                'workflow_status': Lead.WorkflowStatus.VALIDATED,
                'source':          Lead.Source.DIRECTOR_ASSIGNED,
                'assigned_to':     S,
                'created_by':      A,
                'validated_by':    A,
                'validated_at':    now - timedelta(days=5),
            },
        )
        leads['bouhlal'] = l4
        if created:
            Activity.objects.create(
                lead=l4, activity_type=Activity.Type.APPEL,
                subject='Premier contact téléphonique',
                planned_at=now - timedelta(days=5),
                duration_min=20,
                assigned_to=S, status=Activity.Status.REALISE,
                compte_rendu='Client a appelé suite à recommandation. Projet de rénovation complète '
                             'cuisine + dressing. Visite terrain à programmer.',
                created_by=A,
            )
            LeadActivityLog.objects.create(
                lead=l4, log_type=LeadActivityLog.LogType.APPEL,
                content='Appel entrant. Projet rénovation villa 250 m². Visite à planifier.',
                performed_by=S,
            )
            self.stdout.write(f'    + Lead : {l4}')

        # ── Lead 5 : Immeuble Zerktouni — GAGNEE ─────────────────
        l5, created = Lead.objects.get_or_create(
            project_name='Immeuble Bureaux Zerktouni',
            defaults={
                'contact_name':    'M. Rachid Filali',
                'company':         'Filali Invest',
                'client_type':     'Investisseur',
                'email':           'r.filali@filaliinvest.ma',
                'phone':           '06 44 55 66 77',
                'location':        'Casablanca — Quartier Zerktouni',
                'project_type':    'Bureaux',
                'products':        'Cloisons vitrées, Portes design, Mobilier réception',
                'status':          Lead.Status.GAGNEE,
                'potential':       Lead.Potential.IMPORTANT,
                'canal_origine':   Lead.Canal.PRESCRIPTION,
                'flux_type':       Lead.FluxType.COMMANDE,
                'probability':     Lead.Probability.HIGH,
                'budget_mad':      980_000,
                'offer_amount_ht': 940_000,
                'offer_sent_date': today - timedelta(days=45),
                'workflow_status': Lead.WorkflowStatus.VALIDATED,
                'source':          Lead.Source.DIRECTOR_ASSIGNED,
                'assigned_to':     S,
                'created_by':      A,
                'validated_by':    A,
                'validated_at':    now - timedelta(days=60),
            },
        )
        leads['zerktouni'] = l5
        if created:
            LeadActivityLog.objects.create(
                lead=l5, log_type=LeadActivityLog.LogType.STATUS_CHANGE,
                content='Bon de commande reçu. Lead passé en statut Gagné.',
                performed_by=A,
            )
            self.stdout.write(f'    + Lead : {l5} (gagné)')

        total = Lead.objects.count()
        self.stdout.write(f'    → {total} leads au total dans le pipeline')
        return leads

    # ────────────────────────────────────────────────────────────
    # Chiffrage
    # ────────────────────────────────────────────────────────────

    def _create_chiffrage_data(self, users, leads):
        from apps.chiffrage.models import DemandeChiffrage, MessageFil, HistoriqueAction

        self.stdout.write('\n[5/6] Demandes de chiffrage…')
        now = timezone.now()
        A   = users['admin']
        S   = users['sophie.martin']
        P   = users['pierre.dubois']

        # ── Demande 1 : Hôtel Aziz — DEVIS_VALIDE ─────────────────
        d1, created = DemandeChiffrage.objects.get_or_create(
            client_nom='Groupe Aziz Hospitality',
            defaults={
                'client_ref_affaire':      'AZH-2026-001',
                'description':             'Fourniture et pose de la menuiserie intérieure complète '
                                           'de l\'Hôtel Aziz 5* — 120 chambres + suites + espaces communs.',
                'delai_souhaite':          now.date() + timedelta(days=30),
                'urgence':                 DemandeChiffrage.Urgence.URGENT,
                'finitions':               'Laqué blanc mat et noyer naturel huilé.',
                'kits_references':         'Portes isophoniques 42 dB, Dressings sur mesure, Cuisines compactes.',
                'quantites_estimees':      '120 portes chambre, 60 dressings, 8 cuisines suite.',
                'statut':                  DemandeChiffrage.Statut.DEVIS_VALIDE,
                'commercial':              S,
                'assigned_to':             P,
                'validated_by_dc':         A,
                'validated_by_dg':         A,
                'montant_ht':              2_350_000,
                'validated_dc_at':         now - timedelta(days=25),
                'validated_dg_at':         now - timedelta(days=10),
                'lead':                    leads.get('aziz'),
            },
        )
        if created:
            HistoriqueAction.objects.create(
                demande=d1, auteur=S,
                action='Création de la demande de chiffrage',
                nouveau_statut=DemandeChiffrage.Statut.EN_ATTENTE,
            )
            HistoriqueAction.objects.create(
                demande=d1, auteur=A,
                action='Validation DC — transmis à Méthodes',
                ancien_statut=DemandeChiffrage.Statut.EN_ATTENTE,
                nouveau_statut=DemandeChiffrage.Statut.VALIDEE_DC,
            )
            HistoriqueAction.objects.create(
                demande=d1, auteur=P,
                action='Chiffrage terminé — soumis à la DG',
                ancien_statut=DemandeChiffrage.Statut.EN_CHIFFRAGE,
                nouveau_statut=DemandeChiffrage.Statut.SOUMIS_DG,
            )
            HistoriqueAction.objects.create(
                demande=d1, auteur=A,
                action='Devis validé par la DG — montant 2 350 000 MAD HT',
                ancien_statut=DemandeChiffrage.Statut.SOUMIS_DG,
                nouveau_statut=DemandeChiffrage.Statut.DEVIS_VALIDE,
            )
            MessageFil.objects.create(
                demande=d1, auteur=P,
                contenu='Chiffrage réalisé sur la base des plans fournis. '
                        'Hypothèse : portes isophoniques classe 3 (42 dB), huisseries à sceller. '
                        'Marge de sécurité de 8 % incluse pour aléas chantier.',
                is_internal=True,
            )
            MessageFil.objects.create(
                demande=d1, auteur=S,
                contenu='Devis prêt à transmettre au client. Rendez-vous de présentation confirmé dans 2 jours.',
            )
            self.stdout.write(f'    + Demande : {d1.reference} — {d1.client_nom} ({d1.get_statut_display()})')

        # ── Demande 2 : Résidence Les Pins — EN_CHIFFRAGE ──────────
        d2, created = DemandeChiffrage.objects.get_or_create(
            client_nom='Benali Immobilier — Résidence Les Pins',
            defaults={
                'client_ref_affaire': 'BIM-2026-048',
                'description':        '48 appartements T3/T4. Cuisines équipées, dressings chambre, '
                                      'portes palières et intérieures.',
                'delai_souhaite':     now.date() + timedelta(days=20),
                'urgence':            DemandeChiffrage.Urgence.STANDARD,
                'finitions':          'Laqué blanc brillant. Poignées inox brossé.',
                'quantites_estimees': '48 cuisines, 48 dressings, 200 portes intérieures.',
                'statut':             DemandeChiffrage.Statut.EN_CHIFFRAGE,
                'jalon':              DemandeChiffrage.Jalon.CHIFFRAGE,
                'commercial':         S,
                'assigned_to':        P,
                'validated_by_dc':    A,
                'validated_dc_at':    now - timedelta(days=8),
                'lead':               leads.get('pins'),
            },
        )
        if created:
            HistoriqueAction.objects.create(
                demande=d2, auteur=S, action='Demande soumise',
                nouveau_statut=DemandeChiffrage.Statut.EN_ATTENTE,
            )
            HistoriqueAction.objects.create(
                demande=d2, auteur=A, action='Validation DC',
                ancien_statut=DemandeChiffrage.Statut.EN_ATTENTE,
                nouveau_statut=DemandeChiffrage.Statut.VALIDEE_DC,
            )
            HistoriqueAction.objects.create(
                demande=d2, auteur=P, action='Prise en charge par Méthodes',
                ancien_statut=DemandeChiffrage.Statut.VALIDEE_DC,
                nouveau_statut=DemandeChiffrage.Statut.EN_CHIFFRAGE,
            )
            MessageFil.objects.create(
                demande=d2, auteur=P,
                contenu='Plans reçus. Je commence l\'analyse des métrés. '
                        'Délai estimé : 5 jours ouvrés pour le chiffrage complet.',
                is_internal=True,
            )
            self.stdout.write(f'    + Demande : {d2.reference} — {d2.client_nom} ({d2.get_statut_display()})')

        # ── Demande 3 : Complexe Ibn Rochd — EN_ATTENTE ────────────
        d3, created = DemandeChiffrage.objects.get_or_create(
            client_nom='Fondation Ibn Rochd — Complexe Scolaire',
            defaults={
                'description':         'Appel d\'offre public — fourniture et pose portes coupe-feu, '
                                       'bibliothèques salles et mobilier réception.',
                'delai_souhaite':      now.date() + timedelta(days=12),
                'urgence':             DemandeChiffrage.Urgence.CRITIQUE,
                'contraintes_techniques': 'Portes coupe-feu EI60 obligatoires. Normes EN 1634-1.',
                'statut':              DemandeChiffrage.Statut.EN_ATTENTE,
                'commercial':          S,
                'lead':                leads.get('ibnrochd'),
            },
        )
        if created:
            HistoriqueAction.objects.create(
                demande=d3, auteur=S, action='Demande soumise — urgence critique (AO public)',
                nouveau_statut=DemandeChiffrage.Statut.EN_ATTENTE,
            )
            self.stdout.write(f'    + Demande : {d3.reference} — {d3.client_nom} ({d3.get_statut_display()})')

        total = DemandeChiffrage.objects.count()
        self.stdout.write(f'    → {total} demandes de chiffrage au total')

    # ────────────────────────────────────────────────────────────
    # Notifications
    # ────────────────────────────────────────────────────────────

    def _create_notifications(self, users, projects):
        from apps.notifications.models import Notification
        from apps.projects.models import Task
        from django.contrib.contenttypes.models import ContentType

        self.stdout.write('\n[6/6] Notifications…')

        ct_task = ContentType.objects.get_for_model(Task)
        notifs = [
            (users['jean.moreau'], users['sophie.martin'],
             Notification.Type.TASK_ACTIVATED,
             'Tâche activée : Assemblage caissons',
             'La tâche « Assemblage caissons » sur le projet BC-2024-001 est maintenant active.'),
            (users['thomas.petit'], users['sophie.martin'],
             Notification.Type.TASK_ASSIGNED,
             'Nouvelle affectation',
             'Vous avez été affecté à « Réglages portes coulissantes » sur le projet Dressing Lambert.'),
            (users['pierre.dubois'], users['admin'],
             Notification.Type.TASK_OVERDUE,
             'Tâche en retard',
             'La tâche « Calcul giration et tirage » sur Escalier Moreau arrive à échéance.'),
            (users['sophie.martin'], None,
             Notification.Type.PROJECT_UPDATE,
             'Projet Cuisine Durand — avancement 48%',
             'Le projet BC-2024-001 a progressé : 48% des tâches sont terminées.'),
        ]
        for recipient, sender, ntype, title, msg in notifs:
            Notification.objects.get_or_create(
                recipient=recipient,
                notification_type=ntype,
                title=title,
                defaults={'sender': sender, 'message': msg},
            )

        self.stdout.write(f'    + {len(notifs)} notifications créées')
