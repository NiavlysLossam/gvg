---
title: "Story 4.2 : Rappels Automatiques Programmés J-7 et J-2"
type: 'feature'
created: '2026-09-13'
status: 'done'
baseline_commit: '132bd51e176851bcacd252a940fad492bf20e2fd'
route: 'dispatch'
review_loop_iteration: 1
context:
  - '_bmad-output/implementation-artifacts/epic-4-context.md'
  - '_bmad-output/planning-artifacts/architecture/architecture-gvg-2026-09-04/ARCHITECTURE-SPINE.md'
  - '_bmad-output/planning-artifacts/ux-designs/ux-gvg-2026-09-04/EXPERIENCE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** À l'approche de la date du vide-grenier, les exposants inscrits risquent d'oublier des informations opérationnelles indispensables pour le bon déroulement du Jour J : les horaires stricts d'ouverture des barrières et d'installation (`setup_start_time` à `setup_end_time`), l'itinéraire d'accès et l'adresse exacte, la liste des emplacements attribués, et surtout l'obligation légale (Art. L310-2 du Code de commerce) d'apporter l'original de leur pièce d'identité et leur attestation sur l'honneur signée. Sans rappels automatiques et sans visibilité pour l'organisateur, les arrivées au petit matin risquent d'engendrer des bouchons, des litiges et des refus d'accès.

**Approach:** 
1. Concevoir des gabarits d'e-mails de rappel élégants et responsives (HTML + texte brut) pour les échéances J-7 et J-2, récapitulant les consignes opérationnelles, les horaires, les stands réservés et les documents obligatoires.
2. Développer un service de détection et de traitement planifié des rappels (`reminder_service.py`) avec **idempotence absolue** garantie par la table `email_logs` (`email_type='reminder_j7'` et `email_type='reminder_j2'`).
3. Fournir une triple passerelle d'exécution : un endpoint API d'audit et de déclenchement pour l'organisateur (`POST /api/v1/events/{id_or_slug}/reminders/trigger` et `GET .../reminders/status`), un endpoint système pour les tâches cron externes (`POST /api/v1/system/reminders/process`), et un script d'exécution autonome en CLI (`python -m app.scripts.process_reminders`).
4. Intégrer un widget d'état des rappels sur le tableau de bord organisateur afin d'offrir une visibilité immédiate sur les rappels envoyés et à venir.

## Boundaries & Constraints

**Always:**
- Les rappels ne ciblent STRICTEMENT que les commandes au statut `confirmed` rattachées à un événement `published`. Les commandes annulées, refusées ou en attente d'approbation sont rigoureusement exclues.
- Tout envoi d'email de rappel doit être idempotent : si un log avec le statut `sent` ou `simulated` existe déjà dans `email_logs` pour le couple `(order_id, email_type)`, aucun second e-mail n'est expédié.
- Les envois sont asynchrones via `BackgroundTasks` ou script non bloquant pour ne jamais saturer l'API.
- L'e-mail doit inclure le lien d'accès direct passwordless de la commande (`/e/:slug/confirmation/:orderId?token=...`).
- Si aucun serveur SMTP n'est configuré, le service bascule automatiquement en mode simulation (`status="simulated"`), trace l'action dans `email_logs` et renvoie un rapport d'exécution valide.
- Ne jamais lever d'exception non interceptée : si l'envoi d'un email échoue pour un exposant, l'erreur est consignée dans `email_logs` (`status="failed"`) et le traitement continue pour les autres exposants.

**Never:**
- Ne jamais envoyer de rappel à un exposant sans adresse e-mail (ex: saisie manuelle guichet sans e-mail).
- Ne jamais réexpédier un rappel J-7 ou J-2 lors de déclenchements multiples ou de cron répété.
- Ne jamais bloquer la réponse API de l'organisateur lors d'un déclenchement manuel.

## I/O & Edge-Case Matrix

| Scénario | Données en entrée | Résultat attendu | Gestion d'erreur / Robustesse |
|---|---|---|---|
| Traitement automatique J-7 | Événement à J-7 (entre 7 et 2 jours avant `start_date`) | E-mails J-7 envoyés à tous les exposants confirmés non encore notifiés. | Logué dans `email_logs` (`email_type="reminder_j7"`). |
| Traitement automatique J-2 | Événement à J-2 (entre 2 et 0 jours avant `start_date`) | E-mails J-2 envoyés à tous les exposants confirmés non encore notifiés. | Logué dans `email_logs` (`email_type="reminder_j2"`). |
| Double exécution de la tâche cron | Le cron s'exécute deux fois le même jour | La seconde exécution détecte les logs existants et ignore les commandes déjà notifiées (`reminders_skipped += 1`). | 0 doublon envoyé. |
| Commande sans email (guichet) | `order.email = None` | L'ordre est ignoré proprement dans la boucle sans générer d'erreur. | Comptabilisé dans `orders_without_email`. |
| Commande annulée ou en modération | `order.status in ('rejected', 'refunded', 'pending_approval', 'cancellation_requested')` | Aucune notification envoyée. | Seules les commandes `confirmed` sont éligibles. |
| Événement passé ou annulé | `event.status == 'cancelled'` ou `event.start_date < now` | Événement ignoré par le planificateur. | Aucun envoi rétroactif. |
| Déclenchement manuel anticipé par l'organisateur | Clic "Déclencher rappel J-7" depuis le tableau de bord | Envoi immédiat des rappels J-7 aux exposants éligibles et mise à jour du statut. | Réponse JSON immédiate avec rapport. |

</frozen-after-approval>

## Code Map

- `backend/app/templates/emails/` -- Gabarits Jinja2 pour les rappels :
  - `reminder_j7.html` / `reminder_j7.txt` : Rappel J-7 avec préparation de l'arrivée, récapitulatif des stands, rappel des pièces obligatoires.
  - `reminder_j2.html` / `reminder_j2.txt` : Rappel J-2 (ultime rappel avant Jour J) avec consignes d'accès, météo et barrières.
- `backend/app/services/reminder_service.py` -- Moteur de planification et d'envoi des rappels :
  - `calculate_event_reminder_windows(event: Event, now: Optional[datetime] = None) -> dict`
  - `send_order_reminder_email(order: Union[Order, uuid.UUID], event: Union[Event, uuid.UUID], reminder_type: str, db: Optional[Session] = None) -> Optional[EmailLog]`
  - `process_event_reminders(event_id: uuid.UUID, reminder_type: Optional[str] = None, force: bool = False, db: Optional[Session] = None) -> dict`
  - `process_all_scheduled_reminders(db: Optional[Session] = None, now: Optional[datetime] = None) -> dict`
- `backend/app/schemas/reminder.py` -- Schémas Pydantic pour l'état et le déclenchement des rappels (`ReminderStatusResponse`, `ReminderTriggerResponse`).
- `backend/app/api/v1/endpoints/reminders.py` -- Endpoints FastAPI :
  - `GET /api/v1/events/{id_or_slug}/reminders/status` : Statut des rappels J-7 / J-2 et compteurs pour l'événement.
  - `POST /api/v1/events/{id_or_slug}/reminders/trigger` : Déclenchement manuel à la demande avec `BackgroundTasks`.
  - `POST /api/v1/system/reminders/process` : Déclencheur système / tâche cron globale.
- `backend/app/scripts/process_reminders.py` -- Script CLI pour intégration cron / systemd timer (`python -m app.scripts.process_reminders`).
- `frontend/src/components/RemindersCard.tsx` (ou onglet communication) -- Widget administrateur affichant le statut des rappels et le bouton de déclenchement avec confirmation.
- `backend/tests/test_reminder_service.py` -- Suite complète de tests automatisés.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/templates/emails/` -- Créer les templates `reminder_j7.html`, `reminder_j7.txt`, `reminder_j2.html`, `reminder_j2.txt`.
- [x] `backend/app/schemas/reminder.py` -- Définir les schémas Pydantic `ReminderStatusResponse` et `ReminderTriggerResponse`.
- [x] `backend/app/services/reminder_service.py` -- Implémenter la logique d'éligibilité, l'idempotence, l'envoi et les rapports.
- [x] `backend/app/api/v1/endpoints/reminders.py` & `router.py` -- Exposer les routes d'état et de déclenchement.
- [x] `backend/app/scripts/process_reminders.py` -- Créer le script CLI pour tâche cron.
- [x] `frontend/src/` -- Intégrer l'affichage du statut des rappels dans le tableau de bord de l'organisateur.
- [x] `backend/tests/test_reminder_service.py` -- Valider la logique, les fenêtres temporelles, l'idempotence et les endpoints.

**Acceptance Criteria:**
- Given un événement planifié à J-7 ou J-2, when le service de rappel est exécuté, then un email personnalisé est envoyé à chaque exposant ayant une réservation confirmée.
- Given un rappel déjà envoyé pour une commande et une échéance donnée, when la tâche s'exécute à nouveau, then aucun e-mail doublon n'est expédié.
- Given une commande sans adresse email, when les rappels sont traités, then la commande est ignorée sans provoquer d'erreur.
- Given l'interface d'administration de l'événement, when Marc consulte le tableau de bord, then il visualise l'état des rappels (J-7 et J-2) et peut déclencher manuellement un envoi anticipé.
- Given un environnement sans serveur SMTP, when le service s'exécute, then tous les rappels sont consignés en mode `simulated` dans `email_logs`.

## Implementation Notes

- **Templates Jinja2** :
  - Conçus avec support HTML responsive et fallback texte clair (`reminder_j7.html`, `reminder_j7.txt`, `reminder_j2.html`, `reminder_j2.txt`).
  - Incluent le rappel légal strict (Art. L310-2 : pièce d'identité originale et attestation sur l'honneur signée) requis pour le registre des brocantes.
  - Utilisation de dates et créneaux horaires formatés en français (`email_service.format_event_date`).
- **Moteur de rappel (`reminder_service.py`)** :
  - Calcul de fenêtres temporelles strictement disjointes : J-7 (`2.5 < days_until <= 7.5`) et J-2 (`0.0 <= days_until <= 2.5`), évitant tout chevauchement à 2.2 jours ou envoi rétroactif si l'événement a débuté.
  - Filtrage exclusif des commandes `confirmed` et des événements `published` (rejet immédiat en erreur 400 si draft/cancelled).
  - Idempotence garantie par requête d'unicité sur `EmailLog(order_id, email_type)` (`sent` ou `simulated`).
  - Tolérance aux pannes : capture des erreurs d'envoi individuelles sans interrompre le traitement global, journalisation dans `email_logs` avec statut `failed`.
- **API & Scripts** :
  - `GET /api/v1/events/{id_or_slug}/reminders/status` retourne l'état des fenêtres et les compteurs uniques d'envois.
  - `POST /api/v1/events/{id_or_slug}/reminders/trigger` supporte l'envoi immédiat synchrone ou asynchrone via `BackgroundTasks`.
  - `POST /api/v1/system/reminders/process` et script CLI `backend/app/scripts/process_reminders.py` utilisables en cron avec code de sortie strict.
- **Frontend Admin** :
  - Composant `RemindersCard.tsx` avec badges d'état (Passé, Actif, À venir), modale de confirmation avant déclenchement manuel, et rapport détaillé en direct.
  - Intégré dans l'onglet des inscriptions `RegistrationsPage.tsx`.

## Spec Change Log

- **2026-09-13** : Clarification de la séparation stricte des fenêtres temporelles à 2.5 jours pour éliminer tout chevauchement lors de l'évaluation automatique.

## Review Triage Log

- **Blind Hunter / Edge Case Hunter / Verification Gap Reviewer** :
  - [x] Fenêtre de chevauchement J-7/J-2 corrigée (`2.5 < days <= 7.5` vs `0.0 <= days <= 2.5`).
  - [x] Validation de statut d'événement ajouté (`status != "published"` rejeté).
  - [x] Formatage de la date en français vérifié dans tous les templates de rappel.
  - [x] Mention de l'attestation sur l'honneur ajoutée dans le template J-2.
  - [x] Ajout de la classe CSS `.badge-indigo` dans `base.html`.
  - [x] Modale de confirmation ajoutée dans l'interface utilisateur pour éviter les envois accidentels.
  - [x] 13 tests unitaires et d'intégration validés dans `backend/tests/test_reminder_service.py` et 179 tests backend au vert.

