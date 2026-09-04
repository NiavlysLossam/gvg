# Epic 1 Context: Configuration d'Événement & Éditeur de Plan Interactif

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Fournir à l'organisateur (Marc) une interface ergonomique et robuste pour déclarer les métadonnées de son vide-grenier, configurer la zone géographique ou la salle (vue satellite ou plan PNG intérieur), et concevoir son plan de masse avec tracé vectoriel de stands et numérotation séquentielle automatique.

## Stories

- Story 1.1: Initialisation du projet & Création d'Événement
- Story 1.2: Calibrage du Fond de Plan (Satellite OSM ou Image de Salle)
- Story 1.3: Dessin Vectoriel des Emplacements avec Leaflet-Geoman
- Story 1.4: Duplication Rapide, Snap-to-Grid & Numérotation Automatique

## Requirements & Constraints

- Configuration complète d'événement : titre, description, dates de début/fin, créneaux horaires d'installation (ex: 6h-8h) et d'ouverture au public (ex: 8h-18h), adresse postale, règlement intérieur, et tarif unitaire au mètre linéaire (EUR).
- Fond de plan hybride : support des tuiles cartographiques mondiales (OpenStreetMap / satellite) et téléversement d'image statique de salle des fêtes / gymnase avec coordonnées planaires `L.CRS.Simple`.
- Tracé vectoriel de stands : création de rectangles/polygones géoréférencés dans PostGIS (`geometry(Polygon, 4326)` ou planaires), avec métrage linéaire et calcul automatique du tarif.
- Numérotation séquentielle assistée : application d'un préfixe d'allée et d'un incrément numérique avec contrainte d'unicité SQL absolue au sein de l'événement.
- Double support d'exécution : conteneurs Docker Compose pour développement et déploiement standard, ainsi que script d'installation natif Ubuntu LTS (`scripts/install-ubuntu.sh`).

## Technical Decisions

- **Backend** : Python 3.12, FastAPI, Pydantic v2 pour la validation des schémas, SQLAlchemy 2.0 (async/sync) et GeoAlchemy2.
- **Base de données** : PostgreSQL 16 + extension PostGIS 3.4. Tables initiales `events` et préparation de `spots`.
- **Frontend** : React (Vite), Leaflet 1.9, `@geoman-io/leaflet-geoman-free`, Tailwind CSS.
- **API Formats** : REST standard pour le CRUD événement, GeoJSON (RFC 7946) pour les objets géographiques.
- **Arborescence** :
  - `backend/` : code API FastAPI, modèles SQLAlchemy, migrations Alembic.
  - `frontend/` : application Vite React.
  - `docker-compose.yml` : orchestration PostgreSQL PostGIS + backend + frontend.
  - `scripts/install-ubuntu.sh` : script d'installation natif pour Ubuntu 22.04/24.04.

## UX & Interaction Patterns

- Interface desktop prioritaire pour l'organisateur sur la conception de plan.
- Formulaire d'événement clair avec validations immédiates des horaires et tarifs.
- Boîte d'outils cartographiques ergonomique avec poignées de manipulation directes.

## Cross-Story Dependencies

- **Story 1.1** constitue le socle fondamental : initialisation du projet, base de données, table `events`, API FastAPI de base et squelette frontend.
- Les Stories 1.2, 1.3 et 1.4 s'appuient directement sur la table `events` et le scaffold établi par Story 1.1.

