---
title: "Story 3.1: Tableau de Bord Administrateur & Saisie Manuelle Hors-Ligne"
type: "feature"
created: "2026-09-13"
status: "done"
baseline_commit: "edb35c70dd988f828e4a9f39443947bfa24d0ee1"
route: "dispatch"
review_loop_iteration: 0
context:
  - "_bmad-output/implementation-artifacts/epic-3-context.md"
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Les organisateurs (Marc) manquent d'une vue d'ensemble centralisée des réservations pour piloter le remplissage de leur événement et ne peuvent pas enregistrer les règlements hors-ligne (chèques ou espèces déposés en mairie), ce qui crée un risque de double attribution de stand.

**Approach:** Développer un tableau de bord administrateur des inscriptions (`/admin/e/:id/inscriptions`) affichant la jauge de remplissage, le chiffre d'affaires et la liste filtrable des inscrits, ainsi qu'un formulaire de réservation manuelle permettant d'affecter instantanément des stands libres au statut `reserved` avec tag « Hors-ligne ».

## Boundaries & Constraints

**Always:**
- Les réservations manuelles hors-ligne passent immédiatement le ou les stands au statut `reserved` dans une transaction SQL atomique.
- Les moyens de paiement hors-ligne acceptés sont `check` (chèque), `cash` (espèces) et `other` (autre / gratuité).
- Le tableau de bord calcule en temps réel le taux de remplissage (% de stands réservés sur le total) et le CA global ventilé (en ligne Stripe vs hors-ligne).
- Le tableau d'inscriptions permet une recherche instantanée (nom, prénom, numéro de stand, email) et un filtrage par statut (`all`, `confirmed`, `pending`, `offline`).
- Les stands réservés hors-ligne portent l'indicateur visuel `Hors-ligne` tant sur l'interface organisateur que dans la consultation publique.
- Conserver l'invariant de sécurité : aucun mot de passe requis pour les exposants et aucun stockage de fichier CNI.

**Never:**
- Ne jamais permettre l'enregistrement d'une réservation manuelle sur un stand déjà réservé ou bloqué (rejet HTTP 409 Conflict).
- Ne jamais appeler l'API Stripe lors d'une saisie manuelle hors-ligne.
- Ne pas introduire de suppression d'inscriptions dans cette story (réservé à l'arbitrage des remboursements en Story 3.4).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Consultation KPIs & Inscriptions | `GET /api/v1/events/{id}/orders` | Liste paginée/filtrable des commandes + stats de remplissage (% remplissage, CA Stripe, CA hors-ligne) | 404 si événement inexistant |
| Recherche & Filtre | `?status=offline&search=Robert` | Seules les commandes correspondantes avec stands associés sont retournées | Retourne liste vide `[]` si aucun match |
| Réservation manuelle valide | `POST /api/v1/events/{id}/orders/manual` avec stands libres, nom, mode `check` | Commande créée statut `confirmed`, stands passés à `reserved`, items liés créés | 201 Created |
| Conflit stand déjà réservé | `POST /api/v1/events/{id}/orders/manual` avec stand déjà `reserved` | Rejet atomique, aucun stand modifié, aucune commande créée | 409 Conflict avec message explicite |
| Saisie sans email | Stand réservé en mairie avec téléphone seul | Commande créée avec succès, email facultatif en mode hors-ligne | 201 Created |

</frozen-after-approval>

## Code Map

- `backend/app/models/order.py` -- Entités `Order` et `BookingItem` : ajouter champs `offline_payment_reference` et `admin_notes`, rendre `email` et adresse optionnels si commande hors-ligne.
- `backend/alembic/versions/005_add_offline_order_fields.py` -- Migration Alembic pour ajouter les colonnes et adapter la nullabilité.
- `backend/app/schemas/order.py` -- Schémas `OfflineOrderCreate`, `EventDashboardStats`, `AdminOrderListResponse`, `AdminOrderOut`.
- `backend/app/schemas/public.py` -- Exposer `is_offline: bool` ou `payment_method` dans `PublicSpotProperties` pour le tag "Hors-ligne".
- `backend/app/api/v1/endpoints/orders.py` -- Nouveaux contrôleurs admin : `GET /events/{id}/orders`, `GET /events/{id}/dashboard-stats`, `POST /events/{id}/orders/manual`.
- `backend/app/api/v1/router.py` -- Enregistrement du routeur `orders.router` sous `/events`.
- `backend/tests/test_admin_orders_api.py` -- Tests unitaires et d'intégration couvrant la matrice I/O.
- `frontend/src/types/order.ts` -- Interfaces TypeScript `AdminOrder`, `DashboardStats`, `OfflineBookingPayload`.
- `frontend/src/lib/api.ts` -- Fonctions API `fetchEventOrders`, `fetchEventDashboardStats`, `createManualBooking`.
- `frontend/src/pages/RegistrationsPage.tsx` -- Page du tableau de bord des inscriptions (KPIs, jauge, table, filtres).
- `frontend/src/components/ManualBookingModal.tsx` -- Modale de saisie manuelle (sélection stand, identité, moyen de paiement).
- `frontend/src/components/EventCard.tsx` -- Ajout du bouton d'accès rapide « Inscriptions » vers le tableau de bord.
- `frontend/src/components/SpotEditor.tsx` -- Option "Ajouter une réservation manuelle" au clic sur un stand disponible.
- `frontend/src/App.tsx` -- Routage de l'onglet `inscriptions` avec événement sélectionné.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/models/order.py` -- Ajouter `offline_payment_reference` et `admin_notes` aux modèles, adapter nullabilité -- Préparer persistance hors-ligne
- [x] `backend/alembic/versions/005_add_offline_order_fields.py` -- Créer la migration Alembic 005 et l'appliquer en base -- Schéma SQL PostgreSQL
- [x] `backend/app/schemas/order.py` -- Définir `OfflineOrderCreate`, `EventDashboardStats`, `AdminOrderListResponse` -- Typage Pydantic v2
- [x] `backend/app/schemas/public.py` -- Ajouter `is_offline` et `payment_method` à `PublicSpotProperties` -- Rendu visuel public
- [x] `backend/app/api/v1/endpoints/orders.py` -- Implémenter les endpoints admin listing, stats et réservation manuelle -- Logique métier REST
- [x] `backend/app/api/v1/router.py` -- Brancher le routeur orders dans l'API v1 -- Intégration FastAPI
- [x] `backend/tests/test_admin_orders_api.py` -- Écrire les tests de couverture automatisés -- Validation backend & non-régression
- [x] `frontend/src/types/order.ts` & `frontend/src/lib/api.ts` -- Ajouter types et requêtes API pour le dashboard admin -- Couche client typée
- [x] `frontend/src/components/ManualBookingModal.tsx` -- Créer la modale ergonomique de saisie de règlement hors-ligne -- Interface de saisie
- [x] `frontend/src/pages/RegistrationsPage.tsx` -- Créer le tableau de bord avec jauge de remplissage, cartes KPIs et table triable -- Vue pilotage
- [x] `frontend/src/components/EventCard.tsx` & `frontend/src/App.tsx` -- Connecter le bouton « Inscriptions » et l'onglet admin -- Navigation applicative
- [x] `frontend/src/components/SpotEditor.tsx` -- Intégrer l'action réservation manuelle au clic sur un stand libre -- Ergonomie cartographique

**Acceptance Criteria:**
- Given Marc connecté sur son espace administrateur, when il consulte `/admin` et clique sur « Inscriptions », then il visualise la jauge de remplissage (ex: 84/120 stands, 70%), le CA cumulé (Stripe + Hors-ligne), et la liste triable des inscrits avec filtres.
- Given un stand libre sur le plan ou dans la liste, when Marc enregistre une réservation avec Nom="Robert", Téléphone="0600000000" et Moyen="Chèque", then le stand passe immédiatement à `reserved` avec le tag "Hors-ligne" et apparaît dans le tableau de bord.
- Given une tentative de réservation manuelle sur un stand déjà réservé, when la requête est soumise, then le serveur la rejette avec un code HTTP 409 et le plan reste intègre.

## Implementation Notes

## Spec Change Log

## Review Triage Log

| Verdict | Finding / Scope | Evidence / Disposition |
|---------|-----------------|------------------------|
| patch | Pagination SQL row slicing with joinedload (`orders.py`) | Replaced joinedload with selectinload on Order.items and BookingItem.spot. |
| patch | Blocked spots omitted from available calculation (`orders.py`) | Subtracted blocked_spots in available_spots formula. |
| patch | Full name search ("Prénom Nom") (`orders.py`) | Added concat(first_name, ' ', last_name) search query. |
| patch | Internal admin_notes exposed publicly (`schemas/order.py`) | Removed admin_notes from OrderOut, retained on AdminOrderOut. |
| patch | Public spot GeoJSON exposed payment_method (`schemas/public.py`) | Removed payment_method from public spot schemas, kept only is_offline. |
| patch | get_spot/update_spot lacked is_offline attribute (`spots.py`) | Resolved order_payment_method in scalar subquery. |
| patch | Missing tests for pagination, custom_price_cents=0, blocked spots | Added test cases in test_admin_orders_api.py (all 102 backend tests pass). |
| patch | React 422 error detail array crash & comma parsing (`ManualBookingModal.tsx`) | Formatted detail array, sanitized comma to dot, reset form on open. |
| patch | Missing sortable table headers & search debouncing (`RegistrationsPage.tsx`) | Added column click-to-sort, 300ms debounced search, fixed py-0.2 typo. |
| false | Missing authentication on admin endpoints | Out of scope for Story 3.1: GVG v1 MVP currently operates in local/single-organizer mode without auth. |

## Design Notes

- **Jauge de remplissage :** Composant épuré avec barre bicolore (vert pour réservé, ambre pour verrouillé temporairement, gris clair pour disponible) avec ratio numérique et pourcentage.
- **Badges de statut d'inscription :**
  - `stripe` : Badge vert émeraude "En ligne (Stripe)"
  - `check` : Badge bleu ardoise "Hors-ligne (Chèque)"
  - `cash` : Badge ambre "Hors-ligne (Espèces)"
  - `other` : Badge violet "Hors-ligne (Autre)"

## Verification

**Commands:**
- `/home/sylvain/projets/gvg/gvg/.venv/bin/pytest backend/tests/test_admin_orders_api.py -v` -- expected: Tous les tests d'API admin au vert
- `/home/sylvain/projets/gvg/gvg/.venv/bin/pytest -v` -- expected: Suite complète de 90+ tests backend au vert
- `PATH=/home/sylvain/projets/gvg/gvg/.tools/node/bin:$PATH npm run build --prefix frontend` -- expected: Build frontend TypeScript sans erreur
