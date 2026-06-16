"""
Script de conversion : DATA.csv → import_leads_ready.csv
Lancer avec : python convert_data_csv.py
"""
import csv
import re

INPUT  = 'DATA.csv'
OUTPUT = 'import_leads_ready.csv'

STATUT_MAP = {
    'Prospection': 'VISITE',
    'En cours':    'CHIFFRAGE',
    'Négociation': 'OFFRE',
    'Gagné':       'GAGNEE',
    'Perdu':       'PERDUE',
}

PRIORITY_MAP = {
    'LOW':    'FAIBLE',
    'MEDIUM': 'MOYEN',
    'HIGH':   'IMPORTANT',
}

def map_proba(pct_str):
    try:
        val = int(pct_str.replace('%', '').strip())
    except Exception:
        return 'LOW'
    if val <= 10:
        return 'LOW'
    elif val <= 60:
        return 'MED'
    else:
        return 'HIGH'

def clean_budget(val):
    if not val:
        return ''
    cleaned = re.sub(r'[\s\xa0]', '', val)
    try:
        int(float(cleaned))
        return cleaned
    except Exception:
        return ''

def clean_ville(val):
    if not val or val.strip() in ('#VALEUR!', '#N/A'):
        return ''
    return val.strip()

rows_in  = 0
rows_out = 0

with open(INPUT, encoding='utf-8-sig', newline='') as fin, \
     open(OUTPUT, 'w', encoding='utf-8-sig', newline='') as fout:

    reader = csv.reader(fin, delimiter=';')
    writer = csv.writer(fout, delimiter=';')

    # En-tête de sortie
    writer.writerow([
        'commercial', 'contact', 'entreprise', 'nom_projet',
        'localisation', 'ville', 'region', 'pays',
        'email', 'telephone', 'type_client', 'type_projet', 'produits',
        'statut', 'potentiel', 'canal_origine', 'flux_type',
        'budget_mad', 'probabilite', 'commentaire',
        'date_closing_est', 'prochaine_relance',
    ])

    header = next(reader)  # skip header row

    for row in reader:
        if len(row) < 12:
            continue

        commercial = row[0].strip()
        client     = row[1].strip()
        projet     = row[2].strip()
        segment    = row[3].strip()
        ville_raw  = clean_ville(row[4])
        region     = row[5].strip()
        pays       = row[6].strip()
        budget_raw = clean_budget(row[7])
        proba_raw  = row[8].strip()
        commentaire= row[10].strip()
        statut_raw = row[11].strip()
        closing    = row[16].strip() if len(row) > 16 else ''
        priority   = row[14].strip() if len(row) > 14 else ''

        # Ignorer lignes sans commercial ou sans projet
        if not commercial or not projet:
            continue

        rows_in += 1

        statut   = STATUT_MAP.get(statut_raw, 'VISITE')
        potentiel= PRIORITY_MAP.get(priority, 'MOYEN')
        proba    = map_proba(proba_raw)

        # Localisation = ville si pas vide, sinon region
        localisation = ville_raw or region

        writer.writerow([
            commercial,      # commercial
            client,          # contact (on utilise le nom client comme contact)
            client,          # entreprise
            projet,          # nom_projet
            localisation,    # localisation
            ville_raw,       # ville
            region,          # region
            pays,            # pays
            '',              # email
            '',              # telephone
            '',              # type_client
            segment,         # type_projet
            '',              # produits
            statut,          # statut
            potentiel,       # potentiel
            '',              # canal_origine
            '',              # flux_type
            budget_raw,      # budget_mad
            proba,           # probabilite
            commentaire,     # commentaire
            closing,         # date_closing_est
            '',              # prochaine_relance
        ])
        rows_out += 1

print(f'Lignes lues     : {rows_in}')
print(f'Lignes converties: {rows_out}')
print(f'Fichier généré  : {OUTPUT}')
