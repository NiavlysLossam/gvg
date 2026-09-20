---
title: 'Story 8.2 - Fiche Détaillée d Inscription Modifiable & Notes Internes'
type: 'feature'
created: '2026-09-19'
status: 'done'
baseline_commit: dd3934043dc57156922fbec652af0fa6201c5297
route: 'dispatch'
review_loop_iteration: 1
context:
  - _bmad-output/implementation-artifacts/epic-8-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Les organisateurs manquent d'une vue unifiée sur chaque inscription pour consulter l'intégralité du dossier exposant, corriger les coquilles de saisie (e-mail erroné empêchant la réception des convocations, numéro de téléphone mal saisi) et consigner des annotations d'équipe confidentielles.

**Approach:** Implémenter un panneau latéral coulissant (slide-over drawer) interactif s'ouvrant au clic sur une ligne de réservation, permettant de consulter la fiche détaillée (état civil, stands, règlement, modération, logs de communication), de modifier les coordonnées de contact avec validation RFC, d'enregistrer des notes administratives internes privées, et de réexpédier immédiatement l'attestation PDF par e-mail à l'adresse mise à jour.

## Boundaries & Constraints

**Always:**
- Valider le format de l'e-mail avec une regex RFC stricte et vérifier la validité du numéro de téléphone (8 à 15 chiffres).
- Conserver le champ `admin_notes` strictement privé (jamais exposé sur les routes publiques exposants).
- Permettre la réexpédition de l'attestation PDF uniquement pour les commandes au statut `confirmed` disposant d'un e-mail valide.
- Enregistrer chaque envoi d'attestation dans la table `email_logs` (type `attestation` ou `confirmation`) pour traçabilité complète.
- Préserver la sélection multiple et les filtres actifs lors de l'ouverture ou la fermeture de la fiche détaillée.

**Never:**
- Ne jamais écraser ou altérer les montants financiers (`total_price_cents`) ou les stands réservés depuis cette fiche d'inscription.
- Ne jamais stocker de fichiers PDF temporaires sur disque (génération WeasyPrint en mémoire).
- Ne jamais autoriser la modification d'inscriptions appartenant à un autre organisateur (contrôle strict des droits d'accès `check_event_ownership`).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Consultation de la fiche | Clic sur une ligne ou bouton "Fiche" dans le tableau | Ouverture du slide-over avec données complètes de l'inscription | Fallback propre si certaines données optionnelles sont absentes |
| Mise à jour de l'e-mail et du téléphone | Saisie d'un nouvel e-mail valide et téléphone | PATCH 200, mise à jour en base et synchronisation immédiate de la ligne du tableau | Rejet 422 si format d'e-mail invalide ou téléphone hors limites |
| Saisie de notes internes | Saisie de texte libre dans `admin_notes` | Persistance en base de données, affichage dans le badge notes du tableau | Longueur maximale sécurisée (5000 caractères) |
| Réexpédition de l'attestation PDF | Clic sur "Renvoyer l'attestation par e-mail" pour commande `confirmed` | Envoi d'un e-mail avec PDF en pièce jointe + lien direct, ajout dans `email_logs` | Rejet 400 si commande non confirmée ou absence d'e-mail |
| Inscription sans e-mail (guichet) | Commande hors-ligne sans e-mail | Bouton de réexpédition désactivé avec message invitant à renseigner un e-mail | Tooltip explicatif "Renseignez une adresse e-mail pour réexpédier" |

</frozen-after-approval>

## Code Map

- `backend/app/models/order.py` -- Modèle `Order` : contient déjà `admin_notes: Text` et les coordonnées exposant.
- `backend/app/schemas/order.py` -- Définition du schéma d'entrée `AdminOrderUpdate` (validation e-mail RFC, phone, admin_notes, noms, adresse).
- `backend/app/api/v1/endpoints/orders.py` -- Ajout des endpoints `PATCH /{id_or_slug}/orders/{order_id}` et `POST /{id_or_slug}/orders/{order_id}/resend-attestation`.
- `backend/app/services/email_service.py` -- Support des pièces jointes PDF dans `send_raw_email` et nouvelle fonction `send_attestation_email`.
- `backend/app/templates/emails/attestation_resend.html` & `.txt` -- Gabarits Jinja2 pour l'e-mail de réexpédition d'attestation officielle.
- `backend/tests/test_admin_orders_api.py` -- Tests automatisés de mise à jour des coordonnées, des notes internes, et de la réexpédition d'attestation.
- `frontend/src/types/order.ts` -- Définition de l'interface `AdminOrderUpdateInput`.
- `frontend/src/lib/api.ts` -- Fonctions clientes `updateAdminOrder`, `resendOrderAttestationEmail`, et `fetchOrderEmails`.
- `frontend/src/pages/registrations/OrderDetailsDrawer.tsx` -- Composant slide-over moderne présentant la fiche d'inscription complète avec formulaires d'édition, bloc-notes interne et réexpédition d'attestation.
- `frontend/src/pages/registrations/RegistrationsTab.tsx` -- Intégration du déclencheur au clic de ligne, gestion de l'état `selectedOrderForDrawer` et rafraîchissement réactif.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/schemas/order.py` -- Définir `AdminOrderUpdate` avec validation RFC email, phone normalisé et admin_notes.
- [x] `backend/app/services/email_service.py` -- Étendre `send_raw_email` avec support optionnel des pièces jointes (`attachments`) et implémenter `send_attestation_email`.
- [x] `backend/app/templates/emails/attestation_resend.html` & `attestation_resend.txt` -- Créer les gabarits d'envoi d'attestation officielle.
- [x] `backend/app/api/v1/endpoints/orders.py` -- Implémenter les routes `PATCH /api/v1/events/{id_or_slug}/orders/{order_id}` et `POST /api/v1/events/{id_or_slug}/orders/{order_id}/resend-attestation`.
- [x] `backend/tests/test_admin_orders_api.py` -- Ajouter la suite de tests automatisés pour la modification de commande et le renvoi d'attestation.
- [x] `frontend/src/types/order.ts` & `frontend/src/lib/api.ts` -- Ajouter les interfaces et fonctions d'API pour la mise à jour et la réexpédition.
- [x] `frontend/src/pages/registrations/OrderDetailsDrawer.tsx` -- Développer le panneau latéral coulissant avec onglets/sections (Coordonnées modifiables, Stands, Paiement & Modération, Bloc-notes interne, Historique des e-mails, Actions PDF).
- [x] `frontend/src/pages/registrations/RegistrationsTab.tsx` -- Connecter le clic de ligne au slide-over, mettre à jour l'ordre localement lors de l'enregistrement.

**Acceptance Criteria:**
- Given une réservation existante, when l'organisateur clique sur la ligne du tableau des inscriptions, then le panneau coulissant `OrderDetailsDrawer` s'affiche avec la totalité des informations de l'exposant sans recharger la page.
- Given le formulaire de coordonnées dans le slide-over, when l'organisateur saisit une nouvelle adresse e-mail ou un téléphone et enregistre, then les modifications sont validées (format RFC), persistées en base via `PATCH`, et répercutées immédiatement sur la ligne du tableau.
- Given le bloc de notes internes dans le slide-over, when l'organisateur saisit une note d'équipe et clique sur "Enregistrer la note", then `admin_notes` est sauvegardé en base de données et demeure invisible sur les interfaces exposants.
- Given une commande confirmée avec adresse e-mail, when l'organisateur clique sur "Renvoyer l'attestation par e-mail", then l'attestation légale PDF est compilée à la volée, transmise en pièce jointe d'un e-mail de confirmation, et une trace est consignée dans `EmailLog`.

## Implementation Notes

- Implémenté `AdminOrderUpdate` et `ResendAttestationResponse` dans `backend/app/schemas/order.py` avec validation stricte RFC de l'e-mail, normalisation et vérification du téléphone (8 à 15 chiffres), et contrôle de la taille des notes administratives (max 5000 caractères).
- Support des pièces jointes MIME `multipart/mixed` avec `multipart/alternative` pour le contenu HTML/texte et `MIMEApplication` pour les fichiers joints dans `send_raw_email` (`backend/app/services/email_service.py`).
- Implémenté `send_attestation_email` dans `email_service.py` générant l'attestation PDF WeasyPrint en mémoire sans stockage disque, envoyant l'e-mail avec pièce jointe et consignant l'audit dans `EmailLog` (type `attestation`).
- Créé les gabarits Jinja2 `attestation_resend.html` et `attestation_resend.txt` dans `backend/app/templates/emails/`.
- Ajouté les endpoints `PATCH /api/v1/events/{id_or_slug}/orders/{order_id}` et `POST /api/v1/events/{id_or_slug}/orders/{order_id}/resend-attestation` dans `backend/app/api/v1/endpoints/orders.py` avec vérification stricte des permissions organisateur.
- Couverture de test complète dans `backend/tests/test_admin_orders_api.py` (21 tests passants, 100% succès) couvrant modification coordonnées, validation 422, confidentialité des notes administratives, immutabilité des montants et stands, réexpédition d'attestation PDF, cas d'erreurs 400 et sécurité 403.
- Ajouté les types et fonctions client d'API dans `frontend/src/types/order.ts` et `frontend/src/lib/api.ts` (`updateAdminOrder`, `resendOrderAttestationEmail`, `fetchOrderEmails`).
- Créé le composant slide-over `frontend/src/pages/registrations/OrderDetailsDrawer.tsx` avec édition réactive des coordonnées, bloc-notes interne confidentiel, historique audité des e-mails, téléchargement et réexpédition d'attestation avec états de chargement et retours utilisateur.
- Intégré le déclencheur de clic de ligne et bouton d'action dans `frontend/src/pages/registrations/RegistrationsTab.tsx` et propagation réactive d'état dans `frontend/src/pages/RegistrationsPage.tsx` préservant filtres et sélections multiples.

## Spec Change Log

<!-- Append-only. Populated during review loops. -->

## Review Triage Log

| Finding | Verdict | Evidence / Disposition |
|---|---|---|
| Null payload on non-nullable fields (first_name, last_name, phone) | medium | Raised 500 IntegrityError on DB commit. Fixed with explicit null checks raising 422 in Pydantic validators. |
| Drawer state overwrite and instant success dismissal on order update | high | useEffect([order]) wiped in-flight inputs and success banners. Fixed by keying effect on order?.id and preserving state. |
| Resend attestation with unsaved modified email input | medium | Prevented sending to old address when email field is changed without saving. Added explicit validation prompt. |
| Out-of-order race condition in loadEmailLogs | medium | Rapid order switching could overwrite audit log with wrong exhibitor. Fixed with currentOrderIdRef guard. |
| MIMEApplication subtype ignored in send_raw_email | medium | Attachment MIME type defaulted to octet-stream. Fixed by setting _subtype from attachment MIME type. |
| Silent failure in send_attestation_email if PDF generation fails | medium | Swallow of PDF compilation error sent email claiming PDF was attached. Fixed by recording failed EmailLog and aborting. |
| Checkbox column cell click opening drawer in RegistrationsTab | medium | Clicking td padding triggered row onClick. Fixed by adding checkbox-cell guard and stopPropagation. |
| Non-existent Tailwind classes (backdrop-blur-xs, shadow-2xs, etc.) | low | Replaced with standard Tailwind v3 classes (backdrop-blur-sm, shadow-sm, transition-transform). |
| Dialog accessibility & body scroll locking | low | Added overflow: hidden body scroll lock while drawer is open. |
| Missing test assertions for PDF attachment bytes & MIME headers | medium | Added spy assertion in test_resend_attestation_confirmed_order_success and new MIME test in test_email_service.py. |
| Missing boundary 422 and 404 tests | medium | Added unit tests covering null fields, phone sanitization, 5000-char note limits, and 404 nonexistent IDs. |
| Double-toggle on row checkbox click in RegistrationsTab | high | Event bubbling from input to td cancelled selection out. Fixed with e.stopPropagation() and e.target check. |
| Re-opening drawer for same order skipped form & log reload | high | prevOrderIdRef.current was not reset on close. Fixed by resetting ref on drawer close and depending on isOpen. |
| Over-restrictive phone regex rejecting standard formats | medium | Regex rejected numbers with parentheses. Updated to support parentheses and up to 30 characters. |
| N+1 query regression on relationship expiration after PATCH | medium | db.refresh(order) expired items. Fixed by re-querying order with eager selectinload. |
| Missing unverified test for PDF compilation error path | medium | Added test_resend_attestation_pdf_compilation_failure_logs_error asserting failed EmailLog and no email sent. |
| Missing spot_labels assertion on PATCH response | medium | Added assert updated["spot_labels"] == ["VG-01"] in test_update_admin_order_contact_success. |
| Missing last_name null rejection check in tests | low | Added explicit null verification for last_name in test_update_admin_order_null_mandatory_fields_422. |
| Missing linear meters and stand length in drawer view | low | Displayed stand linear meters and total linear meters badge in stands card. |
| Missing honor declaration acceptance metadata in drawer and endpoint check | low | Added honor declaration verification in backend resend endpoint and timestamp badge in UI. |
| Uncleaned timer timeouts on drawer unmount | low | Added timersRef and cleanup on unmount. |
| Unsaved name edits before attestation resend | low | Extended guard to verify first_name and last_name in addition to email. |

## Design Notes

- **Ergonomie Slide-Over** : Utilisation d'un panneau latéral `fixed inset-y-0 right-0 max-w-xl w-full bg-white shadow-2xl z-50` avec backdrop semi-transparent et fermeture sur Échap / clic extérieur pour préserver le contexte visuel du tableau.
- **Édition Réactive** : Mise à jour direct du state parent `orders` dans `RegistrationsTab` lors de la réussite du `PATCH` pour éviter un rechargement complet perturbant le défilement.
- **Pièces jointes MIME** : `send_raw_email` configure une structure MIME `multipart/mixed` avec une sous-partie `multipart/alternative` pour le corps HTML/texte et des sous-parties `MIMEApplication` pour les fichiers joints.

## Verification

**Commands:**
- `.venv/bin/pytest backend/tests/test_admin_orders_api.py -v` -- expected: 100% passing tests for order update and attestation resend.
- `export PATH="/home/sylvain/projets/gvg/gvg/.tools/node/bin:$PATH" && npm run build --prefix frontend` -- expected: 0 TypeScript and Vite errors.

