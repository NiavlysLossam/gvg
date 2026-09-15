---
title: "Story 5.3 : Scripts de Déploiement (Docker Compose & Script Natif Ubuntu)"
type: 'feature'
created: '2026-09-15'
status: 'done'
baseline_commit: '81a8ec220d56e80f1153d3fe044c792bb8dead5d'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '_bmad-output/implementation-artifacts/epic-5-context.md'
  - '_bmad-output/planning-artifacts/architecture/architecture-gvg-2026-09-04/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Les organisateurs de vide-greniers sont souvent des associations loi 1901 ou des communes rurales disposant d'infrastructures d'hébergement hétérogènes. Certaines équipes disposent d'un serveur conteneurisé Docker, tandis que d'autres louent un simple serveur VPS Ubuntu vierge sans Docker ni compétences DevOps avancées. Le projet doit fournir des scripts et configurations d'installation automatisés "clé en main", garantissant le démarrage complet de la base PostGIS, l'exécution automatique des migrations Alembic, la compilation du frontend, le reverse-proxy Nginx et le service démon systemd.

**Approach:**
1. Sécuriser et enrichir la configuration Docker Compose (`docker-compose.yml` et `docker-compose.prod.yml`) :
   - Créer un `backend/entrypoint.sh` exécutable qui lance systématiquement `alembic upgrade head` avant de démarrer Uvicorn.
   - S'assurer que `backend/Dockerfile` installe toutes les dépendances C pour WeasyPrint (`libcairo2`, `libpango-1.0-0`, `fonts-liberation`, etc.) et configure l'entrypoint.
   - Fournir une configuration de production conteneurisée avec reverse-proxy Nginx sur le port 80.
2. Durcir et valider le script d'installation natif Ubuntu (`scripts/install-ubuntu.sh`) :
   - Vérification des droits root/sudo, installation automatique de PostgreSQL 16, PostGIS, Python 3.12, Nginx, Node.js 20 LTS et polices d'écriture WeasyPrint (`fonts-liberation`).
   - Création de l'utilisateur dédié `gvg`, initialisation de la base de données, configuration de l'environnement virtuel Python et exécution des migrations Alembic.
   - Configuration du service systemd (`deploy/systemd/gvg.service`) avec `PYTHONPATH` explicite et redémarrage automatique en cas de panne (`Restart=always`).
   - Configuration du reverse-proxy Nginx (`deploy/nginx/gvg.conf`) servant le build React statique sur `/` et relayant les requêtes API/Swagger vers `127.0.0.1:8000`.
3. Fournir un fichier de configuration universel documenté (`.env.example`) à la racine :
   - Centraliser toutes les variables configurables par l'utilisateur (identifiants PostgreSQL, nom du site, port/domaine d'accès, clés Stripe, paramètres SMTP).
   - Prise en charge transparente de ce fichier `.env` à la fois par Docker Compose (`env_file`) et par le script natif Ubuntu (qui charge les variables ou déploie le fichier `.env` dans `/opt/gvg/backend/.env`).
4. Créer une suite de tests automatisés (`backend/tests/test_deployment.py`) validant la conformité syntaxique bash (`bash -n`), la structure YAML de Docker Compose, la complétude de `.env.example`, les services systemd et la configuration Nginx.

## Boundaries & Constraints

**Always:**
- Respecter strictement la décision architecturale AD-8 (double cible de déploiement de niveau égal : conteneurs Docker & script natif Ubuntu).
- Fournir à la racine du projet un fichier modèle `.env.example` complet et commenté en français, documentant chaque variable optionnelle ou obligatoire.
- Docker Compose et le script natif Ubuntu doivent tous les deux pouvoir lire et exploiter directement ce même fichier `.env` sans divergence de nommage des variables.
- Toute exécution de conteneur backend doit appliquer automatiquement les migrations de schéma (`alembic upgrade head`) au démarrage pour éviter toute incohérence de tables.
- `scripts/install-ubuntu.sh` doit être idempotent, déclarer `set -euo pipefail`, préserver un éventuel fichier `.env` pré-rempli par l'administrateur (ou en générer un sécurisé à partir de `.env.example`), et fonctionner sur Ubuntu 22.04 LTS et 24.04 LTS.
- La configuration Nginx doit router les requêtes `/api`, `/docs`, `/redoc`, `/openapi.json` et `/health` vers le backend Uvicorn, et servir l'application monopage React avec gestion des routes client (`try_files $uri $uri/ /index.html`).

**Never:**
- Ne jamais coder en dur de mots de passe de production non personnalisables dans les scripts.
- Ne jamais écraser silencieusement un fichier `.env` existant configuré par l'utilisateur.
- Ne jamais nécessiter de manipulations manuelles dans la base de données ou de commandes SQL manuelles pour démarrer l'application.

## I/O & Edge-Case Matrix

| Scénario | Données en entrée | Résultat attendu | Gestion d'erreur / Robustesse |
|---|---|---|---|
| Démarrage Docker Compose | `docker compose up -d` avec `.env` présent | Démarre PostGIS (`db`), exécute les migrations Alembic via `entrypoint.sh`, démarre FastAPI (`backend`) et React (`frontend`) avec les variables du `.env` | `depends_on: db: condition: service_healthy` évite le crash du backend avant que PostgreSQL soit prêt |
| Déploiement Ubuntu avec `.env` pré-rempli | `bash scripts/install-ubuntu.sh` avec `.env` dans le dossier source | Le script détecte le `.env`, conserve les mots de passe et paramètres choisis par l'utilisateur pour initialiser la DB et le backend | Préserve les clés personnalisées sans régénération destructive |
| Déploiement Ubuntu sans `.env` initial | `bash scripts/install-ubuntu.sh` sur machine vierge | Copie `.env.example` vers `.env`, génère un mot de passe DB fort via `openssl rand -hex 16` et configure l'application | Configuration prête à l'emploi avec secrets générés |
| Exécution sans root sur Ubuntu | Utilisateur non root lance `bash scripts/install-ubuntu.sh` | Arrêt immédiat avec message explicite "This script must be run as root or with sudo" | Code de sortie 1 |
| Redémarrage de la machine | Reboot du serveur Ubuntu hôte | `gvg.service` (systemd) et `nginx` redémarrent automatiquement au boot | `[Install] WantedBy=multi-user.target` et `Restart=always` |
| Rendu PDF WeasyPrint en conteneur | Génération d'attestation ou feuille d'émargement | Polices nettes et mise en page parfaite sans polices manquantes | `fonts-liberation` et `shared-mime-info` installés dans l'image |

</frozen-after-approval>

## Code Map

- `.env.example` -- Modèle officiel de configuration unifié pour les déploiements Docker et natifs Ubuntu (DB, Domaine, Stripe, SMTP, etc.).
- `backend/entrypoint.sh` -- Script d'entrée conteneur exécutant les migrations Alembic (`alembic upgrade head`) avant `exec "$@"`.
- `backend/Dockerfile` -- Déclaration des bibliothèques C pour WeasyPrint, polices Liberation, ajout et exécution de `entrypoint.sh`.
- `docker-compose.yml` -- Configuration multi-conteneurs (PostGIS `db` avec healthcheck, `backend` avec entrypoint, `frontend`, prise en charge de `env_file`).
- `docker-compose.prod.yml` -- Configuration Docker Compose pour déploiement de production complet avec Nginx sur le port 80.
- `deploy/nginx/gvg.conf` & `deploy/nginx/nginx.prod.conf` -- Configurations Nginx pour hôte natif et conteneur de production.
- `deploy/systemd/gvg.service` -- Définition du service systemd avec variables d'environnement, redémarrage automatique et sécurité.
- `scripts/install-ubuntu.sh` -- Script d'installation automatisé complet pour Ubuntu 22.04 / 24.04 LTS gérant le fichier `.env`.
- `backend/tests/test_deployment.py` -- Tests automatisés de validation syntaxique bash, YAML Compose, conformité `.env.example`, service systemd et Nginx.

## Tasks & Acceptance

**Execution:**
- [x] `.env.example` -- Créer le fichier de configuration modèle universel commenté en français.
- [x] `backend/entrypoint.sh` -- Créer le script d'entrée conteneur exécutant les migrations Alembic automatiquement.
- [x] `backend/Dockerfile` -- Intégrer `entrypoint.sh` et les polices `fonts-liberation`.
- [x] `docker-compose.yml` & `docker-compose.prod.yml` -- Mettre à jour et finaliser les configurations Docker Compose (dev et prod) avec support `.env`.
- [x] `deploy/systemd/gvg.service` -- Mettre à jour le service systemd avec `PYTHONPATH` explicite.
- [x] `scripts/install-ubuntu.sh` -- Adapter et enrichir le script d'installation avec la gestion du fichier `.env`, les polices et l'idempotence.
- [x] `backend/tests/test_deployment.py` -- Écrire la suite de tests automatisés validant tous les artefacts de déploiement et la cohérence de `.env.example`.

**Acceptance Criteria:**
- Given un administrateur préparant son déploiement, when il ouvre `.env.example`, then toutes les variables configurables (base de données, nom du site, clés Stripe, paramètres SMTP, nom de domaine) sont documentées avec des exemples clairs.
- Given un environnement Docker avec un fichier `.env`, when l'administrateur exécute `docker compose up -d`, then la base PostGIS et le backend démarrent en utilisant les variables configurées et l'entrypoint applique automatiquement les migrations Alembic.
- Given un serveur Ubuntu avec ou sans fichier `.env` préalable, when l'administrateur exécute `bash scripts/install-ubuntu.sh`, then le script respecte la configuration utilisateur (ou initialise un `.env` sécurisé depuis le modèle) et configure PostgreSQL, Python, Nginx et le service systemd sans erreur.
- Given la suite de tests `backend/tests/test_deployment.py`, when les tests sont lancés, then tous les fichiers de déploiement (Compose, Dockerfile, Nginx, systemd, script bash, `.env.example`) sont vérifiés et valides.

## Implementation Notes

- Création du modèle universel `.env.example` à la racine, commenté en français et structuré en 5 blocs (Général, Base de données PostGIS, Réseau/CORS, Stripe, SMTP).
- Création de `backend/entrypoint.sh` exécutable (+x) avec boucle d'attente résiliente de la base de données et exécution systématique de `alembic upgrade head` avant le démarrage de la commande principale.
- Mise à jour de `backend/Dockerfile` incluant `fonts-liberation` pour WeasyPrint, configuration de `ENTRYPOINT ["/app/entrypoint.sh"]` et droits d'exécution.
- Mise à jour de `docker-compose.yml` avec support `env_file`, variables d'environnement paramétrées avec valeurs de repli et healthcheck PostGIS.
- Création de `docker-compose.prod.yml` orchestrant `db`, `backend` (uvicorn avec workers), `frontend` (compilation production) et `nginx` (reverse proxy sur le port 80).
- Création de `deploy/nginx/nginx.prod.conf` pour conteneur Docker avec routage SPA et reverse proxy vers `http://backend:8000`.
- Mise à jour de `deploy/systemd/gvg.service` avec déclaration explicite de `Environment="PYTHONPATH=/opt/gvg/backend"`.
- Enrichissement de `scripts/install-ubuntu.sh` avec gestion idempotente du `.env` (préservation si existant, génération de mot de passe fort via openssl si initialisation depuis `.env.example`), installation de `fonts-liberation`, vérification des droits root et configuration systemd/Nginx.
- Création de `backend/tests/test_deployment.py` avec 11 tests automatisés validant la syntaxe bash (`bash -n`), Dockerfile, YAML compose, `.env.example`, service systemd, Nginx natif et prod.

## Review Triage Log

- **Verification Gap / Blind / Edge Case Review Findings**:
  - `backend/entrypoint.sh` retry loop logic: Fixed potential failure when reaching MAX_RETRIES, added default command fallback (`uvicorn app.main:app`), and supported environment-configurable retry limits (`MIGRATION_MAX_RETRIES`, `MIGRATION_RETRY_INTERVAL`). [Action: Patched + Added test `test_entrypoint_execution_success` & `test_entrypoint_execution_failure_retry` in `test_deployment.py`].
  - `docker-compose.prod.yml` startup race condition: `nginx` started before `frontend` builder finished building static files. [Action: Patched `depends_on: frontend: condition: service_completed_successfully, backend: condition: service_started`, and set `restart: "no"` on `frontend`].
  - Nginx Stripe webhooks routing: In both `deploy/nginx/nginx.prod.conf` and `deploy/nginx/gvg.conf`, requests to `/webhooks/stripe` were not caught by API reverse proxy regex, causing 405 error from static SPA routing. [Action: Added `webhooks` to location regex in both Nginx configs, and added assertions in `test_deployment.py`].
  - Native Ubuntu installer robustness: `scripts/install-ubuntu.sh` missed `systemctl enable nginx`, lacked a timeout on PostgreSQL wait loop, and didn't grant schema permissions under PostgreSQL 15+. [Action: Added `systemctl enable nginx`, 30s timeout on PostgreSQL readiness check, and public schema permissions `GRANT ALL ON SCHEMA public TO $DB_USER` / `ALTER SCHEMA public OWNER TO $DB_USER`].
  - Configuration completeness: Added `VITE_API_URL` to `.env.example` and added `${DATABASE_URL:-...}` fallbacks in Compose files.
  - Added `.dockerignore` files at repo root, `backend/`, and `frontend/`.

## Verification

**Commands:**
- `pytest backend/tests/test_deployment.py` -- 14/14 tests pass.
- `bash -n scripts/install-ubuntu.sh` -- syntax ok.
- `bash -n backend/entrypoint.sh` -- syntax ok.
- `pytest backend/tests/` -- 250/250 tests pass (0 regressions).
- `npm --prefix frontend run build` -- built in 7.12s without error.

