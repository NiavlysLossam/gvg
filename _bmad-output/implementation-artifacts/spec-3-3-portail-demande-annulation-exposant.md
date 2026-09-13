---
title: "Story 3.3 : Portail de Demande d'Annulation pour l'Exposant"
type: 'feature'
created: '2026-09-13'
status: 'done'
baseline_commit: 'c9aad4fca45c108fcb85edbf1af386ff2f6b9b45'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '_bmad-output/implementation-artifacts/epic-3-context.md'
  - '_bmad-output/planning-artifacts/ux-designs/ux-gvg-2026-09-04/EXPERIENCE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Actuellement, un exposant empêché ne dispose d'aucun moyen numérique autonome pour signaler son désistement ou demander un remboursement sans devoir contacter directement l'organisateur par téléphone ou voie postale.

**Approach:** Offrir un portail public d'annulation sans mot de passe accessible via le magic token HMAC de la commande (`/e/:slug/annulation/:orderId?token=...`). L'exposant sélectionne son motif d'annulation, ajoute un commentaire explicatif optionnel, et soumet sa demande. La commande passe à l'état `cancellation_requested` avec enregistrement de l'horodatage et des motifs, informant l'exposant que son dossier est transmis à l'organisateur pour arbitrage.

## Boundaries & Constraints

**Always:**
- L'accès au formulaire d'annulation et la soumission requièrent impérativement le token d'accès HMAC valide (`access_token`) vérifié en temps constant (`secrets.compare_digest`).
- Seules les commandes aux statuts `confirmed` (ou `pending_approval`) sont éligibles à une demande d'annulation.
- Lors de la soumission de la demande d'annulation, les emplacements réservés restent attribués à l'exposant (`reserved`) jusqu'à l'arbitrage formel de l'organisateur en Story 3.4.
- La page de confirmation (`/e/:slug/confirmation/:orderId`) doit comporter un lien direct vers le portail d'annulation pour les commandes confirmées.
- Si une commande est déjà en statut `cancellation_requested`, afficher un écran informatif clair indiquant que la demande est en cours d'examen par l'organisateur.

**Never:**
- Ne jamais exiger de mot de passe ou de création de compte utilisateur pour soumettre une annulation.
- Ne jamais libérer automatiquement les stands (`available`) lors de la simple demande d'annulation (seul l'arbitrage organisateur en Story 3.4 valide la libération des stands).
- Ne jamais autoriser de demande d'annulation sur une commande déjà annulée (`cancelled`), rejetée (`rejected`) ou remboursée (`refunded`).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Consultation portail éligible | Commande `confirmed`, token valide | Formulaire d'annulation affiché : rappel des stands réservés, montant, sélecteur de motif, champ commentaire, bouton soumettre. | N/A |
| Demande avec token invalide | Token erroné ou manquant | Refus d'accès avec message d'erreur sécurisé. | 401 si manquant, 403 si invalide |
| Soumission formulaire valide | Motif sélectionné (ex: "medical") + commentaire | Statut passe en `cancellation_requested`, `cancellation_reason`, `cancellation_comment` et `cancellation_requested_at` sauvegardés. | 400 si motif vide |
| Commande déjà en attente | Commande déjà `cancellation_requested` | Vue récapitulative : message rassurant informant que la demande a déjà été transmise et est en cours d'examen. | Idempotent (affiche l'état en cours) |
| Commande inéligible | Statut `cancelled`, `rejected` ou `refunded` | Message d'information indiquant que la commande n'est plus modifiable. | 409 Conflict sur POST |
| Commande introuvable | `order_id` inexistant ou mauvais slug | Message d'erreur 404 standard. | 404 Not Found |
| Accès depuis Confirmation | Clic sur "Demander une annulation" | Navigation fluide vers `/e/:slug/annulation/:orderId?token=...`. | Conserve le token en URL et session |

</frozen-after-approval>

## Code Map

- `backend/app/models/order.py` -- Modèle `Order`, ajout des colonnes `cancellation_reason`, `cancellation_comment` et `cancellation_requested_at`.
- `backend/alembic/versions/006_add_cancellation_fields.py` -- Migration Alembic pour ajouter les colonnes d'annulation à la table `orders`.
- `backend/app/schemas/order.py` -- Schéma d'entrée `CancellationRequestIn`, mise à jour de `OrderOut` et `AdminOrderOut` avec les champs d'annulation.
- `backend/app/api/v1/endpoints/public.py` -- Endpoint public `POST /events/{slug}/orders/{order_id}/cancellation-request` sécurisé par `access_token`.
- `backend/app/api/v1/endpoints/orders.py` -- Prise en compte du statut `cancellation_requested` dans la liste admin et les compteurs stats.
- `backend/tests/test_cancellation_workflow.py` -- Tests automatisés couvrant les cas nominaux et d'erreur de la demande d'annulation.
- `frontend/src/types/order.ts` -- Extension des types `OrderOut`, `AdminOrder`, `CancellationRequestIn` et union de statuts.
- `frontend/src/lib/api.ts` -- Fonction cliente `submitCancellationRequest`.
- `frontend/src/pages/CancellationPage.tsx` -- Page dédiée du portail d'annulation exposant avec sélection du motif et confirmation visuelle.
- `frontend/src/pages/ConfirmationPage.tsx` -- Remplacement du bandeau temporaire par le lien actif d'annulation et affichage du statut `cancellation_requested`.
- `frontend/src/App.tsx` -- Détection et routage des URLs `/e/:slug/annulation/:orderId` et hash `#/...`.
- `frontend/src/pages/RegistrationsPage.tsx` -- Ajout du filtre et badge "Annulation demandée" dans la gestion des inscriptions.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/models/order.py` & `backend/alembic/versions/006_add_cancellation_fields.py` -- Ajouter les champs d'annulation au modèle `Order` et générer la migration Alembic.
- [x] `backend/app/schemas/order.py` -- Créer `CancellationRequestIn` et exposer les champs dans `OrderOut` et `AdminOrderOut`.
- [x] `backend/app/api/v1/endpoints/public.py` -- Implémenter l'endpoint `POST /events/{slug}/orders/{order_id}/cancellation-request` avec vérification du token et validation des statuts.
- [x] `backend/tests/test_cancellation_workflow.py` -- Rédiger les tests d'API pour la consultation et la soumission d'une demande d'annulation.
- [x] `frontend/src/types/order.ts` & `frontend/src/lib/api.ts` -- Déclarer les types TypeScript et la fonction d'appel API `submitCancellationRequest`.
- [x] `frontend/src/pages/CancellationPage.tsx` -- Développer la page du portail exposant avec gestion des états (formulaire, succès, déjà soumis, erreurs).
- [x] `frontend/src/pages/ConfirmationPage.tsx` & `frontend/src/App.tsx` -- Intégrer le lien d'accès à l'annulation, le rendu du statut sur la confirmation et le routage applicatif.
- [x] `frontend/src/pages/RegistrationsPage.tsx` -- Afficher le badge et le statut "Annulation demandée" sur le tableau de bord admin.

**Acceptance Criteria:**
- Given une commande en statut `confirmed`, when l'exposant ouvre `/e/:slug/annulation/:orderId?token=...`, then le récapitulatif de sa commande et le formulaire d'annulation s'affichent.
- Given le formulaire d'annulation affiché, when l'exposant choisit un motif, renseigne un commentaire et clique sur "Confirmer ma demande d'annulation", then la commande passe en `cancellation_requested` et un message confirme la prise en compte pour arbitrage.
- Given une commande déjà en statut `cancellation_requested`, when l'exposant réouvre la page d'annulation ou la confirmation, then un bandeau d'attente informe que la demande est en cours d'examen par l'organisateur.
- Given une tentative d'annulation avec un token absent ou incorrect, then l'API renvoie 401 ou 403 et l'interface affiche une erreur sécurisée sans dévoiler d'information.

## Implementation Notes

- Modèle et migration : Ajout de `cancellation_reason` (VARCHAR 100), `cancellation_comment` (TEXT) et `cancellation_requested_at` (TIMESTAMP WITH TIME ZONE) dans `orders`. Migration Alembic `006_add_cancellation_fields.py` validée en upgrade et downgrade.
- Endpoint public : `POST /api/v1/public/events/{slug}/orders/{order_id}/cancellation-request`.
  - Sécurité HMAC : Validation du token d'accès via `secrets.compare_digest`.
  - Statuts éligibles : `confirmed` et `pending_approval`.
  - Idempotence : Si `cancellation_requested`, renvoie la commande sans ré-écrire.
  - Invariant critique : Les stands restent à l'état `reserved`, aucun stand n'est remis en `available` lors de la demande.
- Frontend :
  - `CancellationPage.tsx` : Portail autonome d'annulation exposant avec sélection de motifs prédéfinis (`medical`, `personal`, `weather`, `other`), contrôle de saisie pour `other`, gestion des erreurs token/statut et affichage du récapitulatif en attente d'arbitrage.
  - `ConfirmationPage.tsx` : Remplacement du placeholder par un lien actif "Demander une annulation" / "Suivre ma demande" et badge ambre pour `cancellation_requested`.
  - `App.tsx` : Ajout de la route `/e/:slug/annulation/:orderId` et prise en charge du hash navigation.
  - `RegistrationsPage.tsx` : Ajout du filtre par statut `cancellation_requested` avec compteur dédié, badge d'état ambre et affichage des motifs d'annulation dans la colonne Notes & Ref.
- Retours de revue appliqués :
  - Retrait de `admin_notes` de `OrderOut` pour empêcher toute fuite de notes internes.
  - Inclusion de `cancellation_requested` dans les KPIs de chiffre d'affaires et commandes confirmées tant que le remboursement n'a pas été validé.
  - Validation stricte Pydantic sur `CancellationRequestIn` des motifs autorisés et commentaire obligatoire pour 'other'.
  - Support de recherche admin dans `list_event_orders` sur `cancellation_reason` et `cancellation_comment`.
  - Nettoyage des classes Tailwind CSS incompatibles v4 (`focus:outline-none`, `shadow-sm`, `backdrop-blur-sm`).
  - Extraction robuste du token depuis `window.location.search` et `window.location.hash`.
  - Affichage générique "L'organisateur" et gestion des états terminaux sur `ConfirmationPage`.
  - Export des constantes partagées `CANCELLATION_REASONS` et fonction `getCancellationReasonLabel`.
  - Bouton de copie directe du lien d'annulation dans le presse-papier.
- Tests : 16 tests automatisés complets dans `backend/tests/test_cancellation_workflow.py` validant tous les cas nominaux et d'erreur. 132/132 tests backend au vert. Build de production frontend TypeScript & Vite validé.

## Spec Change Log

## Review Triage Log

| Finding | Severity | Verdict & Evidence | Route |
|---|---|---|---|
| Information disclosure of `admin_notes` in `OrderOut` | Medium | `medium` - Les notes d'administration étaient exposées sur le modèle public `OrderOut`. Retiré du modèle et du mapping. | patch |
| Chiffre d'affaires et commandes sous-comptabilisés pendant l'annulation | Medium | `medium` - `compute_dashboard_stats` excluait prématurément les commandes `cancellation_requested` avant arbitrage. Corrigé. | patch |
| Validation stricte des motifs d'annulation et commentaire obligatoire pour 'other' | Medium | `medium` - Empêche la saisie de motifs arbitraires et garantit un commentaire explicatif pour 'other'. | patch |
| Recherche administrateur omettant les motifs/commentaires d'annulation | Medium | `medium` - Ajout de `cancellation_reason` et `cancellation_comment` dans le filtre `ilike` admin. | patch |
| Classes incompatibles Tailwind CSS v4 | Medium | `medium` - Classes `focus:outline-hidden`, `shadow-xs`, etc. remplacées par la syntaxe standard Tailwind v3. | patch |
| Extraction du token dans le routage par hash | Medium | `medium` - Les tokens passés dans `#/e/:slug/annulation/:id?token=...` sont maintenant extraits avec succès. | patch |
| Rendu résilient des erreurs de validation Pydantic 422 | Medium | `medium` - Évite un crash React potentiel en cas de retour d'erreur sous forme de liste d'objets. | patch |
| Support du slash terminal dans l'URL d'annulation | Low | `low` - Ajout de `\/?` dans la regex de `App.tsx`. | patch |
| Rendu et personnalisation sur la page de confirmation | Low | `low` - Remplacement du prénom en dur "Marc" par "L'organisateur" et cartes héro dédiées pour `cancelled`/`refunded`. | patch |
| Constantes partagées pour les motifs d'annulation | Low | `low` - Export de `CANCELLATION_REASONS` dans `order.ts` pour uniformiser l'affichage UI. | patch |
| Action de copie de lien sur le portail d'annulation | Low | `low` - Bouton de copie du lien dans le presse-papier avec feedback visuel. | patch |

## Design Notes

- Motifs standards prédéfinis :
  1. `medical` : Empêchement médical / Santé
  2. `personal` : Imprévu personnel ou familial
  3. `weather` : Météo / Transport / Logistique
  4. `other` : Autre motif (avec précision obligatoire dans le champ commentaire)
- Palette visuelle cohérente : bandeau ambre/orange rassurant pour le statut `cancellation_requested` (ex: `bg-amber-50 border-amber-200 text-amber-900`) pour marquer l'attente d'arbitrage sans inquiéter l'exposant.
