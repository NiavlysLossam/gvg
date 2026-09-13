---
title: "Story 4.3 : Envoi Manuel d'E-mails Groupés avec Variables Dynamiques"
type: 'feature'
created: '2026-09-13'
status: 'done'
baseline_commit: '479af126b4bed462017f061459786e64d0da03bb'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '_bmad-output/implementation-artifacts/epic-4-context.md'
  - '_bmad-output/planning-artifacts/architecture/architecture-gvg-2026-09-04/ARCHITECTURE-SPINE.md'
  - '_bmad-output/planning-artifacts/ux-designs/ux-gvg-2026-09-04/EXPERIENCE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** En cours d'organisation ou à la veille de l'événement, l'organisateur (Marc) doit pouvoir diffuser des consignes imprévues ou des alertes ciblées (alerte météo, déviation d'accès routier, rappel des horaires de portail, consignes de stationnement) à l'ensemble de ses exposants inscrits. Actuellement, aucun outil ne permet de rédiger un message personnalisé de masse directement depuis la plateforme sans exporter les emails vers un outil externe.

**Approach:**
1. Concevoir un système d'interpolation de variables dynamiques (`{{exposant.prenom}}`, `{{exposant.nom}}`, `{{commande.numero}}`, `{{commande.emplacements}}`, `{{evenement.titre}}`, `{{evenement.date}}`, `{{commande.lien}}`) avec support des syntaxes `{variable}` et `{{variable}}`.
2. Créer un gabarit d'e-mail responsive (`custom_broadcast.html` et `custom_broadcast.txt`) respectant la charte visuelle GVG (`base.html`), avec en-tête de l'événement, mise en page aérée des paragraphes du message, encadré récapitulatif du stand et pied de page officiel.
3. Développer un service backend (`broadcast_service.py`) avec prévisualisation en direct (`/preview`), envoi unitaire de test, et diffusion asynchrone non-bloquante via `BackgroundTasks` (`/send`), enregistrant chaque notification dans `email_logs` (`email_type='custom_broadcast'`).
4. Intégrer une modale d'envoi de diffusion groupée (`BroadcastModal.tsx`) dans le tableau de bord de gestion des inscriptions (`RegistrationsPage.tsx`), offrant des badges d'insertion de tags au clic, un onglet d'aperçu dynamique en temps réel, un sélecteur d'audience (tous les confirmés ou sélection courante du tableau) et une confirmation sécurisée.

## Boundaries & Constraints

**Always:**
- L'envoi groupé de masse doit TOUJOURS être asynchrone (FastAPI `BackgroundTasks`) pour ne jamais bloquer la requête HTTP de l'organisateur.
- Seules les commandes au statut `confirmed` avec une adresse e-mail valide reçoivent l'e-mail (les commandes sans e-mail, annulées ou rejetées sont ignorées).
- Chaque e-mail expédié ou simulé génère un enregistrement dans `email_logs` avec `email_type='custom_broadcast'`, le sujet évalué et le destinataire.
- En cas de défaillance SMTP ou d'absence de configuration SMTP, basculer en mode `simulated` sans faire échouer le traitement.
- Toute variable non reconnue ou manquante dans le texte rédigé est remplacée proprement ou laissée vide sans générer d'exception `KeyError`.

**Never:**
- Ne jamais expédier d'e-mails réels sans confirmation explicite de l'organisateur via la boîte de dialogue modale.
- Ne jamais bloquer le thread principal ni lever d'exception non gérée interrompant la boucle d'envoi en cas d'erreur sur un destinataire isolé.
- Ne jamais exposer de données sensibles d'autres exposants dans le contenu du message.

## I/O & Edge-Case Matrix

| Scénario | Données en entrée | Résultat attendu | Gestion d'erreur / Robustesse |
|---|---|---|---|
| Aperçu dynamique en direct | Sujet et corps avec tags `{{exposant.prenom}}` et `{{commande.emplacements}}` | Rendu HTML/texte instantané basé sur une commande test ou premier inscrit | Si aucune commande n'existe, utilise des données d'exemple réalistes |
| Envoi de test | `is_test=True`, `test_recipient='marc@test.com'` | Envoi d'un seul email de validation à l'organisateur avec les tags évalués | Aucun email envoyé aux vrais exposants |
| Diffusion générale nominale | `target_audience='all_confirmed'` (ex. 84 inscrits) | Tâche de fond lancée, 84 messages individualisés envoyés et logués | Comptabilisation des envois, succès et échecs |
| Exposants sans e-mail | 3 commandes au guichet avec `email=None` | Ces 3 commandes sont comptabilisées dans `recipients_without_email` et ignorées | Aucun plantage ni tentative d'envoi SMTP |
| Erreur réseau SMTP partielle | Connexion SMTP rejetée pour le 12e destinataire | Logué avec `status='failed'`, la boucle continue pour les 83 autres | Rapport final incluant le détail des erreurs |
| Balise inconnue ou mal formée | `{{variable_inconnue}}` ou accolade orpheline `{` | Remplacement propre ou préservation du texte brut | Zéro plantage de regex ou template |

</frozen-after-approval>

## Code Map

- `backend/app/templates/emails/` -- Gabarits Jinja2 pour l'envoi personnalisé :
  - `custom_broadcast.html` : Gabarit HTML avec mise en page des paragraphes, bouton d'accès au stand, mentions légales.
  - `custom_broadcast.txt` : Alternative texte brut.
- `backend/app/schemas/broadcast.py` -- Schémas Pydantic pour prévisualisation et diffusion :
  - `BroadcastPreviewRequest`, `BroadcastPreviewResponse`, `BroadcastSendRequest`, `BroadcastSendResponse`.
- `backend/app/services/broadcast_service.py` -- Moteur d'interpolation et de diffusion :
  - `render_dynamic_tags(text: str, context: dict) -> str` : Substitution sécurisée des balises.
  - `generate_broadcast_preview(event_id: uuid.UUID, subject: str, body: str, db: Session)` : Aperçu évalué.
  - `send_broadcast_emails(event_id: uuid.UUID, payload: BroadcastSendRequest, db: Session)` : Dispatch asynchrone et traçabilité.
- `backend/app/api/v1/endpoints/broadcast.py` -- Endpoints FastAPI :
  - `POST /api/v1/events/{id_or_slug}/broadcast/preview` : Génération de l'aperçu instantané.
  - `POST /api/v1/events/{id_or_slug}/broadcast/send` : Déclenchement de la diffusion avec `BackgroundTasks`.
- `backend/app/api/v1/router.py` -- Enregistrement du routeur `broadcast.router`.
- `frontend/src/types/broadcast.ts` -- Types TypeScript pour prévisualisation et envoi.
- `frontend/src/components/BroadcastModal.tsx` -- Modale d'édition avec tags cliquables, onglet d'aperçu live et confirmation.
- `frontend/src/pages/RegistrationsPage.tsx` -- Bouton d'ouverture dans la barre d'outils et passage de la sélection d'ordres.
- `frontend/src/lib/api.ts` -- Fonctions clientes `previewBroadcastEmail` et `sendBroadcastEmail`.
- `backend/tests/test_broadcast_service.py` -- Suite de tests automatisés.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/templates/emails/` -- Créer `custom_broadcast.html` et `custom_broadcast.txt`.
- [x] `backend/app/schemas/broadcast.py` -- Créer les modèles Pydantic de requête et de réponse.
- [x] `backend/app/services/broadcast_service.py` -- Implémenter l'interpolation des tags, la prévisualisation et la diffusion.
- [x] `backend/app/api/v1/endpoints/broadcast.py` & `router.py` -- Exposer et monter les endpoints `/preview` et `/send`.
- [x] `frontend/src/types/broadcast.ts` & `frontend/src/lib/api.ts` -- Déclarer les interfaces et appels API frontend.
- [x] `frontend/src/components/BroadcastModal.tsx` -- Développer l'interface d'édition, insertion de tags, prévisualisation live et confirmation.
- [x] `frontend/src/pages/RegistrationsPage.tsx` -- Intégrer le déclencheur d'envoi groupé avec support des sélections.
- [x] `backend/tests/test_broadcast_service.py` -- Valider la substitution des tags, les aperçus, l'asynchronisme et les cas d'erreur.

**Acceptance Criteria:**
- Given Marc sur le tableau de bord des inscriptions d'un événement, when il clique sur "Diffuser un e-mail", then la modale s'ouvre avec la liste des tags disponibles et le nombre d'inscrits ciblés.
- Given la saisie d'un sujet et d'un corps contenant `{{exposant.prenom}}` et `{{commande.emplacements}}`, when Marc consulte l'onglet Aperçu, then les variables sont remplacées en temps réel avec les données d'un inscrit.
- Given un clic sur "Envoyer", when l'organisateur confirme dans la boîte de dialogue, then l'API répond immédiatement avec le statut `enqueued` et les messages sont expédiés en tâche de fond.
- Given chaque e-mail expédié, when la diffusion se termine, then chaque message est consigné dans `email_logs` avec `email_type='custom_broadcast'`.

## Implementation Notes

- **Gabarits d'e-mail responsive (`custom_broadcast.html`, `custom_broadcast.txt`)** :
  - Mise en page respectant la charte visuelle GVG (`base.html`), conversion sécurisée des sauts de ligne en paragraphes `<p>` et retours `<br/>`.
  - Élimination des salutations dupliquées pour laisser l'organisateur libre de son accroche.
  - Encadré de rappel du stand (numéro de commande, numéros d'emplacements, métrage, lien d'accès passwordless).
- **Moteur d'interpolation (`broadcast_service.py`)** :
  - Supporte les syntaxes `{tag}` et `{{tag}}`, y compris les variantes accentuées (`{{exposant.prénom}}`, `{{événement.titre}}`, `{{commande.emplacement}}`).
  - Échappement HTML strict pour prévenir toute injection XSS dans le template d'email.
  - Gestion des créneaux d'installation : si non configurés, `setup_hours` est omis proprement sans inventer d'horaire d'arrivée.
- **Sécurité & Isolation du mode test** :
  - Les e-mails de test envoyés à l'organisateur sont isolés (`order_id=None`), ne polluant pas l'historique d'audit des vrais exposants.
  - Rejet HTTP 400 immédiat en cas de tentative de diffusion sur un événement au statut `cancelled`.
  - Si `target_audience == "selected"` et qu'aucun ordre n'est fourni (`[]`), la requête est rejetée en HTTP 400 pour empêcher toute diffusion involontaire à tous les exposants.
- **Interface Administrateur (`BroadcastModal.tsx` & `RegistrationsPage.tsx`)** :
  - Insertion fluide des balises dynamiques au niveau du curseur.
  - Onglet d'aperçu dynamique instantané généré côté serveur.
  - Le mode test n'efface plus le brouillon et ne ferme plus la modale : confirmation visuelle en direct.
  - Sélection multiple de lignes dans le tableau des inscriptions avec bandeau d'actions rapides groupées.

## Spec Change Log

- **2026-09-13** : Prise en charge des variables accentuées et rejet strict des événements annulés.

## Review Triage Log

- **Blind Hunter / Edge Case Hunter / Verification Gap Reviewer** :
  - [x] Sélection vide (`selected_order_ids=[]`) : corrigé pour ne plus jamais diffuser à tous les inscrits (rejet HTTP 400).
  - [x] Événements annulés : rejet HTTP 400 implémenté sur `/preview` et `/send`.
  - [x] Mode test : conservation du brouillon et maintien de la modale ouverte, `order_id=None` dans `EmailLog`.
  - [x] Assainissement des retours à la ligne dans le sujet (protection injection CRLF).
  - [x] Suppression de la salutation en doublon dans le template `custom_broadcast.html`.
  - [x] Support des balises avec accents français (`prénom`, `événement`).
  - [x] Couverture de test complète : 17 tests validant l'asynchronisme `BackgroundTasks`, la sélection d'ordres, l'idempotence et les cas d'erreur.

