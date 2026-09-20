---
title: 'Story 8.3 - Verrouillage Strict des Prix des Stands Réservés'
type: 'feature'
created: '2026-09-20'
status: 'done'
baseline_commit: bd42d82f755cd156754dda8af72581b2bf2c8d2d
route: 'dispatch'
review_loop_iteration: 1
context:
  - _bmad-output/implementation-artifacts/epic-8-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Actuellement, un organisateur peut modifier le tarif ou le métrage linéaire d'un stand dans l'éditeur de plan même lorsque celui-ci a déjà été réservé ou payé par un exposant, ce qui engendre des incohérences comptables graves entre les paiements perçus et le plan d'implantation.

**Approach:** Verrouiller strictement toute tentative de modification de tarif (`price_cents` ou `linear_meters` recalculant le tarif) pour tout stand ayant le statut `reserved` ou associé à une commande active, tant au niveau du formulaire de propriétés dans l'éditeur cartographique (champs grisés et badge d'information) que sur les routes backend (`PATCH /{id_or_slug}/spots/{spot_id}` et mise à jour groupée), avec déverrouillage automatique si la réservation est ultérieurement annulée ou remboursée et le stand remis en disponibilité.

## Boundaries & Constraints

**Always:**
- Rejeter avec un code HTTP 400 Bad Request toute requête API tentant de modifier `price_cents` ou `linear_meters` sur un stand réservé (`spot.status == 'reserved'` ou commande active au statut `confirmed`, `pending`, `pending_approval`, `cancellation_requested`).
- Afficher un badge visible "Prix verrouillé (stand déjà réservé)" et désactiver les champs de prix et de métrage dans `SpotPropertyDrawer.tsx` dès qu'un stand réservé est sélectionné.
- Autoriser la modification du libellé (`label`) ou de la géométrie polygonale (`geometry`) d'un stand réservé tant que son prix et son métrage ne sont pas altérés.
- Redevenir immédiatement éditable dès lors que toutes les réservations associées ont été annulées ou remboursées et que le stand a retrouvé le statut `available`.
- Retourner des messages d'erreur clairs en français pour l'utilisateur.

**Never:**
- Ne jamais modifier le tarif d'un stand réservé lors d'une mise à jour unitaire ou groupée.
- Ne jamais bloquer les stands disponibles, verrouillés temporairement dans un panier expiré, ou dont la réservation a été annulée/remboursée.
- Ne jamais altérer silencieusement les montants des commandes ou des factures passées.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Sélection d'un stand réservé dans l'éditeur | Clic sur un stand avec `status == 'reserved'` | Ouverture de `SpotPropertyDrawer` avec champs tarif/métrage grisés et badge "Prix verrouillé (stand déjà réservé)" | N/A |
| Tentative de modification unitaire de prix | `PATCH /spots/{id}` avec `price_cents != spot.price_cents` sur stand réservé | Rejet HTTP 400 Bad Request avec message explicite | Message : "Impossible de modifier le prix d'un stand déjà réservé ou associé à une commande active." |
| Tentative de modification unitaire de métrage | `PATCH /spots/{id}` avec `linear_meters != spot.linear_meters` sur stand réservé | Rejet HTTP 400 Bad Request avec message explicite | Message : "Impossible de modifier les dimensions ou le prix d'un stand déjà réservé ou associé à une commande active." |
| Envoi du prix identique sans modification | `PATCH /spots/{id}` avec `price_cents == spot.price_cents` ou changement de `label`/`geometry` | Succès HTTP 200, mise à jour effectuée sans blocage | N/A |
| Modification groupée (`batch update`) | `PATCH /spots/batch` avec un lot dont un stand réservé change de prix | Transaction annulée, rejet HTTP 400 avec identification du stand en conflit | HTTP 400 identifiant le libellé du stand réservé |
| Remise en disponibilité après annulation/remboursement | Commande annulée ou remboursée, stand redevenu `available` | Le stand redevient librement modifiable en tarif et métrage | N/A |

</frozen-after-approval>

## Code Map

- `backend/app/models/spot.py` -- Modèle `Spot` : statuts `available`, `locked`, `reserved`, `blocked`, relation `booking_items`.
- `backend/app/models/order.py` -- Modèle `Order` : statut de commande (`confirmed`, `pending`, `pending_approval`, `cancellation_requested`, `refunded`, `cancelled`, `rejected`).
- `backend/app/schemas/spot.py` -- Schémas `SpotUpdate`, `SpotBatchUpdateItem`, `SpotBatchUpdate`, `SpotBatchUpdateResponse`.
- `backend/app/api/v1/endpoints/spots.py` -- Contrôleur `update_spot` et nouvel endpoint `batch_update_spots` (`PATCH /{id_or_slug}/spots/batch`) avec détection d'état réservé / commande active.
- `backend/tests/test_spots_api.py` -- Tests automatisés de verrouillage strict de prix : rejet 400 unitaire et groupé, préservation des modifications non tarifaires (label, geometry), et réouverture de l'édition après annulation d'une commande.
- `frontend/src/types/spot.ts` -- Interfaces TypeScript pour la mise à jour unitaire et groupée des stands.
- `frontend/src/lib/api.ts` -- Fonctions clientes `updateSpot` et `batchUpdateSpots`.
- `frontend/src/components/SpotPropertyDrawer.tsx` -- Panneau d'édition cartographique : détection de l'état réservé, verrouillage des contrôles de tarif et de métrage, affichage du badge `Lock` avec mention "Prix verrouillé (stand déjà réservé)", et gestion de la soumission sécurisée.
- `frontend/src/components/SpotEditor.tsx` -- Vue principale de l'éditeur cartographique Leaflet / Geoman.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/schemas/spot.py` -- Ajouter `SpotBatchUpdateItem`, `SpotBatchUpdate` et `SpotBatchUpdateResponse`.
- [x] `backend/app/api/v1/endpoints/spots.py` -- Intégrer la validation anti-modification de prix sur `update_spot` et implémenter `PATCH /{id_or_slug}/spots/batch` avec vérification de commande active.
- [x] `backend/tests/test_spots_api.py` -- Écrire les tests d'intégration validant le verrouillage HTTP 400 sur commande confirmée/pending, l'autorisation si prix inchangé, le rejet en lot et l'éditabilité après remboursement.
- [x] `frontend/src/components/SpotPropertyDrawer.tsx` -- Griser le tarif et le métrage lorsque `spot.properties.status === 'reserved'`, afficher le badge de verrouillage et sécuriser `handleSubmit`.
- [x] `frontend/src/lib/api.ts` & `frontend/src/types/spot.ts` -- Exporter les types et fonctions de batch update.

**Acceptance Criteria:**
- Given un stand ayant le statut `reserved` ou associé à une commande active, when l'organisateur sélectionne ce stand dans l'éditeur de plan, then le champ de prix dans le panneau de propriétés est grisé / désactivé avec le badge informatif "Prix verrouillé (stand déjà réservé)".
- Given une requête API tentant de modifier le prix ou le métrage d'un stand réservé (`PATCH /api/v1/events/{id}/spots/{spot_id}` ou `PATCH /api/v1/events/{id}/spots/batch`), when le backend détecte une commande active sur ce stand, then la requête est rejetée avec un code HTTP 400 Bad Request et un message explicite.
- Given un stand réservé, when l'organisateur met à jour son libellé ou sa géométrie sans altérer son prix ni son métrage, then la mise à jour est acceptée avec un code HTTP 200.
- Given une réservation ultérieurement annulée ou remboursée et le stand remis en statut `available`, when l'organisateur ou l'API tente de modifier le prix du stand, then la modification est acceptée et le prix est mis à jour.

## Implementation Notes

## Spec Change Log

<!-- Append-only. Populated during review loops. -->

## Review Triage Log

- **Verification Gap (Weak assertion in test_batch_update_spots_success)**: Dispositon: `patch`. Ajouté vérifications explicites de `linear_meters` et `price_cents` sur les features retournées par le batch update.
- **Verification Gap (Missing active order rejection test in batch_update_spots)**: Disposition: `patch`. Ajouté `test_batch_update_spots_active_order_conflict_rejected` vérifiant le rejet 400 et le rollback atomique lors d'une mise à jour de prix sur un stand rattaché à une commande en statut `pending_approval`.
- **Verification Gap (Missing linear_meters rejection test on locked spots in batch_update_spots)**: Disposition: `patch`. Ajouté `test_batch_update_spots_reserved_linear_meters_rejected` vérifiant le rejet 400 lors d'une tentative de mise à jour des dimensions en batch.
- **Verification Gap (Missing active order deletion rejection test in delete_spot)**: Disposition: `patch`. Ajouté `test_delete_spot_active_order_rejected` testant l'interdiction de suppression HTTP 400 d'un stand rattaché à une commande active.
- **Blind Hunter (Linear meters float comparison tolerance)**: Disposition: `patch`. Remplacé les comparaisons strictes `!=` par `abs(a - b) > 0.001` dans `update_spot` et `batch_update_spots` pour éviter les faux rejets 400 sur imprécision binaire IEEE-754.
- **Blind Hunter (HTTP 404 for spots from different events in batch update)**: Disposition: `patch`. `batch_update_spots` renvoie désormais HTTP 404 au lieu de 400 si un ID d'emplacement n'appartient pas à l'événement.
- **Blind Hunter (SpotBatchUpdateItem price & price_cents synchronization)**: Disposition: `patch`. Validateur Pydantic mis à jour pour recalculer/synchroniser `price_cents` dès que `price` en euros est spécifié.
- **Blind Hunter (SpotPropertyDrawer locked status check)**: Disposition: `patch`. `isReserved` inclut désormais `status === 'locked'` en plus de `'reserved'`.
- **Edge Case Hunter**: Aucun finding rapporté (`[]`).

## Design Notes

- **Détection d'une réservation active** : Un stand est considéré comme verrouillé si son `status == "reserved"` OU s'il existe une ligne `BookingItem` rattachée à une commande active (statut dans `["confirmed", "pending", "pending_approval", "cancellation_requested"]`).
- **Tolérance des requêtes idempotentes** : Si une requête `PATCH` envoie une valeur de `price_cents` identique à la valeur courante, elle n'est pas considérée comme une tentative de modification et ne déclenche pas de rejet 400.
- **Ergonomie UI** : Dans `SpotPropertyDrawer.tsx`, le badge jaune/ambre avec icône cadenas (`Lock`) informe immédiatement l'organisateur de l'impossibilité de modifier le prix, tout en lui laissant la liberté de corriger le libellé si nécessaire.

## Verification

**Commands:**
- `.venv/bin/pytest backend/tests/test_spots_api.py -v` -- expected: 100% passing tests for spot price locking.
- `export PATH="/home/sylvain/projets/gvg/gvg/.tools/node/bin:$PATH" && npm run build --prefix frontend` -- expected: 0 TypeScript and Vite errors.

