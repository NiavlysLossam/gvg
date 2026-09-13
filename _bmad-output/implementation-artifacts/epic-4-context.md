# Epic 4 Context: Module de Communication & E-mailing

<!-- Compiled from planning artifacts (PRD, Architecture Spine, UX Designs, Epics). Edit freely. -->

## Goal

Automatiser la transmission des informations clés par email pour les exposants (confirmations de réservation, reçus, notifications d'arbitrage de modération ou de remboursement, rappels programmés à J-7 et J-2) et offrir à l'organisateur (Marc) un outil de diffusion d'annonces de masse personnalisées avec variables dynamiques et prévisualisation en direct.

## Stories

- **Story 4.1 : E-mails Transactionnels Automatisés (Confirmation, Reçus & Suivi d'Arbitrage)**
- **Story 4.2 : Rappels Automatiques Programmés J-7 et J-2**
- **Story 4.3 : Envoi Manuel d'E-mails Groupés avec Variables Dynamiques**

## Requirements & Constraints

- **Asynchronisme strict (AD-7) :** L'envoi d'emails ne doit JAMAIS bloquer le thread HTTP de l'API FastAPI. Tous les envois sont exécutés en arrière-plan via `BackgroundTasks` ou worker dédié.
- **Gabarits HTML élégants & Fallback texte :** Tous les emails transactionnels utilisent le moteur de template Jinja2, sont responsive pour lecture mobile, et incluent une version texte brut (`multipart/alternative`).
- **Configuration SMTP flexible & Mode Dev :**
  - Paramètres SMTP configurables via variables d'environnement (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_TLS`, `EMAILS_FROM_EMAIL`, `EMAILS_FROM_NAME`).
  - En environnement de développement ou si le SMTP n'est pas configuré, le service bascule automatiquement en mode simulation (journalisation locale des emails sans échec réseau).
- **Zéro mot de passe / Liens signés :** Les emails transactionnels contiennent les URLs d'accès direct sécurisées par le token unifié de la commande (`/e/:slug/confirmation/:orderId?token=...` et `/e/:slug/annulation/:orderId?token=...`).
- **Traçabilité des envois :** Historisation des messages envoyés dans la base de données (type de message, destinataire, sujet, statut de délivrance, horodatage) pour visibilité organisateur et prévention des envois multiples.

## Technical Decisions

- **Service d'email dédié (`backend/app/services/email_service.py`) :**
  - Fonctions spécialisées : `send_order_confirmation_email`, `send_moderation_status_email`, `send_refund_arbitration_email`, `send_event_cancellation_email`.
  - Intégration transparente avec `BackgroundTasks` de FastAPI dans les endpoints de réservation (`public.py`), de webhooks (`webhooks.py`), et d'arbitrage (`orders.py`).
- **Templates Jinja2 (`backend/app/templates/emails/`) :**
  - `base.html` : En-tête avec titre du vide-grenier, pied de page avec mentions légales et coordonnées de l'organisateur.
  - `order_confirmation.html` : Récapitulatif des stands, métrage, montant, horaires d'installation, lien d'accès et consignes du Jour J.
  - `moderation_update.html` : Notification d'acceptation (fonds capturés) ou de refus (pré-autorisation levée, stands libérés) avec motif éventuel.
  - `refund_arbitration.html` : Notification de validation de remboursement ou de refus avec motif obligatoire.
  - `event_cancellation.html` : Notification d'annulation d'urgence pour force majeure / météo et explications sur le remboursement.
- **Journalisation des emails (`email_logs`) :**
  - Table SQLAlchemy dédiée enregistrant chaque envoi lié à une commande ou un événement : id, event_id, order_id, recipient, email_type, subject, status (sent/failed/simulated), sent_at, error_message.

## Cross-Story Dependencies

- **Story 4.1** crée le moteur d'envoi d'emails (configuration SMTP, service d'envoi, templates Jinja2 de base, logging) et branche les déclencheurs transactionnels (confirmation de commande, modération, arbitrage, annulation événement).
- **Story 4.2** réutilisera ce moteur et ajoutera la planification temporelle (J-7 / J-2) avec idempotence des rappels.
- **Story 4.3** fournira l'interface administrateur d'envoi groupé avec éditeur de variables dynamiques s'appuyant sur ce service.

