---
title: 'Story 3.2 : Workflow de Modération Optionnelle à l''Inscription'
type: 'feature'
created: '2026-09-13'
status: 'done'
baseline_commit: '97aac871ed203a39a0937cc70e57415a62b7e612'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '_bmad-output/implementation-artifacts/epic-3-context.md'
  - '_bmad-output/implementation-artifacts/spec-3-1-tableau-de-bord-admin-saisie-manuelle-hors-ligne.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Actuellement, les réservations en ligne sont immédiatement encaissées sans contrôle préalable de l'organisateur sur la conformité de l'inscription.

**Approach:** Permettre à l'organisateur d'activer la validation manuelle (`manual_approval_required`). Les paiements Stripe en ligne effectuent alors une pré-autorisation (`capture_method: manual`), la commande passe en `pending_approval` et les stands sont protégés. Sur le tableau de bord, l'organisateur peut "Accepter" (capture des fonds et confirmation) ou "Refuser" (annulation de l'autorisation sans débit et libération immédiate des stands).

## Boundaries & Constraints

**Always:**
- Avec modération active, aucun débit réel avant l'action explicite "Accepter".
- En cas de refus, annuler le PaymentIntent (`stripe.PaymentIntent.cancel`) et rétablir immédiatement les stands en statut `available`.
- Tant qu'une commande est `pending_approval`, ses stands restent protégés contre toute autre réservation.
- Les actions d'approbation et de rejet nécessitent l'authentification organisateur.
- En cas de désactivation du mode, les futures commandes repassent en capture automatique.

**Never:**
- Ne jamais stocker de coordonnées bancaires ou de CVV en base de données.
- Ne jamais laisser des stands bloqués ou réservés si une pré-autorisation est rejetée.
- Ne jamais appeler Stripe Refund sur une pré-autorisation non capturée : utiliser uniquement l'annulation (`cancel`).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Checkout avec modération | `manual_approval_required=True`, paiement CB valide | PaymentIntent `capture_method="manual"`, statut `requires_capture`. Commande `pending_approval`. Stands réservés. | 400 si validation invalide |
| Confirmation exposant | Consultation commande `pending_approval` avec token | Bandeau informatif : réservation en attente, pré-autorisation enregistrée sans débit immédiat. | 403 si token invalide |
| Approbation organisateur | Clic "Accepter" sur commande `pending_approval` | `stripe.PaymentIntent.capture`. Commande `confirmed`. Stands `reserved`. KPIs actualisés. | 400 si statut inéligible, 502 si erreur Stripe |
| Rejet organisateur | Clic "Refuser" sur commande `pending_approval` (+ motif optionnel) | `stripe.PaymentIntent.cancel`. Commande `rejected`. Stands `available`. Motif dans `admin_notes`. | 400 si statut inéligible, 502 si erreur Stripe |
| Concurrence sur action | Deux requêtes simultanées sur la même commande | Première requête exécutée, seconde traitée de façon idempotente (409 Conflict ou 400). | Message explicite retourné |
| Webhook Stripe capturable | Événement `payment_intent.amount_capturable_updated` | Commande passe en `pending_approval` de manière idempotente. | 400 si signature invalide |
| Toggle paramètre modération | Organisateur active/désactive la modération | `PATCH /api/v1/events/{id}` met à jour `manual_approval_required`. | 404 si événement introuvable |

</frozen-after-approval>

## Code Map

- `backend/app/models/event.py` -- Modèle `Event`, possède déjà le champ `manual_approval_required: bool`.
- `backend/app/schemas/event.py` -- Schémas `EventBase`, `EventUpdate`, `EventResponse` (déjà compatibles).
- `backend/app/models/order.py` -- Modèle `Order`, intègre statuts `pending_approval` et `rejected`.
- `backend/app/schemas/order.py` -- `DashboardStatsOut` enrichi avec `pending_approval_orders_count`, schéma `OrderApprovalAction`.
- `backend/app/services/stripe_service.py` -- `capture_method` conditionnel, méthodes `hold_order_for_approval`, `approve_and_capture_order`, et `reject_and_cancel_order`.
- `backend/app/api/v1/endpoints/orders.py` -- Routes admin `POST /events/{id}/orders/{order_id}/approve` et `reject`. Compteur dans `dashboard-stats`.
- `backend/app/api/v1/endpoints/webhooks.py` -- Gestion de `payment_intent.amount_capturable_updated`.
- `backend/app/api/v1/endpoints/public.py` -- Fallback résilience dans `get_public_order_by_id` pour `requires_capture`.
- `frontend/src/types/order.ts` -- Statuts étendus et mise à jour de `DashboardStats`.
- `frontend/src/lib/api.ts` -- Fonctions `approveOrder` et `rejectOrder`.
- `frontend/src/components/checkout/StripePaymentForm.tsx` -- Prise en compte de `requires_capture` pour appeler `onSuccess`.
- `frontend/src/pages/ConfirmationPage.tsx` -- Affichage adapté pour `pending_approval`.
- `frontend/src/pages/RegistrationsPage.tsx` -- Onglet "À valider", boutons d'action "Accepter" / "Refuser", et toggle modération.
- `frontend/src/components/EventForm.tsx` -- Case à cocher de modération manuelle à la création.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/services/stripe_service.py` -- Implémenter capture manuelle conditionnelle et méthodes de cycle de vie (`hold_order_for_approval`, `approve_and_capture_order`, `reject_and_cancel_order`) -- Gérer les états Stripe et transitions idempotentes.
- [x] `backend/app/api/v1/endpoints/webhooks.py` -- Gérer l'événement Stripe `payment_intent.amount_capturable_updated` -- Assurer la transition automatique vers `pending_approval`.
- [x] `backend/app/api/v1/endpoints/public.py` -- Ajouter la synchronisation directe pour `requires_capture` dans `get_public_order_by_id` -- Garantir la cohérence en cas de latence webhook.
- [x] `backend/app/api/v1/endpoints/orders.py` -- Ajouter les routes admin `approve` et `reject`, et ajouter `pending_approval_orders_count` dans `dashboard-stats` -- Permettre l'arbitrage et le suivi.
- [x] `backend/tests/test_moderation_workflow.py` -- Tests automatisés complets du cycle de modération (checkout pré-autorisé, webhook capturable, acceptation, refus, libération des stands) -- Sécuriser le comportement financier.
- [x] `frontend/src/types/order.ts` & `frontend/src/lib/api.ts` -- Déclarer les types et méthodes API de modération -- Fournir le contrat client.
- [x] `frontend/src/components/checkout/StripePaymentForm.tsx` -- Supporter `requires_capture` comme succès de pré-autorisation -- Rediriger vers la confirmation.
- [x] `frontend/src/pages/ConfirmationPage.tsx` -- Rendre la vue `pending_approval` avec message explicite -- Rassurer l'exposant sur le non-débit immédiat.
- [x] `frontend/src/pages/RegistrationsPage.tsx` -- Ajouter l'onglet "À valider", les boutons d'action avec confirmation et le switch de modération -- Fournir l'ergonomie de modération à Marc.
- [x] `frontend/src/components/EventForm.tsx` -- Ajouter la case à cocher modération au formulaire de création -- Permettre l'activation initiale.

**Acceptance Criteria:**
- Given un événement avec `manual_approval_required` activé, when un exposant valide le paiement Stripe, then le PaymentIntent est créé avec `capture_method: "manual"`, la commande est marquée `pending_approval` et les stands sont verrouillés/réservés.
- Given une commande `pending_approval`, when l'organisateur clique sur "Accepter", then Stripe capture les fonds, la commande passe en `confirmed` et les stands restent réservés.
- Given une commande `pending_approval`, when l'organisateur clique sur "Refuser", then l'autorisation Stripe est annulée sans débit, la commande passe en `rejected` et les stands redeviennent immédiatement `available`.
- Given un événement avec `manual_approval_required` désactivé, when un exposant paie en ligne, then la capture automatique immédiate reste appliquée.

## Implementation Notes

- Implemented conditional `capture_method="manual"` in Stripe PaymentIntent creation when `event.manual_approval_required` is enabled.
- Implemented `hold_order_for_approval` service to transition orders to `pending_approval` while protecting reserved stalls.
- Implemented `approve_and_capture_order` and `reject_and_cancel_order` with Stripe API integration (capture and cancel).
- Handled Stripe webhooks for `payment_intent.amount_capturable_updated`, `payment_intent.succeeded` (on pending_approval), and `payment_intent.canceled`.
- Enhanced `RegistrationsPage.tsx` with "À valider" and "Refusés" tabs, inline modal error handling, quick moderation toggle switch, and accept/reject action modals.
- Enhanced `ConfirmationPage.tsx` with dedicated status alerts and color styling for `pending_approval` and `rejected` orders.
- Added 14 comprehensive automated backend tests in `backend/tests/test_moderation_workflow.py` (all 116 backend tests pass).

## Spec Change Log

## Review Triage Log

| Verdict | Location | Summary & Evidence |
|---|---|---|
| patch | `StripePaymentForm.tsx:206-211` | 409 conflict check now includes `pending_approval` and `approval` to redirect already held orders to confirmation. |
| patch | `stripe_service.py:649-659` | Validated `stripe_payment_intent_id` presence and handled already-captured StripeError idempotently in `approve_and_capture_order`. |
| patch | `stripe_service.py:723-728` | Handled already-canceled/expired StripeError gracefully in `reject_and_cancel_order` to prevent 502 abort from blocking stall liberation. |
| patch | `webhooks.py:385` | Added handler for `payment_intent.canceled` calling `reject_and_cancel_order` to free stalls when pre-auth expires. |
| patch | `ConfirmationPage.tsx:440-465` | Styled rejected status badge red/neutral and updated price label to show no amount due. |
| patch | `RegistrationsPage.tsx:1531-1548` | Updated `event.manual_approval_required` on toggle to prevent stale parent prop overwrite. |
| patch | `orders.py:235-238` | Added automated test verifying `list_event_orders` with `status=pending_approval` filter. |
| patch | `stripe_service.py:155` | Added automated test for `payment_intent.succeeded` webhook on `pending_approval` order. |
| patch | `stripe_service.py:723-728` | Added automated test verifying 502 Bad Gateway on unexpected Stripe cancellation failure. |
| patch | `orders.py:192-280` | Added `with_for_update()` on order query in approve and reject endpoints to serialize concurrent admin actions. |
| patch | `public.py:563-585` | Restricted synchronous Stripe retrieve to `order.status == 'pending'`. |
| false | Notifications | Email notifications are out of scope for Story 3.2 (scheduled in Story 4.1). |
| patch | `RegistrationsPage.tsx` | Added 'Refusés' status filter tab to isolate rejected applications. |
| patch | `RegistrationsPage.tsx` | Displayed error messages directly inside the approval and rejection modals. |

## Design Notes

- Les stands d'une commande `pending_approval` restent au statut `reserved` avec association `BookingItem` pour empêcher tout sur-booking par d'autres exposants sur le plan public.
- En cas de refus, l'API remet les stands en `status="available"`, efface `locked_until` et `locked_by_token`, et annule l'autorisation Stripe via `stripe.PaymentIntent.cancel`.
- Le tableau de bord affiche un onglet "À valider" avec pastille de comptage pour traiter rapidement les demandes en attente.

## Verification

**Commands:**
- `.venv/bin/pytest -v backend/tests/test_moderation_workflow.py` -- expected: Tests du workflow de modération validés
- `.venv/bin/pytest -v backend/tests` -- expected: Suite complète de tests sans régression
- `PATH=/home/sylvain/projets/gvg/gvg/.tools/node/bin:$PATH npm --prefix frontend run build` -- expected: Compilation TypeScript et build Vite réussis

