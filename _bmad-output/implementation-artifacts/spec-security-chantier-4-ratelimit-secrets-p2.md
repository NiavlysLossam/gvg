---
title: 'Chantier Sécurité 4 - Limitation de débit (Rate Limiting), Rotation des secrets & Durcissement Opérationnel (P2)'
type: 'security'
created: '2026-10-13'
status: 'done'
baseline_commit: 4ccec0c
route: 'dispatch'
review_loop_iteration: 1
context:
  - _bmad-output/implementation-artifacts/epic-8-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:**
L'audit de sécurité multi-agents a relevé plusieurs axes d'amélioration de niveau P2 (Opérations, Disponibilité, Protection contre les attaques par force brute & Rotation des clés) :
1. **SEC-P2-01 (Absence de limitation de débit sur l'authentification et les APIs sensibles)** :
   L'endpoint `/api/v1/auth/login` (et `/token`) ne dispose pas de limitation de requêtes (rate limiting). Un attaquant peut mener des attaques par force brute distribuées ou répétées sur les mots de passe des comptes organisateurs sans ralentissement serveur, provoquant également une surconsommation CPU due au calcul bcrypt (`12` rounds). Les endpoints publics de verrouillage (`/lock`) et de checkout méritent également une limitation Nginx dédiée.
2. **SEC-P2-02 (Configuration Nginx pour Rate Limiting & Fail2ban / Journald)** :
   Dans `deploy/nginx/gvg.conf` et `deploy/nginx/nginx.prod.conf`, aucune directive `limit_req_zone` n'est configurée pour amortir les rafales malveillantes ou les dénis de service (DoS).
3. **SEC-P2-03 (Script d'automatisation de rotation des secrets critiques)** :
   En environnement de production (Ubuntu natif), il n'existe pas d'outil automatisé sécurisé permettant à l'administrateur de renouveler à chaud la `JWT_SECRET_KEY` ou le mot de passe de base de données PostgreSQL sans corruption de fichier ni interruption prolongée du service `gvg.service`.
4. **SEC-P2-04 (Durcissement des permissions et variables de déploiement Ubuntu)** :
   Garantir l'intégrité des scripts de maintenance et du service systemd (`gvg.service`).

**Approach:**
1. **Rate Limiting Nginx (`gvg.conf` & `nginx.prod.conf`)** :
   - Définir une zone de limitation globale pour les APIs (`limit_req_zone $binary_remote_addr zone=api_general_limit:10m rate=30r/s;`).
   - Définir une zone stricte pour l'authentification et les requêtes sensibles (`limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/m;`).
   - Appliquer `limit_req zone=auth_limit burst=5 nodelay;` sur `location ~ ^/api/v1/auth/(login|token)$`.
   - Renvoyer HTTP 429 Too Many Requests (`limit_req_status 429;`).
2. **Rate Limiting applicatif FastAPI / Middleware de protection anti-bruteforce en mémoire** :
   - Implémenter un contrôleur de débit défensif en mémoire (sliding window) sur `/login` avec double vérification IP et compte, extraction d'IP via reverse proxy (`X-Forwarded-For`), et éviction mémoire.
3. **Script de rotation de secrets (`scripts/rotate-secrets.sh`)** :
   - Fournir un script robuste avec validation des privilèges root, sauvegarde horodatée du `.env` (`.env.bak.<timestamp>`), génération cryptographique forte (`openssl rand -hex 32`), mise à jour avec gestion des espaces, et rechargement contrôlé de `systemctl restart gvg.service`.
4. **Guide et documentation opérationnelle de sécurité (`docs/security.md`)** :
   - Documenter les règles d'exploitation, l'intégration Fail2ban avec Nginx, la politique de rotation des secrets et les audits réguliers.

## Boundaries & Constraints

**Always:**
- Utiliser HTTP 429 en cas de dépassement de quota.
- Sauvegarder automatiquement le `.env` avant toute modification par `rotate-secrets.sh`.
- Préserver les performances des utilisateurs légitimes (burst tolérant).

**Never:**
- Ne jamais bloquer indéfiniment les utilisateurs légitimes sans délai d'expiration.
- Ne jamais écraser le fichier `.env` sans sauvegarde préalable et permission `chmod 600`.

</frozen-after-approval>

## Code Map

- `deploy/nginx/gvg.conf` -- Configuration Nginx avec zones `limit_req_zone` et `limit_req` sur `/auth/login`.
- `deploy/nginx/nginx.prod.conf` -- Configuration Nginx Docker avec limitation de débit.
- `backend/app/api/v1/endpoints/auth.py` -- Protection anti-bruteforce avec suivi des tentatives et délai/blocage temporaire.
- `scripts/rotate-secrets.sh` -- Script shell de rotation sécurisée de la `JWT_SECRET_KEY` et mot de passe DB.
- `backend/tests/test_security_chantier_4.py` -- Tests automatisés de validation du rate limiting et des scripts.

## Tasks & Acceptance

**Execution:**
- [x] Configurer `limit_req_zone` et `limit_req` dans `deploy/nginx/gvg.conf` et `deploy/nginx/nginx.prod.conf`.
- [x] Ajouter la protection anti-bruteforce dans `backend/app/api/v1/endpoints/auth.py`.
- [x] Créer le script `scripts/rotate-secrets.sh` sécurisé et exécutable.
- [x] Écrire la suite de tests `backend/tests/test_security_chantier_4.py`.
- [x] Soumettre à la revue BMAD multi-agents (4 sous-agents indépendants).
- [x] Valider l'absence de régression et finaliser le commit.

