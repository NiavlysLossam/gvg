# Guide d'Installation et de Déploiement — GVG (Gestion de Vide-Greniers)

Bienvenue dans le guide officiel d'installation de **GVG (Gestion de Vide-Greniers)**, solution libre et moderne d'organisation de vide-greniers, brocantes et foires à tout, dotée d'un placement cartographique vectoriel interactif, d'un paiement sécurisé Stripe, d'un système d'e-mails transactionnels et de la conformité réglementaire (attestation légale PDF et feuille d'émargement officielle).

Ce document présente les **3 méthodes d'installation** disponibles :
1. [Méthode 1 : Déploiement Conteneurisé Docker Compose (Recommandé)](#méthode-1--déploiement-conteneurisé-docker-compose-recommandé)
2. [Méthode 2 : Déploiement Natif Automatisé sur Serveur Ubuntu (22.04 / 24.04 LTS)](#méthode-2--déploiement-natif-automatisé-sur-serveur-ubuntu)
3. [Méthode 3 : Installation Manuelle Locale pour Développeur](#méthode-3--installation-manuelle-locale-pour-développeur)

---

## Prérequis Généraux

### Spécifications Matérielles Minimales
- **Processeur (CPU)** : 1 vCPU (2 vCPU recommandés pour les événements de grande taille).
- **Mémoire Vive (RAM)** : 1 Go minimum (2 Go recommandés pour la compilation frontend et le rendu PDF WeasyPrint).
- **Espace Disque** : 5 Go d'espace libre (incluant Docker ou PostgreSQL et les dépendances).
- **Ports Réseau** :
  - Port `80` (HTTP) et `443` (HTTPS).
  - Port `8000` (API FastAPI en développement).
  - Port `5173` (Vite dev server en développement).
  - Port `5432` (PostgreSQL / PostGIS).

---

## Méthode 1 : Déploiement Conteneurisé Docker Compose (Recommandé)

Cette méthode est la plus simple et la plus fiable, tant pour la mise en production sur un serveur que pour tester le projet localement.

### Prérequis Docker
- [Docker Engine](https://docs.docker.com/engine/install/) (version 24.0 ou supérieure)
- [Docker Compose](https://docs.docker.com/compose/install/) (version 2.20 ou supérieure, commande `docker compose`)

### Étape 1 : Cloner le Répertoire et Préparer l'Environnement

```bash
# 1. Cloner le projet
git clone https://github.com/votre-compte/gvg.git
cd gvg

# 2. Copier le fichier de configuration modèle
cp .env.example .env
```

### Étape 2 : Configurer les Variables d'Environnement (`.env`)

Ouvrez le fichier `.env` avec votre éditeur favori (`nano .env`, `vim .env`...) et ajustez au minimum :
- `POSTGRES_PASSWORD` : définissez un mot de passe fort (ex: `openssl rand -hex 16`).
- `FRONTEND_BASE_URL` : l'adresse de votre site (ex: `http://localhost` ou `https://vide-grenier.mon-village.fr`).
- `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` : vos clés Stripe (voir section [Configuration Stripe](#configuration-stripe)).
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` : vos identifiants d'envoi d'e-mails (voir section [Configuration SMTP](#configuration-smtp)).

> **Remarque :** Si vous ne renseignez pas vos identifiants SMTP immédiatement, GVG bascule automatiquement en **mode simulation** : les e-mails sont journalisés dans la base sans provoquer d'erreur.

---

### Option A : Lancement en Production (Nginx sur Port 80)

Le fichier `docker-compose.prod.yml` orchestre en un clic l'infrastructure de production complète :
- **`db`** : Base de données PostgreSQL 16 avec extension spatiale PostGIS 3.4.
- **`backend`** : Serveur FastAPI Uvicorn multi-workers, avec migration automatique du schéma (`alembic upgrade head`) au démarrage via son entrypoint.
- **`frontend`** : Conteneur de compilation statique (Vite + React) qui assemble les fichiers de production vers un volume partagé.
- **`nginx`** : Reverse-proxy haute performance servant le frontend statique sur `/` et relayant les requêtes API (`/api`), Swagger (`/docs`) et Webhooks Stripe (`/webhooks`) vers le backend.

```bash
# Démarrer en arrière-plan et compiler les images
docker compose -f docker-compose.prod.yml up -d --build
```

**Accès à l'application :**
- **Application Web** : `http://localhost` (ou l'adresse IP / domaine de votre serveur).
- **Documentation Swagger de l'API** : `http://localhost/docs`.
- **Statut de santé du backend** : `http://localhost/health`.

**Commandes utiles en production :**
```bash
# Consulter les logs en temps réel
docker compose -f docker-compose.prod.yml logs -f

# Logs du backend uniquement
docker compose -f docker-compose.prod.yml logs -f backend

# Vérifier l'état des conteneurs
docker compose -f docker-compose.prod.yml ps

# Arrêter les services
docker compose -f docker-compose.prod.yml down
```

---

### Option B : Lancement en Développement (Hot-Reload)

Pour modifier le code en direct avec rechargement automatique :

```bash
docker compose up -d --build
```

**Accès en développement :**
- **Frontend Vite (Hot Reload)** : `http://localhost:5173`
- **Backend FastAPI (Reload auto)** : `http://localhost:8000`
- **Documentation interactive API** : `http://localhost:8000/docs`

---

## Méthode 2 : Déploiement Natif Automatisé sur Serveur Ubuntu

Si vous hébergez GVG sur un serveur VPS Ubuntu 22.04 LTS ou 24.04 LTS sans Docker, un script d'installation clé en main est fourni conformément à la décision d'architecture **AD-8**.

### Ce que le script automatise pour vous :
1. Mise à jour système et installation des paquets APT : PostgreSQL 16, PostGIS, Python 3.12, Nginx, Node.js 20 LTS, WeasyPrint C-libraries (`libcairo2`, `libpango`, `fonts-liberation`).
2. Création d'un utilisateur système dédié `gvg` pour exécuter les processus sans privilèges root.
3. Déploiement sécurisé du fichier `.env` (si non présent, copie de `.env.example` avec génération automatique d'un mot de passe fort via `openssl rand -hex 16`).
4. Création de la base de données PostgreSQL et de l'extension spatiale PostGIS, avec attribution des droits sur le schéma public.
5. Création de l'environnement virtuel Python (`.venv`) et installation des dépendances backend.
6. Exécution automatique des migrations de schéma de base de données (`alembic upgrade head`).
7. Compilation de l'application frontend React en fichiers statiques dans `/opt/gvg/frontend/dist`.
8. Installation, activation et démarrage du démon systemd `gvg.service` (redémarrage automatique en cas de panne).
9. Configuration et activation du reverse-proxy Nginx avec support SPA (`try_files`) et relais API/Webhooks.

### Procédure d'installation Ubuntu :

```bash
# 1. Cloner le projet ou le téléverser sur le serveur
git clone https://github.com/votre-compte/gvg.git /opt/gvg
cd /opt/gvg

# 2. (Optionnel mais recommandé) Pré-configurer votre .env
cp .env.example .env
nano .env  # Renseignez vos clés Stripe, SMTP, etc.

# 3. Lancer le script d'installation avec les droits root
sudo bash scripts/install-ubuntu.sh
```

À la fin de l'exécution, le script affiche un récapitulatif avec les accès :
```text
[SUCCESS] GVG has been successfully installed and started!
[INFO] Access GVG at: http://localhost
[INFO] API Docs available at: http://localhost/docs
[INFO] Database credentials saved in: /opt/gvg/backend/.env
```

### Administration des Services Ubuntu :

```bash
# Vérifier l'état du serveur backend GVG
sudo systemctl status gvg.service

# Consulter les logs du backend en direct
sudo journalctl -u gvg.service -f

# Redémarrer l'application backend
sudo systemctl restart gvg.service

# Vérifier et recharger la configuration Nginx
sudo nginx -t
sudo systemctl reload nginx
```

---

## Méthode 3 : Installation Manuelle Locale pour Développeur

Cette méthode s'adresse aux développeurs souhaitant exécuter et déboguer le code directement sur leur poste de travail Linux ou macOS.

### 1. Prérequis Système
- **Python 3.12** avec `venv` et `pip`
- **Node.js 20+** et `npm`
- **PostgreSQL 16** avec extension **PostGIS 3.4**
- Bibliothèques C pour WeasyPrint :
  - **Ubuntu/Debian** : `sudo apt install libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 shared-mime-info fonts-liberation libpq-dev`
  - **macOS (Homebrew)** : `brew install cairo pango gdk-pixbuf libffi postgis`

### 2. Base de données locale

```bash
sudo -u postgres psql -c "CREATE USER gvg WITH PASSWORD 'gvg_secret';"
sudo -u postgres psql -c "CREATE DATABASE gvg OWNER gvg;"
sudo -u postgres psql -d gvg -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

### 3. Backend FastAPI

```bash
# 1. Aller dans le dossier backend
cd backend

# 2. Créer et activer l'environnement virtuel Python
python3 -m venv .venv
source .venv/bin/activate

# 3. Installer les dépendances
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configurer les variables locales
cp ../.env.example .env
# Vérifier que DATABASE_URL=postgresql+psycopg://gvg:gvg_secret@localhost:5432/gvg

# 5. Appliquer les migrations de base de données
alembic upgrade head

# 6. Démarrer le serveur de développement Uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Frontend React

Dans un autre terminal :

```bash
# 1. Aller dans le dossier frontend
cd frontend

# 2. Installer les dépendances Node.js
npm install

# 3. Démarrer le serveur de développement Vite
npm run dev
```

L'application est immédiatement accessible sur `http://localhost:5173`.

---

## Guide de Configuration du fichier `.env`

Toutes les variables sont décrites et commentées dans le fichier [`.env.example`](.env.example). Voici le détail des sections :

### 1. Paramètres Généraux
| Variable | Description | Exemple |
|---|---|---|
| `PROJECT_NAME` | Nom public affiché sur le site et dans les e-mails | `"GVG (Gestion de Vide-Greniers)"` |
| `ENVIRONMENT` | Environnement d'exécution (`development` ou `production`) | `production` |
| `API_V1_STR` | Préfixe d'URL pour les routes de l'API REST | `/api/v1` |

### 2. Base de Données PostGIS
| Variable | Description | Exemple |
|---|---|---|
| `POSTGRES_USER` | Nom du compte utilisateur PostgreSQL | `gvg` |
| `POSTGRES_PASSWORD` | Mot de passe de la base de données | `votre_mot_de_passe_secret` |
| `POSTGRES_DB` | Nom de la base de données | `gvg` |
| `POSTGRES_PORT` | Port d'écoute PostgreSQL | `5432` |
| `DATABASE_URL` | Chaîne de connexion SQLAlchemy (driver psycopg 3) | `postgresql+psycopg://gvg:secret@localhost:5432/gvg` |

### 3. Réseau, Domaine & Sécurité CORS
| Variable | Description | Exemple |
|---|---|---|
| `FRONTEND_BASE_URL` | URL racine publique utilisée pour générer les liens dans les e-mails | `https://vide-grenier.mon-village.fr` |
| `VITE_API_URL` | URL de l'API backend utilisée par le frontend | `https://vide-grenier.mon-village.fr` |
| `CORS_ORIGINS` | Origines autorisées (séparées par des virgules, sans espaces) | `https://vide-grenier.mon-village.fr` |
| `UPLOAD_DIR` | Dossier local de stockage des fonds de plan importés | `uploads` |

<a id="configuration-stripe"></a>
### 4. Configuration Stripe (Paiements Sécurisés)
GVG s'intègre avec **Stripe Elements** et les webhooks Stripe pour le paiement sécurisé par carte bancaire.

1. Connectez-vous sur votre [Dashboard Stripe](https://dashboard.stripe.com/).
2. Dans **Développeurs > Clés d'API**, copiez votre **Clé secrète** (`sk_test_...` ou `sk_live_...`) et votre **Clé publiable** (`pk_test_...` ou `pk_live_...`).
3. Dans **Développeurs > Webhooks**, cliquez sur **Ajouter un point de terminaison** :
   - **URL du point de terminaison** : `https://votre-domaine.fr/webhooks/stripe`
   - **Événements à écouter** :
     - `payment_intent.succeeded`
     - `payment_intent.payment_failed`
     - `payment_intent.amount_capturable_updated`
     - `payment_intent.canceled`
     - `charge.refunded`
4. Cliquez sur **Révéler** sous "Secret de signature" et copiez la valeur (`whsec_...`).
5. Renseignez ces 3 valeurs dans votre fichier `.env` :
   ```env
   STRIPE_SECRET_KEY=sk_live_...
   STRIPE_PUBLISHABLE_KEY=pk_live_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```

<a id="configuration-smtp"></a>
### 5. Configuration SMTP (E-mails Transactionnels)
Pour que GVG puisse envoyer les e-mails de confirmation, les convocations J-7 et J-2, les attestations et les annonces manuelles :

```env
SMTP_HOST=smtp.votrefournisseur.com
SMTP_PORT=587
SMTP_USER=contact@votre-domaine.fr
SMTP_PASSWORD=votre_mot_de_passe_application
SMTP_TLS=True
SMTP_SSL=False
EMAILS_FROM_EMAIL=noreply@votre-domaine.fr
EMAILS_FROM_NAME="GVG - Vide-Greniers"
```

> **Fournisseurs courants :**
> - **Gmail / Google Workspace** : `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_TLS=True` (nécessite de créer un *Mot de passe d'application* dans votre compte Google).
> - **Brevo (Sendinblue)** : `SMTP_HOST=smtp-relay.brevo.com`, `SMTP_PORT=587`, `SMTP_TLS=True`.
> - **OVH** : `SMTP_HOST=ssl0.ovh.net`, `SMTP_PORT=587`, `SMTP_TLS=True`.
> - **Infomaniak** : `SMTP_HOST=mail.infomaniak.com`, `SMTP_PORT=587`, `SMTP_TLS=True`.

---

## Sécurisation HTTPS avec Let's Encrypt (Certbot)

En production, l'utilisation de HTTPS est **indispensable** (notamment pour l'affichage de Stripe Elements et la protection des données exposants).

Sur un serveur Ubuntu natif :

```bash
# 1. Installer Certbot et son plugin Nginx
sudo apt update
sudo apt install -y certbot python3-certbot-nginx

# 2. Obtenir et appliquer automatiquement le certificat SSL
sudo certbot --nginx -d vide-grenier.mon-village.fr

# 3. Vérifier le renouvellement automatique
sudo certbot renew --dry-run
```

Certbot configure automatiquement les règles de redirection HTTP vers HTTPS dans votre fichier Nginx.

---

## Sauvegarde et Maintenance

### Sauvegarde Quotidienne de la Base de Données

Créez un script de sauvegarde ou ajoutez une ligne dans votre crontab (`crontab -e`) :

**En déploiement natif Ubuntu :**
```bash
# Sauvegarde gzip horodatée
pg_dump -U gvg -d gvg | gzip > /var/backups/gvg_$(date +%Y%m%d_%H%M%S).sql.gz
```

**En déploiement Docker Compose :**
```bash
# Sauvegarde via le conteneur db
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U gvg gvg | gzip > /var/backups/gvg_docker_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Sauvegarde des Fichiers Uploadés
Pensez à inclure le dossier `uploads/` (fonds de plans importés par les organisateurs) dans vos sauvegardes régulières :
```bash
tar -czf /var/backups/gvg_uploads_$(date +%Y%m%d).tar.gz /opt/gvg/backend/uploads/
```

### Mise à Jour de l'Application

Pour déployer une nouvelle version du code :

**Avec Docker Compose :**
```bash
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build
```
*(L'entrypoint exécutera automatiquement les nouvelles migrations Alembic).*

**Avec Ubuntu Natif :**
```bash
cd /opt/gvg
git pull origin main

# Mettre à jour les dépendances backend et exécuter les migrations
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
cd backend && alembic upgrade head && cd ..

# Recompiler le frontend
cd frontend && npm install && npm run build && cd ..

# Redémarrer le service backend
sudo systemctl restart gvg.service
```

---

## Dépannage Fréquent (FAQ)

### 1. `alembic upgrade head` échoue avec une erreur de connexion
- Vérifiez que PostgreSQL est bien démarré (`sudo systemctl status postgresql` ou `docker compose ps`).
- Vérifiez la syntaxe de `DATABASE_URL` dans votre fichier `.env`. Pour Docker, l'hôte est `db`, alors que pour une installation native c'est `localhost` ou `127.0.0.1`.

### 2. Le rendu PDF d'attestation échoue ou manque de polices
- Vérifiez que les dépendances WeasyPrint et polices Liberation sont installées (`sudo apt install fonts-liberation libcairo2 libpango-1.0-0`). Dans Docker, elles sont déjà incluses dans l'image `backend/Dockerfile`.

### 3. Les e-mails ne partent pas
- Consultez les logs du backend (`docker compose logs backend` ou `journalctl -u gvg -f`).
- Si les identifiants SMTP sont erronés, le backend consigne l'erreur dans la table `email_logs` avec le statut `failed` sans faire crasher la requête de l'utilisateur.

---

## Support et Assistance

Pour toute question, anomalie ou suggestion :
- Consultez le code source et les issues sur le dépôt GitHub.
- Consultez la documentation interactive des API sur `/docs` (Swagger UI).

