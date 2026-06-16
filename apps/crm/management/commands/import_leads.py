"""
Commande d'import de leads depuis un CSV.

Usage:
    python manage.py import_leads <fichier.csv> [--dry-run] [--skip-duplicates]

Format CSV attendu (séparateur ;) :
    commercial;contact;entreprise;nom_projet;localisation;ville;region;pays;
    email;telephone;type_client;type_projet;produits;statut;potentiel;
    canal_origine;flux_type;budget_mad;probabilite;commentaire;
    date_closing_est;prochaine_relance
"""
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.crm.models import Lead

User = get_user_model()

STATUT_MAP = {
    'visite':       Lead.Status.VISITE,
    'opportunite':  Lead.Status.OPPORTUNITE,
    'qualification':Lead.Status.QUALIFICATION,
    'chiffrage':    Lead.Status.CHIFFRAGE,
    'offre':        Lead.Status.OFFRE,
    'gagnee':       Lead.Status.GAGNEE,
    'gagnée':       Lead.Status.GAGNEE,
    'perdue':       Lead.Status.PERDUE,
    'perdu':        Lead.Status.PERDUE,
    # alias depuis ancien fichier
    'prospection':  Lead.Status.VISITE,
    'en cours':     Lead.Status.CHIFFRAGE,
    'négociation':  Lead.Status.OFFRE,
    'negociation':  Lead.Status.OFFRE,
    'gagné':        Lead.Status.GAGNEE,
}

POTENTIEL_MAP = {
    'faible':    Lead.Potential.FAIBLE,
    'moyen':     Lead.Potential.MOYEN,
    'important': Lead.Potential.IMPORTANT,
    'low':       Lead.Potential.FAIBLE,
    'medium':    Lead.Potential.MOYEN,
    'high':      Lead.Potential.IMPORTANT,
}

CANAL_MAP = {
    'appel_entrant':  Lead.Canal.APPEL_ENTRANT,
    'prescription':   Lead.Canal.PRESCRIPTION,
    'salon':          Lead.Canal.SALON,
    'appel_offre':    Lead.Canal.APPEL_OFFRE,
    'recommandation': Lead.Canal.RECOMMANDATION,
    'visite_terrain': Lead.Canal.VISITE_TERRAIN,
    'autre':          Lead.Canal.AUTRE,
}

FLUX_MAP = {
    'commande': Lead.FluxType.COMMANDE,
    'marche':   Lead.FluxType.MARCHE,
    'marché':   Lead.FluxType.MARCHE,
}

PROBA_MAP = {
    'low':  Lead.Probability.LOW,
    'med':  Lead.Probability.MED,
    'high': Lead.Probability.HIGH,
}


def parse_date(val):
    if not val or val.strip() in ('', '#VALEUR!'):
        return None
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(val.strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_decimal(val):
    if not val or val.strip() in ('', '#VALEUR!'):
        return None
    cleaned = val.replace(' ', '').replace('\xa0', '').replace(',', '.').replace('%', '')
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def clean(val):
    if not val:
        return ''
    v = val.strip()
    return '' if v in ('#VALEUR!', '#N/A', 'N/A') else v


class Command(BaseCommand):
    help = 'Importe des leads depuis un fichier CSV (séparateur ;)'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Chemin vers le fichier CSV')
        parser.add_argument('--dry-run', action='store_true', help='Simuler sans écrire en base')
        parser.add_argument('--skip-duplicates', action='store_true',
                            help='Ignorer les leads dont nom_projet+entreprise existent déjà')

    def handle(self, *args, **options):
        csv_path  = options['csv_file']
        dry_run   = options['dry_run']
        skip_dup  = options['skip_duplicates']

        # Cache utilisateurs par prénom (insensible à la casse)
        user_cache = {}
        for u in User.objects.all():
            key = u.first_name.strip().lower()
            if key:
                user_cache[key] = u

        self.stdout.write(f'\n{"[DRY-RUN] " if dry_run else ""}Import leads depuis : {csv_path}\n')
        self.stdout.write(f'Utilisateurs trouves : {list(user_cache.keys())}\n')

        created = skipped_dup = skipped_err = unknown_user = 0
        rows_total = 0

        try:
            with open(csv_path, encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    # Ignorer lignes vides
                    commercial_name = clean(row.get('commercial', ''))
                    nom_projet      = clean(row.get('nom_projet', ''))
                    if not commercial_name or not nom_projet:
                        continue

                    rows_total += 1

                    # Trouver l'utilisateur commercial
                    user = user_cache.get(commercial_name.lower())
                    if not user:
                        self.stdout.write(
                            f'  [INCONNU] Commercial : "{commercial_name}" - ligne ignoree ({nom_projet})'
                        )
                        unknown_user += 1
                        continue

                    entreprise = clean(row.get('entreprise', ''))

                    # Vérifier doublon
                    if skip_dup and Lead.objects.filter(
                        project_name__iexact=nom_projet,
                        company__iexact=entreprise,
                    ).exists():
                        self.stdout.write(f'  — Doublon ignoré : {nom_projet} / {entreprise}')
                        skipped_dup += 1
                        continue

                    # Mapper les champs
                    statut_raw   = clean(row.get('statut', '')).lower()
                    potentiel_raw= clean(row.get('potentiel', '')).lower()
                    canal_raw    = clean(row.get('canal_origine', '')).lower()
                    flux_raw     = clean(row.get('flux_type', '')).lower()
                    proba_raw    = clean(row.get('probabilite', '')).lower()

                    status    = STATUT_MAP.get(statut_raw,    Lead.Status.VISITE)
                    potential = POTENTIEL_MAP.get(potentiel_raw, Lead.Potential.MOYEN)
                    canal     = CANAL_MAP.get(canal_raw, '')
                    flux      = FLUX_MAP.get(flux_raw, '')
                    proba     = PROBA_MAP.get(proba_raw, '')

                    budget    = parse_decimal(row.get('budget_mad', ''))
                    closing   = parse_date(row.get('date_closing_est', ''))
                    relance   = parse_date(row.get('prochaine_relance', ''))

                    ville  = clean(row.get('ville', ''))
                    region = clean(row.get('region', ''))
                    loc_parts = [p for p in [ville, region] if p]
                    localisation = clean(row.get('localisation', '')) or ', '.join(loc_parts)

                    commentaire = clean(row.get('commentaire', ''))

                    lead_data = dict(
                        project_name     = nom_projet,
                        company          = entreprise,
                        contact_name     = clean(row.get('contact', '')) or entreprise or nom_projet,
                        location         = localisation,
                        project_type     = clean(row.get('type_projet', '')),
                        client_type      = clean(row.get('type_client', '')),
                        products         = clean(row.get('produits', '')),
                        email            = clean(row.get('email', '')),
                        phone            = clean(row.get('telephone', '')),
                        status           = status,
                        potential        = potential,
                        canal_origine    = canal,
                        flux_type        = flux,
                        probability      = proba,
                        budget_mad       = budget,
                        end_date_est     = closing,
                        next_followup_date = relance,
                        strategic_comment  = commentaire,
                        assigned_to      = user,
                        created_by       = user,
                        workflow_status  = Lead.WorkflowStatus.VALIDATED,
                        source           = Lead.Source.DIRECTOR_ASSIGNED,
                    )

                    if dry_run:
                        self.stdout.write(
                            f'  [OK] [{user.first_name}] {nom_projet} / {entreprise} '
                            f'-> {status} | {budget or "?"} MAD'
                        )
                        created += 1
                    else:
                        try:
                            Lead.objects.create(**lead_data)
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'  [CREE] [{user.first_name}] {nom_projet} / {entreprise}'
                                )
                            )
                            created += 1
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f'  [ERR] {nom_projet} - {e}'))
                            skipped_err += 1

        except FileNotFoundError:
            raise CommandError(f'Fichier introuvable : {csv_path}')

        # Resume
        self.stdout.write('\n' + '-' * 50)
        self.stdout.write(f'Lignes traitees  : {rows_total}')
        label = 'Simules' if dry_run else 'Crees'
        self.stdout.write(self.style.SUCCESS(f'{label}           : {created}'))
        if skipped_dup:
            self.stdout.write(f'Doublons ignores : {skipped_dup}')
        if unknown_user:
            self.stdout.write(self.style.WARNING(f'Commercial inconnu: {unknown_user}'))
        if skipped_err:
            self.stdout.write(self.style.ERROR(f'Erreurs          : {skipped_err}'))
        self.stdout.write('-' * 50 + '\n')
