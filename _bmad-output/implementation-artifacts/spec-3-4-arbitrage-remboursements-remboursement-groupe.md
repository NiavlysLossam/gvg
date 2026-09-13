---
title: "Story 3.4 : Arbitrage des Remboursements & Remboursement Groupé par le Gestionnaire"
type: 'feature'
created: '2026-09-13'
status: 'done'
baseline_commit: '004c5e5d3d67c291d960b605dfebacf5e133d833'
route: 'dispatch'
review_loop_iteration: 1
context:
  - '_bmad-output/implementation-artifacts/epic-3-context.md'
  - '_bmad-output/planning-artifacts/ux-designs/ux-gvg-2026-09-04/EXPERIENCE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Lorsqu'un exposant dépose une demande d'annulation ou en cas de force majeure nécessitant l'annulation de l'événement (ex: alerte météo rouge), l'organisateur ne dispose pas d'outils automatisés pour arbitrer les remboursements, déclencher les remboursements Stripe et libérer les stands sur le plan.

**Approach:** Fournir dans le tableau de bord organisateur une interface d'arbitrage unitaire (accepter et rembourser via l'API Stripe Refund avec libération immédiate des stands en `available`, ou refuser avec motif et maintien de l'inscription en `confirmed`) ainsi qu'un bouton d'urgence d'annulation générale de l'événement avec modale à double confirmation sécurisée déclenchant le remboursement groupé de l'ensemble des commandes et la libération intégrale des stands.

## Boundaries & Constraints

**Always:**
- Toute action d'arbitrage ou d'annulation générale requiert impérativement les droits d'administration de l'événement.
- La validation d'un remboursement unitaire ou groupé d'une commande payée par carte bancaire appelle l'API Stripe Refund (`stripe.Refund.create`).
- Lors de la validation d'un remboursement, tous les stands associés à la commande doivent être atomiquement remis en statut `available` (`locked_until=None`, `locked_by_token=None`).
- En cas de refus de la demande d'annulation par l'organisateur, la commande repasse au statut `confirmed`, les stands restent `reserved`, et le motif du refus est consigné dans `admin_notes`.
- L'annulation générale de l'événement doit comporter une protection par double confirmation explicite (ex: saisie obligatoire du mot "ANNULER" ou du titre de l'événement) pour prévenir tout déclenchement accidentel.
- En cas d'annulation générale, l'opération traite chaque commande de manière résiliente : une défaillance isolée sur une carte n'interrompt pas le remboursement des autres commandes du lot, et un rapport d'exécution consolidé est retourné.

**Never:**
- Ne jamais déclencher de remboursement Stripe sur des commandes réglées hors-ligne (espèces, chèques) : ces commandes sont marquées `refunded` ou `cancelled` avec traçabilité dans `admin_notes` sans appel à l'API bancaire.
- Ne jamais laisser des stands bloqués ou réservés lorsqu'une commande est remboursée (`refunded`).
- Ne jamais ré-exécuter un remboursement sur une commande déjà remboursée (idempotence stricte requise).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Validation remboursement Stripe | Commande `cancellation_requested` payée par CB | Appel `stripe.Refund.create`, commande passe en `refunded`, stands libérés en `available`. | 502 si échec Stripe, message explicite |
| Validation remboursement Hors-ligne | Commande `cancellation_requested` payée par chèque/espèces | Commande passe en `refunded`, stands libérés en `available`, note enregistrée sans appel Stripe. | 400 si commande invalide |
| Refus de la demande d'annulation | Clic "Refuser l'annulation" + motif obligatoire | Commande repasse en `confirmed`, stands restent `reserved`, motif archivé dans `admin_notes`. | 400 si motif vide |
| Annulation générale de l'événement | Clic "Annuler l'événement & Rembourser tous les inscrits" + confirmation texte valide | Toutes les commandes actives traitées (remboursement Stripe ou passage en remboursé/annulé), stands libérés, statut événement passe en `cancelled`. | Rapport détaillé (succès/échecs) |
| Annulation générale avec confirmation incorrecte | Saisie du texte de confirmation erronée | Action bloquée, aucune opération bancaire ou modification de base de données. | Erreur de validation formulaire |
| Webhook Stripe charge.refunded | Réception événement Stripe `charge.refunded` | Commande marquée `refunded` et stands libérés de manière idempotente. | Idempotent |
| Idempotence sur commande déjà remboursée | Tentative de remboursement sur commande déjà `refunded` | Retourne la commande sans ré-exécuter d'appel Stripe. | Statut 200/idempotent |

</frozen-after-approval>

## Code Map

- `backend/app/services/stripe_service.py` -- Fonctions `process_order_refund`, `reject_cancellation_request` et `cancel_and_refund_all_event_orders`.
- `backend/app/api/v1/endpoints/orders.py` -- Endpoints admin `POST /events/{id}/orders/{order_id}/refund`, `POST /events/{id}/orders/{order_id}/reject-cancellation` et `POST /events/{id}/cancel-and-refund-all`.
- `backend/app/api/v1/endpoints/webhooks.py` -- Prise en charge de l'événement `charge.refunded` pour synchronisation idempotente.
- `backend/app/schemas/order.py` -- Schémas `OrderRefundAction`, `OrderRejectCancellationAction` et `BulkEventCancelResponse`.
- `backend/tests/test_refund_arbitration_workflow.py` -- Tests automatisés de l'arbitrage unitaire (Stripe & Hors-ligne), du refus avec motif, de l'annulation groupée et de la libération des stands.
- `frontend/src/types/order.ts` & `frontend/src/types/event.ts` -- Définition des types pour les actions de remboursement et l'annulation groupée.
- `frontend/src/lib/api.ts` -- Fonctions clientes `refundOrder`, `rejectCancellationRequest` et `cancelAndRefundAllEventOrders`.
- `frontend/src/pages/RegistrationsPage.tsx` -- Modales d'arbitrage unitaire (Valider le remboursement / Refuser la demande), boutons d'action sur les lignes `cancellation_requested`, et modale d'annulation générale de l'événement avec double confirmation.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/services/stripe_service.py` -- Implémenter les méthodes d'arbitrage de remboursement unitaire, de refus d'annulation et de remboursement groupé avec libération atomique des stands.
- [x] `backend/app/schemas/order.py` -- Définir les schémas Pydantic pour les requêtes d'arbitrage et la réponse de remboursement groupé.
- [x] `backend/app/api/v1/endpoints/orders.py` -- Ajouter les routes admin d'arbitrage unitaire et de remboursement général de l'événement.
- [x] `backend/app/api/v1/endpoints/webhooks.py` -- Gérer l'événement webhook Stripe `charge.refunded`.
- [x] `backend/tests/test_refund_arbitration_workflow.py` -- Créer la suite de tests automatisés couvrant les remboursements unitaires, les refus, les cas hors-ligne, et le remboursement général.
- [x] `frontend/src/lib/api.ts` & `frontend/src/types/order.ts` -- Ajouter les types et appels API pour le remboursement et le refus d'annulation.
- [x] `frontend/src/pages/RegistrationsPage.tsx` -- Intégrer les boutons d'arbitrage unitaire, les modales d'action associées, et le bouton d'urgence d'annulation générale avec double confirmation.

**Acceptance Criteria:**
- Given une commande avec statut `cancellation_requested`, when l'organisateur clique sur "Valider le remboursement", then le remboursement Stripe est émis (pour CB), la commande passe en `refunded`, et les stands associés redeviennent `available` immédiatement.
- Given une commande avec statut `cancellation_requested`, when l'organisateur clique sur "Refuser" et saisit un motif, then la commande repasse en `confirmed`, les stands restent `reserved`, et le motif est archivé dans les notes admin.
- Given un événement avec plusieurs commandes confirmées, when l'organisateur lance "Annuler l'événement & Rembourser tous les inscrits" et valide la double confirmation, then toutes les commandes sont traitées (remboursement CB ou annulation hors-ligne), tous les stands sont libérés et l'événement passe en statut `cancelled`.

## Implementation Notes

- Arbitrage de remboursement unitaire (`POST /api/v1/events/{id}/orders/{order_id}/refund`) :
  - Valide les statuts admissibles (`cancellation_requested` ou `confirmed` pour geste commercial).
  - Pour les commandes Stripe : émet `stripe.Refund.create` avec clé d'idempotence unique basée sur `order.id` et horodatage de demande.
  - Pour les commandes hors-ligne (chèques, espèces) : consigne la validation sans appel API bancaire.
  - Libère atomiquement tous les stands réservés vers `available` (`locked_until=None`, `locked_by_token=None`).
- Refus de la demande d'annulation (`POST /api/v1/events/{id}/orders/{order_id}/reject-cancellation`) :
  - Motif obligatoire consigné dans `admin_notes`.
  - Réinitialise la commande en `confirmed` et conserve les stands en `reserved`.
  - Idempotent : renvoie 200 en cas de rappel sur une commande déjà refusée.
- Annulation d'urgence et remboursement groupé (`POST /api/v1/events/{id}/cancel-and-refund-all`) :
  - Double confirmation sécurisée : vérifie que le texte correspond insensiblement à `CONFIRMER`, `ANNULER`, ou au titre exact de l'événement.
  - Traitement résilient de chaque commande : un échec de carte bancaire n'interrompt pas le reste du lot (`db.rollback()` par transaction isolée).
  - Passe le statut de l'événement à `cancelled` et libère tous les stands `reserved`/`locked` tout en préservant intacts les stands `blocked` (arbres, poteaux physiques).
  - Verrouille toute nouvelle tentative de réservation publique ou manuelle (`HTTP 409 Conflict`).
- Webhook `charge.refunded` :
  - Gère la synchronisation idempotente Stripe. Ignore les remboursements partiels pour éviter la libération prématurée de stands.
- Frontend `RegistrationsPage.tsx` :
  - Boutons d'arbitrage vert "Valider remboursement" et rouge "Refuser" sur l'onglet dédié et la table.
  - Modale d'annulation générale avec saisie de confirmation et compteurs détaillés en fin d'exécution.
  - Badges visuels violets `Remboursé` et gris barré `Annulé`.
  - Verrouillage du bouton de saisie manuelle si l'événement est annulé.

## Review Triage Log

- Triaged & applied findings from 3 parallel reviewers (Blind Hunter `f5f716ce`, Edge Case Hunter `1df500fc`, Verification Gap `6e42e970`):
  1. Idempotency guard on `reject_cancellation_request` hardened against unrequested orders.
  2. Safeguard against partial refunds in Stripe webhook: only full refunds trigger stall release.
  3. Selective spot release in bulk cancellation: preserve physically blocked spots (`status == "blocked"`).
  4. Per-order `db.rollback()` in bulk loop to avoid `PendingRollbackError` cascades.
  5. HTTP 409 Conflict guards on cancelled events for both public visitor locks and manual admin bookings.
  6. Case-insensitive double confirmation matching (`CONFIRMER`, `ANNULER`, event title).

## Design Notes

- Double confirmation pour l'annulation générale : L'organisateur doit saisir le titre exact de l'événement ou le mot clé "CONFIRMER" pour déverrouiller le bouton de confirmation rouge.
- Interface d'arbitrage sur `RegistrationsPage` :
  - Sur l'onglet "Annulations demandées", chaque ligne affiche directement les boutons "Valider le remboursement" (vert/émeraude) et "Refuser" (rouge/gris).
  - Un badge visuel clair indique le motif de la demande formulé par l'exposant.


