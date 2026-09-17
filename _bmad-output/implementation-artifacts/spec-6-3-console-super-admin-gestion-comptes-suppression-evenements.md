---
title: 'Story 6.3 : Console Super-Admin (Gestion des Comptes & Suppression d''Événements)'
type: 'feature'
created: '2026-09-17'
status: 'done'
route: 'dispatch'
review_loop_iteration: 1
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Les super-administrateurs de la plateforme ne disposent pas d'interface ni d'API dédiée pour gérer les comptes organisateurs (création, activation/désactivation, réinitialisation de mot de passe) ni pour supprimer en cascade les événements obsolètes ou frauduleux avec nettoyage du stockage disque.

**Approach:** Implémenter une API d'administration complète (`/api/v1/admin/users`, `DELETE /api/v1/events/{id_or_slug}`), garantir une suppression en cascade sans faille (stands, commandes, items, logs d'e-mails, fichiers d'arrière-plan), et développer les écrans frontend dédiés (`AdminUsersPage`, navigation réservée au Super-Admin, modale de confirmation renforcée avec saisie du nom exact).

## Boundaries & Constraints

**Always:**
- Restreindre l'accès à tous les endpoints d'administration des utilisateurs et à la suppression d'événements exclusivement au rôle `super_admin` (`HTTP 403 Forbidden` pour tout `event_admin`, `HTTP 401 Unauthorized` pour tout utilisateur anonyme).
- Garantir la suppression complète en cascade des enregistrements liés (tables `spots`, `orders`, `booking_items`, `email_logs`) sans déclencher d'erreur d'intégrité référentielle (`ForeignKeyViolation`).
- Nettoyer le fichier d'arrière-plan de plan de masse sur le disque (`settings.upload_dir_path / ...`) si l'événement en possédait un.
- Exiger la saisie textuelle exacte du titre de l'événement dans le dialogue de confirmation frontend avant d'autoriser la suppression.
- Assurer 100% de passage des tests automatisés et zéro régression.

**Never:**
- Ne jamais permettre à un `event_admin` de modifier d'autres utilisateurs ou d'accéder à `/admin/users`.
- Ne jamais laisser de fichiers orphelins sur le système de fichiers lors de la suppression d'un événement.
- Ne jamais permettre à un super-administrateur de désactiver ou supprimer son propre compte par mégarde via l'API sans contrôle.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Liste des utilisateurs (Super-Admin) | `GET /api/v1/admin/users` avec Bearer token Super-Admin | `200 OK` avec liste des utilisateurs (id, email, role, is_active, created_at, events_count) | N/A |
| Liste des utilisateurs (Non autorisé) | `GET /api/v1/admin/users` avec token `event_admin` ou sans token | Rejet immédiat | `403 Forbidden` ou `401 Unauthorized` |
| Création compte organisateur | `POST /api/v1/admin/users` avec `{email, password, role}` valide | `201 Created` avec nouveau compte créé et mot de passe hashé (bcrypt) | `400/422` si validation échoue |
| Création compte (Email déjà existant) | `POST /api/v1/admin/users` avec un email déjà enregistré | Rejet avec message d'erreur clair | `409 Conflict` ("Cet e-mail est déjà utilisé") |
| Modification statut/rôle utilisateur | `PATCH /api/v1/admin/users/{user_id}` avec `{is_active: false}` ou `{role: "super_admin"}` | `200 OK` avec compte mis à jour | `404 Not Found` si user introuvable |
| Réinitialisation mot de passe | `POST /api/v1/admin/users/{user_id}/reset-password` avec `{new_password}` | `200 OK` avec confirmation et mise à jour du hash | `404 Not Found` si user introuvable, `422` si mot de passe < 6 caractères |
| Suppression d'événement (Super-Admin) | `DELETE /api/v1/events/{id_or_slug}` avec Bearer Super-Admin | `204 No Content`, suppression en cascade de tous les stands, commandes, items, logs emails, et suppression de l'image de fond sur disque | N/A |
| Suppression d'événement (Event Admin) | `DELETE /api/v1/events/{id_or_slug}` avec Bearer `event_admin` | Rejet immédiat | `403 Forbidden` ("Super administrator privileges required") |
| Suppression d'événement inexistant | `DELETE /api/v1/events/unknown-slug` | Rejet | `404 Not Found` |

</frozen-after-approval>

## Code Map

- `backend/app/schemas/auth.py` -- Définition des schémas Pydantic `AdminUserResponse`, `UserCreate`, `UserUpdate`, `ResetPasswordRequest`.
- `backend/app/models/event.py` -- Ajout de la relation cascade `email_logs = relationship("EmailLog", back_populates="event", cascade="all, delete-orphan")`.
- `backend/app/models/email_log.py` -- Alignement des relations SQLAlchemy `back_populates` pour `Event` et `Order`.
- `backend/app/api/v1/endpoints/admin_users.py` -- Endpoints de gestion des utilisateurs réservés au Super-Admin (`GET`, `POST`, `PATCH`, `POST /reset-password`).
- `backend/app/api/v1/endpoints/events.py` -- Endpoint `DELETE /{id_or_slug}` protégé par `require_super_admin` avec cascade et suppression du fichier image.
- `backend/app/api/v1/router.py` -- Enregistrement du router `admin_users` sous `/admin/users`.
- `backend/tests/test_superadmin.py` -- Suite complète de tests unitaires et d'intégration validant les permissions Super-Admin, la gestion des comptes et la suppression d'événement en cascade.
- `frontend/src/types/auth.ts` -- Interfaces TypeScript pour la liste et gestion des utilisateurs administrateurs.
- `frontend/src/lib/api.ts` -- Fonctions clientes `fetchAdminUsers`, `createAdminUser`, `updateAdminUser`, `resetAdminUserPassword`, `deleteAdminEvent`.
- `frontend/src/components/AdminHeader.tsx` -- Bouton d'accès direct à la gestion des utilisateurs pour les comptes Super-Admin.
- `frontend/src/components/DeleteEventModal.tsx` -- Modale de confirmation renforcée exigeant la saisie du titre exact de l'événement.
- `frontend/src/components/EventCard.tsx` -- Intégration du bouton de suppression pour les utilisateurs Super-Admin.
- `frontend/src/pages/AdminUsersPage.tsx` -- Page de gestion des utilisateurs (tableau, création, réinitialisation de mot de passe, filtre, toggle actif/inactif).
- `frontend/src/App.tsx` -- Routage `/admin/users`, protection Super-Admin et intégration des vues.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/schemas/auth.py` -- Ajouter schémas `AdminUserResponse` (avec `events_count`), `ResetPasswordRequest`
- [x] `backend/app/models/event.py` & `backend/app/models/email_log.py` -- Valider relations cascades ORM
- [x] `backend/app/api/v1/endpoints/admin_users.py` -- Implémenter le contrôleur CRUD utilisateurs réservé au super_admin
- [x] `backend/app/api/v1/endpoints/events.py` -- Implémenter endpoint `DELETE /{id_or_slug}` avec suppression de fichier
- [x] `backend/app/api/v1/router.py` -- Monter `admin_users.router` sur `/admin/users`
- [x] `backend/tests/test_superadmin.py` -- Rédiger et exécuter la suite de tests super-admin (CRUD users + DELETE event cascade)
- [x] `frontend/src/types/auth.ts` & `frontend/src/lib/api.ts` -- Définir interfaces et appels API super-admin
- [x] `frontend/src/components/DeleteEventModal.tsx` -- Créer le composant de dialogue renforcé
- [x] `frontend/src/components/EventCard.tsx` -- Ajouter l'action de suppression conditionnée au rôle Super-Admin
- [x] `frontend/src/pages/AdminUsersPage.tsx` -- Développer la console de gestion des utilisateurs
- [x] `frontend/src/components/AdminHeader.tsx` & `frontend/src/App.tsx` -- Connecter le lien de navigation et le routeur

**Acceptance Criteria:**
- Given un Super-Admin authentifié, when il ouvre `/admin/users`, then la liste des utilisateurs s'affiche avec leurs rôles, statut et nombre d'événements, et il peut créer un organisateur ou réinitialiser son mot de passe.
- Given un non Super-Admin (ou visiteur anonyme), when il tente d'accéder aux routes `/api/v1/admin/users` ou `/admin/users`, then il reçoit un code 403 Forbidden (ou 401 Unauthorized) et le frontend redirige vers l'accueil.
- Given un Super-Admin voulant supprimer un événement, when il confirme la suppression en tapant le nom exact de l'événement, then l'événement et toutes ses dépendances (stands, commandes, items, logs, fichier plan) sont supprimés proprement.

## Implementation Notes

- Tous les endpoints `/api/v1/admin/users` sont protégés par la dépendance `require_super_admin`.
- L'endpoint `DELETE /api/v1/events/{id_or_slug}` supprime l'événement en cascade SQLAlchemy (spots, orders, booking_items, email_logs) et nettoie en toute sécurité le fichier de fond de plan téléversé sur disque après le commit en base de données.
- Protection anti-verrouillage : un super-admin ne peut ni désactiver son propre compte ni révoquer son propre rôle de super-admin.
- La modale de suppression `DeleteEventModal` exige la saisie textuelle exacte du nom de l'événement pour débloquer le bouton de confirmation irréversible.

## Review Triage Log

- **Blind Hunter / Edge Case Hunter**:
  - Sécurisation du chemin de suppression d'image de fond contre le directory traversal (`is_relative_to(settings.upload_dir_path.resolve())`). -> *Appliqué*.
  - Séquence de suppression : suppression sur disque uniquement après `db.commit()` réussi pour éviter la perte de fichier en cas d'échec SQL. -> *Appliqué*.
  - Tolérance pour les slugs au format UUID : fallback systématique par slug si la recherche par UUID échoue. -> *Appliqué*.
  - Gestion des conflits d'unicité concurrents (`IntegrityError`) dans `create_admin_user` et `update_admin_user` retournant `409 Conflict`. -> *Appliqué*.
  - Alignement ORM des relations `email_logs` sur `Order` et `EmailLog` avec `back_populates` et `cascade="all, delete-orphan"`. -> *Appliqué*.
- **Verification Gap Reviewer**:
  - Couverture des tests dans `backend/tests/test_superadmin.py` :
    - Test de promotion/rétrogradation de rôle via `PATCH /admin/users/{user_id}`. -> *Ajouté*.
    - Vérification de l'agrégation de `events_count > 0` dans `GET /admin/users`. -> *Ajouté*.
    - Vérification du code 404 lors de la suppression d'un événement inexistant et test de suppression par slug. -> *Ajouté*.
    - Vérification de connexion réussie après création de compte dans `POST /admin/users`. -> *Ajouté*.
  - Accessibilité modale : fermeture via touche `Escape` et clic sur le backdrop dans `DeleteEventModal.tsx`. -> *Appliqué*.

## Verification

**Commands:**
- `/home/sylvain/projets/gvg/gvg/.venv/bin/pytest backend/tests/test_superadmin.py -v` -- Result: 5/5 passed (100%)
- `/home/sylvain/projets/gvg/gvg/.venv/bin/pytest backend/tests/ -q` -- Result: 271/271 passed (100%)
- `npm --prefix frontend run build` -- Result: 0 errors, clean production bundle generated


