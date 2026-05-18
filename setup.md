# Bois&Co — Guide de mise en route

## Prérequis

| Outil        | Version min | Vérification        |
|--------------|-------------|---------------------|
| Python       | 3.11+       | `python --version`  |
| Docker       | 24+         | `docker --version`  |
| Node.js      | 18+         | `node --version`    |
| npm          | 9+          | `npm --version`     |
| make         | (optionnel) | `make --version`    |

## Installation complète (première fois)

### Option A — avec Make

```bash
cd boisandco
copy .env.example .env      # Windows
# cp .env.example .env      # Linux/Mac

# Éditer .env : renseigner SECRET_KEY (obligatoire en prod), garder les défauts en dev

make setup          # installe Python + Tailwind, démarre Docker, applique les migrations
make superuser      # crée votre compte admin
make fixtures       # charge les catégories de documents
python manage.py create_demo_data   # charge les données de démonstration
```

Dans un second terminal :
```bash
make tailwind       # Tailwind en mode watch
```

Puis dans le premier terminal :
```bash
make run            # http://localhost:8000
```

---

### Option B — étape par étape

```bash
# 1. Environnement Python
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# 2. Variables d'environnement
copy .env.example .env
# → éditer .env

# 3. PostgreSQL via Docker
docker-compose up -d db
# pgAdmin accessible sur http://localhost:5050

# 4. Base de données
python manage.py migrate
python manage.py loaddata fixtures/initial_data.json

# 5. Données de démonstration
python manage.py create_demo_data

# 6. Tailwind CSS (terminal séparé)
python manage.py tailwind install
python manage.py tailwind start

# 7. Lancer le serveur
python manage.py runserver
```

---

## Identifiants de démonstration

| Email                         | Rôle       | Mot de passe |
|-------------------------------|------------|--------------|
| admin@boisandco.fr            | Directeur  | `admin123`   |
| sophie.martin@boisandco.fr    | Manager    | `demo123`    |
| pierre.dubois@boisandco.fr    | Estimateur | `demo123`    |
| jean.moreau@boisandco.fr      | Atelier    | `demo123`    |
| marc.leroy@boisandco.fr       | Chauffeur  | `demo123`    |
| thomas.petit@boisandco.fr     | Poseur     | `demo123`    |

## Projets de démonstration

| Référence   | Projet                              | Statut       | Avancement |
|-------------|-------------------------------------|--------------|------------|
| BC-2024-001 | Cuisine équipée — Résidence Durand  | Production   | ~48%       |
| BC-2024-002 | Dressing sur mesure — Lambert       | Pose         | ~85%       |
| BC-2024-003 | Escalier chêne massif — Moreau      | Étude        | ~20%       |
| BC-2024-004 | Bibliothèque salon — Villa Petit    | Avant-vente  | 0%         |

## URLs

| URL                              | Description                          |
|----------------------------------|--------------------------------------|
| `http://localhost:8000`          | Tableau de bord                      |
| `http://localhost:8000/admin`    | Interface d'administration Django    |
| `http://localhost:8000/suivi/<token>/` | Portail client public (token UUID) |
| `http://localhost:5050`          | pgAdmin (PostgreSQL)                 |

## Commandes utiles

```bash
make test           # lance les tests
make shell          # shell Django (shell_plus)
make lint           # vérifie le code
make clean          # supprime les __pycache__
make docker-down    # arrête les conteneurs Docker

# Recréer les données de démo depuis zéro :
python manage.py create_demo_data --reset
```
