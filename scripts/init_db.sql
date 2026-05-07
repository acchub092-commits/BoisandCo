-- Script d'initialisation PostgreSQL pour Bois&Co
-- Exécuté automatiquement par Docker au premier démarrage

-- Extension UUID (utilisée par ClientToken)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Extension pour les recherches full-text en français
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Collation française pour les tris
-- (déjà disponible avec l'image postgres:15-alpine)
