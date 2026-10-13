---
title: 'Chantier Sécurité 3 - Nginx, En-têtes HTTP de sécurité, Uploads sécurisés & Cloisonnement CORS (P1)'
type: 'security'
created: '2026-10-13'
status: 'done'
baseline_commit: b83ea73
route: 'dispatch'
review_loop_iteration: 1
context:
  - _bmad-output/implementation-artifacts/epic-8-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:**
L'audit de sécurité multi-agents a relevé plusieurs carences au niveau des couches réseau, reverse proxy Nginx, en-têtes HTTP de protection du navigateur, exposition des fichiers téléversés (`/uploads`), et politique CORS :
1. **SEC-P1-05 (Absence d'en-têtes HTTP de sécurité et `server_tokens` dans Nginx)** :
   Dans `deploy/nginx/gvg.conf` et `deploy/nginx/nginx.prod.conf`, aucun en-tête de sécurité moderne n'est configuré (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, `Content-Security-Policy`, `Strict-Transport-Security`). De plus, `server_tokens off;` n'est pas activé, exposant la version précise de Nginx aux scanners d'attaquants.
2. **SEC-P1-06 (Exposition et exécution potentielle de scripts dans `/uploads`)** :
   Dans Nginx, `/uploads` est actuellement routé directement vers FastAPI sans en-têtes restrictifs. Si un fichier était servi avec un MIME ambigu ou en direct, le navigateur pourrait tenter d'exécuter du JavaScript (MIME sniffing / XSS stocké). Côté Nginx et FastAPI (`SecureStaticFiles`), les fichiers téléversés doivent être servis avec `X-Content-Type-Options: nosniff` et un `Content-Security-Policy: default-src 'none'; sandbox` strict.
3. **SEC-P1-07 (Validation stricte de la politique CORS en production)** :
   Dans `backend/app/core/config.py`, `CORS_ORIGINS` n'empêche pas explicitement la combinaison non sécurisée du wildcard `*` avec `allow_credentials=True`. Un validateur Pydantic doit interdire le wildcard en environnement de production lorsque des cookies ou des identifiants d'authentification sont transmis.
4. **SEC-P1-08 (Middleware de sécurité HTTP global dans FastAPI)** :
   Pour garantir la protection des réponses API même lors des accès directs ou via des proxies alternatifs, FastAPI doit injecter les en-têtes de défense en profondeur (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`).

**Approach:**
1. **Durcissement des configurations Nginx (`gvg.conf` & `nginx.prod.conf`)** :
   - Ajouter `server_tokens off;`.
   - Ajouter les en-têtes de sécurité recommandés au niveau du serveur :
     - `add_header X-Frame-Options "DENY" always;`
     - `add_header X-Content-Type-Options "nosniff" always;`
     - `add_header Referrer-Policy "strict-origin-when-cross-origin" always;`
     - `add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;`
   - Définir un bloc `location ^~ /uploads/` dédié avec protection et re-déclaration explicite des en-têtes parents, sandbox CSP `default-src 'none'; sandbox`, et interdiction d'exécution de scripts (`location ~* \.(php|pl|py|cgi|sh|bash|exe|bat|cmd|ps1|vbs|jar|html|htm|shtml)$ { return 403; }`).
2. **Sous-classe `SecureStaticFiles` dans FastAPI (`main.py`)** :
   Créer une classe `SecureStaticFiles(StaticFiles)` qui ajoute systématiquement `X-Content-Type-Options: nosniff` et `Content-Security-Policy: default-src 'none'; sandbox` à chaque fichier servi sous `/uploads`.
3. **Middleware de sécurité global & gestionnaire d'exception dans FastAPI (`main.py`)** :
   Ajouter un middleware HTTP léger injectant les en-têtes de sécurité de base (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`) sur toutes les requêtes HTTP, doublé de gestionnaires d'exceptions 422 et 500 préservant ces en-têtes.
4. **Validation CORS Pydantic dans `config.py`** :
   Refuser formellement `*` dans `CORS_ORIGINS` en production, et nettoyer les espaces résiduels.

## Boundaries & Constraints

**Always:**
- Masquer la signature de version Nginx (`server_tokens off;`).
- Appliquer `X-Content-Type-Options: nosniff` sur tous les uploads et réponses API.
- Servir les fichiers `/uploads` avec une sandbox CSP (`default-src 'none'; sandbox`).
- Protéger les pages contre le clickjacking (`X-Frame-Options: DENY` ou `SAMEORIGIN`).

**Never:**
- Ne jamais permettre l'exécution de scripts ou de HTML actif depuis `/uploads`.
- Ne jamais autoriser le wildcard `*` avec des identifiants d'authentification en production.

</frozen-after-approval>

## Code Map

- `deploy/nginx/gvg.conf` -- Configuration Nginx pour déploiement Ubuntu avec en-têtes de sécurité et bloc `/uploads`.
- `deploy/nginx/nginx.prod.conf` -- Configuration Nginx Docker avec en-têtes de sécurité et bloc `/uploads`.
- `backend/app/main.py` -- Middleware de sécurité HTTP global et montage `SecureStaticFiles` pour `/uploads`.
- `backend/app/core/config.py` -- Validation stricte des origines CORS en production.
- `backend/tests/test_security_chantier_3.py` -- Suite de tests automatisés validant les en-têtes HTTP, la sandbox des uploads et les règles CORS.

## Tasks & Acceptance

**Execution:**
- [x] Mettre à jour `deploy/nginx/gvg.conf` avec en-têtes de sécurité et bloc `/uploads`.
- [x] Mettre à jour `deploy/nginx/nginx.prod.conf` avec en-têtes de sécurité et bloc `/uploads`.
- [x] Ajouter `SecureStaticFiles` et le middleware de sécurité HTTP dans `backend/app/main.py`.
- [x] Ajouter la validation stricte de `CORS_ORIGINS` dans `backend/app/core/config.py`.
- [x] Créer `backend/tests/test_security_chantier_3.py` et valider l'ensemble des scénarios.
- [x] Lancer la revue de code BMAD (`bmad-code-review`) avec 4 sous-agents indépendants.
- [x] Traiter les retours de revue et valider les tests de non-régression.

