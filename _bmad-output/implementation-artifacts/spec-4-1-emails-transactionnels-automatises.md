---
title: "Story 4.1 : E-mails Transactionnels Automatisés (Confirmation, Reçus & Suivi d'Arbitrage)"
type: 'feature'
created: '2026-09-13'
status: 'done'
baseline_commit: '938b48a07cba55fffa1249b6b90beec8b1d9bf12'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '_bmad-output/implementation-artifacts/epic-4-context.md'
  - '_bmad-output/planning-artifacts/architecture/architecture-gvg-2026-09-04/ARCHITECTURE-SPINE.md'
  - '_bmad-output/planning-artifacts/ux-designs/ux-gvg-2026-09-04/EXPERIENCE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Actuellement, lorsqu'un exposant réserve et paie sa place en ligne (ou est inscrit manuellement hors-ligne avec email), il ne reçoit aucune confirmation écrite par email. De même, lorsqu'une demande d'annulation est arbitrée (validée ou refusée) ou qu'un événement est annulé d'urgence, aucune notification automatique n'est transmise aux exposants concernés, les privant d'un justificatif officiel, de leurs horaires et de leurs liens d'accès direct.

**Approach:** Développer un service d'envoi d'emails transactionnels asynchrones basé sur FastAPI `BackgroundTasks`, des gabarits HTML soignés (Jinja2) avec version texte alternatif, un modèle de journalisation en base (`email_logs`), et le connecter automatiquement aux événements du cycle de vie des commandes : confirmation de commande, décision de modération, arbitrage d'annulation/remboursement, et annulation générale d'événement.

## Boundaries & Constraints

**Always:**
- Les envois d'emails doivent s'exécuter en arrière-plan via `BackgroundTasks` (FastAPI) pour ne jamais bloquer la réponse HTTP du client (règle AD-7).
- Tout email transactionnel doit comporter une version HTML mise en page et responsive, ainsi qu'une version texte brut (`multipart/alternative`).
- Tout email envoyé à un exposant doit contenir ses liens d'accès direct sécurisés par le token d'accès HMAC sans jamais requérir de mot de passe (`/e/:slug/confirmation/:orderId?token=...` et `/e/:slug/annulation/:orderId?token=...`).
- Si aucun serveur SMTP n'est configuré (ex: environnement local de développement sans `SMTP_HOST`), le service doit basculer automatiquement en mode simulation (`simulated`), journaliser le contenu de l'email et ne jamais faire échouer la transaction métier.
- Chaque tentative d'envoi (réussie, échouée ou simulée) est enregistrée dans la table `email_logs` pour audit et traçabilité.

**Never:**
- Ne jamais bloquer la création d'une commande, la validation d'un paiement ou un arbitrage si l'envoi d'email échoue (résilience et tolérance aux pannes réseau).
- Ne jamais tenter d'envoyer un email si l'exposant n'a pas renseigné d'adresse email (cas possible en saisie hors-ligne).
- Ne jamais stocker de mots de passe ou d'identifiants sensibles dans les templates d'email.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Confirmation commande Stripe | Paiement Stripe confirmé (`payment_intent.succeeded` ou sync) | Envoi asynchrone email confirmation avec stands, métrage, montant, horaires, lien d'accès. | Log dans `email_logs`, pas de crash API |
| Confirmation commande hors-ligne | Saisie manuelle avec email renseigné | Envoi asynchrone email confirmation mentionnant le mode de règlement (Espèces / Chèque). | Si email absent, envoi ignoré proprement |
| Commande soumise à modération | Commande créée avec `manual_approval_required=True` | Envoi d'un email accusant réception de la demande "En attente de validation organisateur". | Journalisé dans `email_logs` |
| Décision de modération : Acceptée | Clic organisateur "Accepter" | Envoi email confirmation finale + capture des fonds + lien accès. | Journalisé dans `email_logs` |
| Décision de modération : Refusée | Clic organisateur "Refuser" + motif | Envoi email de refus expliquant l'annulation de la pré-autorisation bancaire + motif. | Journalisé dans `email_logs` |
| Arbitrage annulation : Validée | Clic organisateur "Valider remboursement" | Envoi email confirmant le remboursement (Stripe ou hors-ligne) et la libération des stands. | Journalisé dans `email_logs` |
| Arbitrage annulation : Refusée | Clic organisateur "Refuser" + motif obligatoire | Envoi email notifiant le maintien de l'inscription avec explication du motif. | Journalisé dans `email_logs` |
| Annulation générale de l'événement | Exécution de `cancel-and-refund-all` | Envoi asynchrone à tous les exposants confirmés de la notification d'annulation d'urgence. | Traitement en lot non bloquant |
| Serveur SMTP injoignable ou absent | SMTP non configuré ou timeout réseau | Statut `simulated` ou `failed` consigné dans `email_logs`, transaction métier complétée avec succès. | Exception interceptée et tracée |

</frozen-after-approval>

## Code Map

- `backend/app/core/config.py` -- Ajout des paramètres de configuration SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_TLS`, `SMTP_SSL`, `EMAILS_FROM_EMAIL`, `EMAILS_FROM_NAME`, `FRONTEND_BASE_URL`).
- `backend/app/models/email_log.py` -- Modèle SQLAlchemy `EmailLog` (`id`, `event_id`, `order_id`, `recipient`, `email_type`, `subject`, `status`, `error_message`, `created_at`).
- `backend/alembic/versions/007_create_email_logs.py` -- Migration Alembic pour la création de la table `email_logs`.
- `backend/app/templates/emails/` -- Gabarits HTML et texte Jinja2 :
  - `base.html` / `base.txt`
  - `order_confirmation.html` / `order_confirmation.txt`
  - `moderation_decision.html` / `moderation_decision.txt`
  - `cancellation_arbitration.html` / `cancellation_arbitration.txt`
  - `event_cancellation.html` / `event_cancellation.txt`
- `backend/app/services/email_service.py` -- Service centralisé de rendu de templates et d'envoi d'emails via SMTP (ou mode simulation) avec journalisation en base.
- `backend/app/api/v1/endpoints/orders.py`, `public.py`, `webhooks.py` -- Branchement des appels `email_service` via `BackgroundTasks`.
- `backend/app/schemas/email.py` -- Schémas Pydantic pour la consultation des logs d'emails.
- `backend/tests/test_email_service.py` -- Tests unitaires et d'intégration couvrant le rendu des templates, l'envoi asynchrone, le mode simulation, la tolérance aux pannes et la journalisation en base.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/core/config.py` & `backend/pyproject.toml` -- Ajouter Jinja2 et les variables de configuration SMTP et URL frontend.
- [x] `backend/app/models/email_log.py` & migration Alembic `007_create_email_logs` -- Créer le modèle et la migration de la table `email_logs`.
- [x] `backend/app/templates/emails/` -- Créer les templates HTML et TXT Jinja2 pour les 4 typologies d'emails transactionnels.
- [x] `backend/app/services/email_service.py` -- Implémenter le service d'envoi (SMTP + simulation) et de journalisation.
- [x] `backend/app/api/v1/endpoints/` (`public.py`, `orders.py`, `webhooks.py`) -- Connecter les déclencheurs d'envoi d'email via `BackgroundTasks`.
- [x] `backend/tests/test_email_service.py` -- Écrire la suite de tests automatisés validant tous les scénarios et cas limites.

**Acceptance Criteria:**
- Given une commande validée par carte bancaire ou saisie au guichet avec adresse email, when la transaction est confirmée, then un email HTML et texte de confirmation est généré avec récapitulatif des stands, horaires d'installation/public, adresse et liens d'accès sécurisés, et tracé dans `email_logs`.
- Given une commande en attente de modération, when l'organisateur valide ou refuse l'inscription, then un email de notification est envoyé avec le statut et le motif éventuel.
- Given une demande d'annulation déposée, when l'organisateur valide le remboursement ou refuse l'annulation, then un email d'arbitrage est envoyé avec le motif consigné.
- Given un événement annulé d'urgence, when l'organisateur confirme l'annulation générale, then les exposants concernés reçoivent un email explicatif d'annulation d'urgence.
- Given un environnement sans serveur SMTP configuré, when un événement transactionnel survient, then l'email est journalisé en statut `simulated` sans bloquer ni altérer la réponse API.

## Implementation Notes

- Added `jinja2>=3.1.4` and SMTP configurations with `FRONTEND_BASE_URL` in `backend/app/core/config.py`.
- Created `EmailLog` model (`subject` VARCHAR(500) with UTC timestamps) and Alembic migration `007_create_email_logs.py`.
- Crafted responsive Jinja2 email templates (HTML + text alternative) with passwordless magic HMAC direct URLs (`/confirmation` and `/annulation`).
- Built resilient `email_service.py` with automatic simulation fallback (`status="simulated"`), UTF-8 RFC 5322 header encoding, socket cleanup, idempotent sending checks, and scalar ID resolution (`_resolve_order_and_event`) to guarantee safety with FastAPI `BackgroundTasks`.
- Integrated background tasks in `webhooks.py`, `public.py`, and `orders.py` (including audit endpoint `GET /{id_or_slug}/orders/{order_id}/emails`).
- 17 dedicated tests in `backend/tests/test_email_service.py` covering template compilation, simulation mode, SMTP error resilience, duplicate idempotency, API manual booking, moderation approve/reject, arbitration refund/reject, emergency event cancellation, webhooks triggers, and public polling sync.

## Review Triage Log

- Addressed code review findings from Blind Hunter, Edge Case Hunter, and Verification Gap Reviewer:
  1. Enforced scalar UUID passing (`order=order.id, event=event.id`) across all endpoints to eliminate detached session issues in `BackgroundTasks`.
  2. Implemented RFC 5322 MIME encoding with `Header` and `formataddr` for accented French email headers.
  3. Added idempotency guards for moderation and arbitration emails to protect against duplicate webhook retries.
  4. Prevented spurious rejection emails on abandoned checkouts (`payment_intent.canceled` restricted to `pending_approval`).
  5. Enlarged `EmailLog.subject` to VARCHAR(500) and added truncation protection to avoid PostgreSQL `DataError`.
  6. Added comprehensive webhook trigger tests and public order sync tests in `test_email_service.py`.

