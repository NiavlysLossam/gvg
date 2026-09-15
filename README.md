# GVG — Gestion de Vide-Greniers

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg)](https://reactjs.org/)
[![PostGIS](https://img.shields.io/badge/PostGIS-16--3.4-336791.svg)](https://postgis.net/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.4-38B2AC.svg)](https://tailwindcss.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**GVG (Gestion de Vide-Greniers)** est une application web complète, moderne et libre conçue pour simplifier l'organisation de vide-greniers, brocantes et foires à tout par les comités des fêtes, mairies et associations loi 1901.

---

## ✨ Fonctionnalités Principales

- 🗺️ **Cartographie & Placement Vectoriel Interactif** :
  - Calibrage de fonds de plan (plans cadastraux, images aériennes ou croquis de salle des fêtes).
  - Dessin vectoriel d'emplacements avec Leaflet et Geoman.
  - Magnétisme (snap-to-grid), duplication rapide et numérotation automatique par allée.
- 📱 **Portail Public Exposant Mobile-First** :
  - Plan interactif fluide sur smartphone et ordinateur pour choisir ses stands contigus en direct.
  - Verrouillage atomique temporaire (15 minutes) anti-collision de réservation.
  - Formulaire invité sans création de compte mot de passe (*passwordless* avec tokens HMAC).
- 💳 **Paiement Sécurisé Stripe & Gestion Hors-Ligne** :
  - Intégration Stripe Elements (CB, Apple Pay, Google Pay) avec confirmation asynchrone par webhooks.
  - Saisie manuelle en guichet pour les règlements en espèces ou par chèque bancaire.
- 🛡️ **Modération, Annulations & Arbitrage** :
  - Modération optionnelle des dossiers avant encaissement.
  - Portail d'annulation exposant autonome avec calcul automatique des retenues.
  - Arbitrage des litiges et annulation générale d'urgence avec remboursement groupé Stripe.
- ✉️ **Module de Communication & E-mailing Transactionnel** :
  - Gabarits Jinja2 responsives (confirmations, reçus, rappels opérationnels J-7 et J-2).
  - Envoi manuel d'e-mails groupés avec tags dynamiques (`{{exposant.nom}}`, `{{commande.emplacement}}`) et aperçu en direct.
  - Audit complet de chaque notification envoyée (`email_logs`).
- ⚖️ **Conformité Légale & Émargement Jour J** :
  - Génération automatique de l'**Attestation sur l'honneur légale PDF** conforme aux articles L. 310-2 et R. 310-8 du Code de commerce (1 page A4 portrait prête à signer).
  - Export de la **Feuille d'émargement officielle** pour les placiers le matin de l'événement en **PDF paysage** et en **tableur Excel (.xlsx)** multi-onglets.
- 🚀 **Déploiement Simplifié (AD-8)** :
  - Déploiement clé en main avec **Docker Compose** (dev & prod multi-conteneurs avec Nginx).
  - Script d'installation automatisé pour serveurs **Ubuntu 22.04 / 24.04 LTS**.
  - Fichier modèle de configuration universel [`.env.example`](.env.example).

---

## 🚀 Démarrage Rapide

### Déploiement avec Docker Compose (Recommandé)

```bash
# 1. Cloner le projet
git clone https://github.com/votre-compte/gvg.git
cd gvg

# 2. Configurer vos variables d'environnement
cp .env.example .env
nano .env

# 3. Lancer en production (Reverse proxy Nginx sur le port 80)
docker compose -f docker-compose.prod.yml up -d --build
```

L'application est immédiatement accessible sur `http://localhost`.

---

## 📖 Documentation Complète d'Installation

Consultez le guide détaillé pas à pas dans :
👉 [**`INSTALL.md` — Guide d'Installation et de Déploiement**](INSTALL.md)

Le guide couvre :
1. **Déploiement conteneurisé Docker Compose** (mode production avec Nginx & mode dev avec hot-reload).
2. **Déploiement natif Ubuntu** avec le script automatisé [`scripts/install-ubuntu.sh`](scripts/install-ubuntu.sh).
3. **Installation manuelle locale pour développeur** (Python 3.12, Node.js 20, PostgreSQL/PostGIS).
4. **Configuration du fichier `.env`** (PostgreSQL, Stripe, SMTP, CORS).
5. **Mise en place de certificats HTTPS gratuits avec Let's Encrypt / Certbot**.
6. **Stratégies de sauvegarde quotidienne et maintenance**.

---

## 🧪 Tests Automatisés

Le projet dispose d'une couverture de tests rigoureuse (250 tests automatisés, 100% de succès) :

```bash
# Activer l'environnement virtuel Python
source .venv/bin/activate

# Lancer la suite de tests backend complète sur PostgreSQL
pytest backend/tests/

# Lancer les tests spécifiques au déploiement et à l'infrastructure
pytest backend/tests/test_deployment.py

# Vérifier la compilation TypeScript du frontend
npm --prefix frontend run build
```

---

## 🛠️ Stack Technique

- **Backend** : Python 3.12, FastAPI, SQLAlchemy 2 (async/sync), GeoAlchemy2, Shapely, Alembic, Pydantic v2, WeasyPrint, openpyxl, psycopg 3.
- **Frontend** : React 18, TypeScript, Vite, Tailwind CSS, Leaflet, Leaflet-Geoman, Lucide React.
- **Base de données** : PostgreSQL 16 + extension spatiale PostGIS 3.4.
- **Serveur & Déploiement** : Nginx (reverse-proxy SPA et API), systemd, Docker & Docker Compose.

---

## 📄 Licence

Ce projet est sous licence MIT.
