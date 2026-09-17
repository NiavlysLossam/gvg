---
title: "Story 6.1 : Modèle Utilisateur, Rôles & API Auth JWT"
type: 'feature'
created: '2026-09-17'
status: 'done'
context:
  - '_bmad-output/planning-artifacts/architecture/architecture-gvg-2026-09-04/ARCHITECTURE-SPINE.md'
  - '_bmad-output/planning-artifacts/epics.md'
---

## Intent

**Problem:** Actuellement, GVG ne possède aucune couche d'authentification ni de modèle utilisateur. Toute personne connaissant l'URL des routes `/admin` peut consulter et modifier les événements sans restriction. Pour permettre le multi-organisateurs et le rôle Super-Admin, un système d'authentification robuste basé sur des tokens signés JWT et un hachage fort de mot de passe (bcrypt) est indispensable, avec rattachement de chaque événement à un propriétaire unique (`owner_id`).

**Approach:** 
1. Créer le modèle `User` (`id`, `email`, `hashed_password`, `role`, `is_active`, `created_at`, `updated_at`) avec énumération de rôles (`super_admin`, `event_admin`).
2. Mettre à jour le modèle `Event` avec `owner_id` (clé étrangère nullable vers `users.id`) et relation bidirectionnelle.
3. Écrire la migration Alembic `008_create_users_and_event_owner.py` assurant la rétrocompatibilité (les événements existants restent valides).
4. Développer le module de sécurité `app/core/security.py` : hachage et vérification de mot de passe par `bcrypt`, génération et validation de JWT HS256 (`pyjwt`) avec expiration configurable (`ACCESS_TOKEN_EXPIRE_MINUTES`).
5. Définir les dépendances FastAPI `get_current_user`, `get_current_active_user`, `require_super_admin`, et `require_event_owner(event_id)`.
6. Exposer les endpoints REST `/api/v1/auth/login`, `/api/v1/auth/me` et `/api/v1/auth/refresh`.
7. Créer le script CLI d'administration `scripts/create_superadmin.py` permettant d'initialiser de manière idempotente le premier compte Super-Admin et de lui rattacher automatiquement les événements existants sans propriétaire.
8. Valider par une suite complète de tests automatisés.

## Boundaries & Constraints

**Always:**
- Les mots de passe ne doivent JAMAIS transiter ou être stockés en clair (hachage strict avec sel aléatoire `bcrypt`).
- Les tokens JWT doivent comporter un timestamp d'expiration (`exp`) et être signés via `settings.JWT_SECRET_KEY` (avec fallback sécurisé).
- L'assignation de `owner_id` dans `Event` doit être compatible avec les bases existantes sans rupture de schéma.
- En cas d'échec d'authentification (email inconnu ou mauvais mot de passe), renvoyer une erreur générique HTTP 401 `Incorrect email or password` pour empêcher l'énumération de comptes.

**Never:**
- Ne jamais exposer `hashed_password` dans les réponses JSON de l'API (`UserResponse`).
- Ne jamais autoriser la connexion d'un utilisateur désactivé (`is_active = False`).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Connexion réussie | Email & mot de passe valides | Token JWT renvoyé (`access_token`, `token_type: bearer`, `expires_in`) + objet user | HTTP 200 OK |
| Mauvais mot de passe | Mot de passe erroné | Erreur générique d'authentification | HTTP 401 Unauthorized |
| Email inexistant | Email non trouvé en base | Même erreur générique | HTTP 401 Unauthorized |
| Compte désactivé | Utilisateur avec `is_active=False` | Connexion refusée | HTTP 400 Bad Request ("Inactive user") |
| Consultation profil `/auth/me` | Bearer token valide | Données utilisateur connectées (`id`, `email`, `role`, `is_active`) | HTTP 200 OK |
| Token expiré ou corrompu | Token altéré ou `exp` dépassé | Rejet immédiat | HTTP 401 Unauthorized ("Could not validate credentials") |
| Script CLI `create_superadmin.py` | Exécution avec email et mot de passe | Création de l'utilisateur avec rôle `super_admin` et rattachement des événements existants | Idempotent : si l'email existe, met à jour le rôle sans écraser |

## Code Map

- `backend/app/core/config.py` -- Ajout des variables de configuration JWT (`JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`).
- `backend/app/models/user.py` -- Modèle SQLAlchemy `User`.
- `backend/app/models/event.py` -- Ajout du champ `owner_id` et relation `owner`.
- `backend/app/models/__init__.py` -- Export du modèle `User`.
- `backend/alembic/versions/008_create_users_and_event_owner.py` -- Migration Alembic pour la table `users` et la colonne `events.owner_id`.
- `backend/app/core/security.py` -- Utilitaires de sécurité : `hash_password`, `verify_password`, `create_access_token`, `decode_access_token`.
- `backend/app/schemas/auth.py` -- Schémas Pydantic (`LoginRequest`, `TokenResponse`, `UserResponse`, `UserCreate`).
- `backend/app/api/deps.py` -- Dépendances d'authentification et d'autorisation (`get_current_user`, `require_super_admin`, `require_event_owner`).
- `backend/app/api/v1/endpoints/auth.py` -- Contrôleur REST `/api/v1/auth`.
- `backend/app/main.py` -- Enregistrement du routeur `auth.router`.
- `scripts/create_superadmin.py` -- Script CLI d'initialisation du Super-Admin et rattachement rétrocompatible.
- `backend/tests/test_auth.py` -- Suite de tests automatisés (hachage, tokens, login, profil, sécurité des rôles).

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/core/config.py` -- Déclarer les paramètres JWT.
- [x] `backend/app/models/user.py` & `event.py` -- Créer `User` et mettre à jour `Event`.
- [x] `backend/alembic/versions/008_create_users_and_event_owner.py` -- Créer la migration de schéma.
- [x] `backend/app/core/security.py` -- Implémenter le hachage bcrypt et l'encodage/décodage JWT.
- [x] `backend/app/schemas/auth.py` -- Créer les schémas Pydantic.
- [x] `backend/app/api/deps.py` -- Développer les dépendances d'autorisation.
- [x] `backend/app/api/v1/endpoints/auth.py` & `backend/app/main.py` -- Exposer les endpoints `/auth`.
- [x] `scripts/create_superadmin.py` -- Implémenter le script CLI d'initialisation.
- [x] `backend/tests/test_auth.py` -- Valider 100% des critères d'acceptation par des tests unitaires et d'intégration.

