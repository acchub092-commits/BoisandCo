# ── Bois&Co — Makefile ─────────────────────────────────────────
# Utilisation : make <cible>
# Prérequis   : Python 3.11+, Docker Desktop, Node.js 18+

.PHONY: help install db migrate superuser fixtures run tailwind \
        shell test lint clean docker-up docker-down

PYTHON  = python
MANAGE  = $(PYTHON) manage.py
PIP     = pip

help:  ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Installation ────────────────────────────────────────────────

install:  ## Installe toutes les dépendances Python + Tailwind
	$(PIP) install -r requirements.txt
	$(MANAGE) tailwind install

# ── Base de données ─────────────────────────────────────────────

docker-up:  ## Démarre PostgreSQL + pgAdmin via Docker
	docker-compose up -d db pgadmin
	@echo "PostgreSQL : localhost:5432"
	@echo "pgAdmin    : http://localhost:5050"

docker-down:  ## Arrête les conteneurs Docker
	docker-compose down

migrate:  ## Applique toutes les migrations
	$(MANAGE) migrate

migrations:  ## Crée les nouvelles migrations
	$(MANAGE) makemigrations

superuser:  ## Crée un superutilisateur
	$(MANAGE) createsuperuser

fixtures:  ## Charge les données de démonstration
	$(MANAGE) loaddata fixtures/demo_data.json

# ── Serveur de développement ────────────────────────────────────

run:  ## Lance le serveur Django
	$(MANAGE) runserver

tailwind:  ## Lance Tailwind en mode watch (terminal séparé)
	$(MANAGE) tailwind start

# ── Utilitaires ─────────────────────────────────────────────────

shell:  ## Ouvre un shell Django
	$(MANAGE) shell_plus --ipython

test:  ## Lance les tests
	$(MANAGE) test apps/ --verbosity=2

lint:  ## Vérifie le code (flake8)
	flake8 apps/ boisandco/

clean:  ## Supprime les fichiers temporaires
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

# ── Setup complet (première installation) ───────────────────────

setup: install docker-up  ## Installation + démarrage DB
	@echo "Attente démarrage PostgreSQL…"
	sleep 3
	$(MAKE) migrate
	@echo ""
	@echo "✓ Bois&Co prêt. Créez votre superuser : make superuser"
	@echo "✓ Chargez les données démo            : make fixtures"
	@echo "✓ Lancez le serveur                   : make run"
