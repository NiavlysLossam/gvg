# Story 6.2 : Écrans de Connexion, Sécurisation Frontend & Scope Admin

## Statut : Complété (`done`)

### 1. Objectifs & Périmètre Réalisé
- **Backend - Sécurisation systématique de tous les endpoints d'administration** :
  - `backend/app/api/v1/endpoints/events.py` : création, consultation, mise à jour, suppression, upload de fond de plan protégés par `get_current_user` et `check_event_ownership`.
  - `backend/app/api/v1/endpoints/spots.py` : liste, création, modification, suppression, batch create et batch renumber vérifiant la propriété de l'événement.
  - `backend/app/api/v1/endpoints/orders.py` : tableau de bord, liste des commandes/inscriptions, réservation manuelle, modération/arbitrage (approbation, rejet, remboursement, rejet d'annulation), annulation générale et exportations (PDF/Excel) sécurisés.
  - `backend/app/api/v1/endpoints/broadcast.py` : prévisualisation et envoi de diffusions d'emails d'annonces protégés.
  - `backend/app/api/v1/endpoints/reminders.py` : statut et déclenchement manuel des rappels J-7/J-2 protégés.
  - Support de l'authentification directe pour les exports fichiers (`attestation.pdf`, `checkin.pdf`, `checkin.xlsx`) via paramètre de requête `?token=...` en plus du header standard `Authorization: Bearer`.
- **Backend - Multi-tenant Scoping & Isolation** :
  - Sur `POST /api/v1/events`, le champ `owner_id` est automatiquement renseigné avec `current_user.id`.
  - Dans `GET /api/v1/events`, un `event_admin` ne voit que ses propres événements (`filter(Event.owner_id == current_user.id)`).
  - Un `event_admin` se voit refuser l'accès (`403 Forbidden`) s'il tente d'accéder ou de modifier un événement, ses stands, ses commandes ou ses rappels s'il n'en est pas le propriétaire.
  - Un `super_admin` dispose d'une visibilité globale : il voit tous les événements et peut gérer n'importe quel événement.
- **Frontend - Authentification & Expérience Utilisateur** :
  - `frontend/src/types/auth.ts` : interfaces complètes `UserRole`, `User`, `LoginResponse`, `LoginCredentials`.
  - `frontend/src/lib/api.ts` : implémentation de `getAuthToken`, `setAuthToken`, `clearAuthToken`, `authFetch`, `loginApi`, `fetchCurrentUser`, et mise à jour de tous les endpoints d'administration pour utiliser `authFetch`.
  - Déconnexion automatique sur code HTTP 401 via l'événement personnalisé `gvg:auth:expired`.
  - `frontend/src/contexts/AuthContext.tsx` : contexte et hook `useAuth` avec persistance de session dans `localStorage` et validation au montage.
  - `frontend/src/components/AdminHeader.tsx` : affichage de l'adresse e-mail de l'administrateur connecté, pill de rôle visuel (`Super-Admin` ou `Organisateur`) et bouton de déconnexion.
  - `frontend/src/pages/LoginPage.tsx` : formulaire moderne et accessible de connexion avec gestion des erreurs 401/403 et redirection post-connexion.
  - `frontend/src/App.tsx` : routage `/login`, protection des routes d'administration et intégration du composant `AdminHeader`.

### 2. Validation & Tests
- **Tests unitaires et de scoping backend** :
  - `backend/tests/test_auth_scoping.py` : 5 tests spécifiques validant :
    1. Rejet 401 sur requêtes non authentifiées.
    2. Auto-assignation de `owner_id` lors de la création d'événement.
    3. Isolation stricte des listes d'événements entre organisateurs distincts.
    4. Code 403 Forbidden sur toute tentative d'accès/modification d'un événement tiers (GET/PATCH event, spots, orders, broadcast, reminders).
    5. Accès global et gestion accordés au super-administrateur.
  - `backend/tests/test_auth.py` : 10 tests unitaires d'authentification validés (100%).
  - `backend/tests/test_events_api.py` : 11 tests d'API événements validés (100%).
- **Build Frontend** :
  - `npm run build` (`tsc -b && vite build`) compilé avec succès (0 erreurs TypeScript, bundle Vite généré dans `dist/`).

