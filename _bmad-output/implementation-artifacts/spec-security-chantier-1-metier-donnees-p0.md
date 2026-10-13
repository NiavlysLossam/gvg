---
title: 'Chantier Sécurité 1 - Durcissement Métier, Données & Authentification (P0)'
type: 'security'
created: '2026-10-13'
status: 'done'
baseline_commit: eb1f26c
route: 'dispatch'
review_loop_iteration: 1
context:
  - _bmad-output/implementation-artifacts/epic-8-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:**
L'audit de sécurité approfondi mené par 4 sous-agents BMAD a mis en évidence 4 failles critiques (P0) :
1. **SEC-CRIT-01 (Fuite de données personnelles & détournement de commande dans `create_guest_order`)** : Lorsqu'un visiteur réserve un stand, le code réutilise sans vérification d'e-mail ou de session une commande `pending` existante abandonnée par un visiteur précédent. L'identité, l'adresse, l'e-mail, le téléphone et l'access token de la commande antérieure fuient vers le nouvel utilisateur.
2. **SEC-CRIT-02 (`JWT_SECRET_KEY` par défaut non bloquée et non générée sur Ubuntu)** : La configuration utilise une clé par défaut publique qui n'est ni bloquée au démarrage en production dans `Settings`, ni générée automatiquement dans `scripts/install-ubuntu.sh`.
3. **SEC-CRIT-03 (Remboursement partiel libérant à tort tous les stands de l'exposant)** : Dans `process_order_refund`, tout remboursement (même partiel, ex. 10 € sur 60 €) libère immédiatement l'intégralité des stands de l'exposant et passe le statut à `refunded`.
4. **SEC-CRIT-04 (Risque de double réservation par absence de verrou transactionnel `FOR UPDATE`)** : Dans `confirm_order_from_payment_intent` et `hold_order_for_approval`, la lecture des stands ne pose pas de verrou `with_for_update()`, permettant à deux confirmations concurrentes de s'exécuter simultanément sur le même stand.

**Approach:**
1. **Isolation stricte de session dans `create_guest_order`** : Si une commande `pending` existe sur les stands demandés, ne la réutiliser que si son e-mail correspond strictement à `payload.email`. Si l'e-mail est différent (ou si la commande est orpheline suite à expiration), annuler formellement l'ancienne commande abandonnée (`order.status = "cancelled"`, note explicite) et créer une nouvelle commande propre pour le nouvel acheteur.
2. **Protection stricte de `JWT_SECRET_KEY`** :
   - Ajouter un validateur `@model_validator` dans `backend/app/core/config.py` interdisant formellement le démarrage si `ENVIRONMENT != "development"` et que `JWT_SECRET_KEY` est la valeur par défaut ou comporte moins de 32 caractères.
   - Générer et injecter un secret aléatoire fort (`openssl rand -hex 32`) dans `scripts/install-ubuntu.sh` lors de l'installation ou de la génération de `.env`.
3. **Conservation des stands lors des remboursements partiels** :
   - Dans `process_order_refund` (`stripe_service.py`), ne libérer les stands et ne passer le statut à `refunded` **que** si le remboursement est total (`amount_cents is None or amount_cents >= order.total_price_cents`).
   - En cas de remboursement partiel, maintenir les stands en statut `reserved`, conserver la commande en statut actif (`confirmed`) et consigner le montant du remboursement partiel dans les `admin_notes`.
   - Rendre la clé d'idempotence Stripe dynamique (`f"refund_{order.id}_{uuid.uuid4().hex[:8]}"`) pour autoriser plusieurs remboursements partiels successifs.
4. **Verrou pessimiste `with_for_update()`** :
   - Verrouiller explicitement les lignes `spots` avec `.with_for_update()` dans `confirm_order_from_payment_intent` et `hold_order_for_approval` pour garantir une exclusion mutuelle stricte sous PostgreSQL.

## Boundaries & Constraints

**Always:**
- Garantir qu'aucune donnée personnelle (PII) d'une ancienne commande `pending` abandonnée ne soit renvoyée à un visiteur tiers.
- Refuser impérativement le démarrage de l'application en production avec la clé secrète JWT par défaut.
- Protéger les stands d'un exposant ayant reçu un geste commercial ou remboursement partiel (ne jamais les libérer).
- Sérialiser les vérifications de statut de stands lors de la confirmation par carte bancaire.

**Never:**
- Ne jamais renvoyer une commande existante à un utilisateur dont l'e-mail diffère de la commande.
- Ne jamais marquer une commande comme `refunded` si seule une partie de la somme a été remboursée.
- Ne jamais permettre de double attribution d'un même stand physique.

</frozen-after-approval>

## Code Map

- `backend/app/api/v1/endpoints/public.py` -- Annulation des anciennes commandes pending orphelines et vérification d'e-mail dans `create_guest_order`.
- `backend/app/core/config.py` -- Validation Pydantic stricte de `JWT_SECRET_KEY` et `ENVIRONMENT`.
- `scripts/install-ubuntu.sh` -- Génération automatique de `JWT_SECRET_KEY` avec `openssl rand -hex 32`.
- `backend/app/services/stripe_service.py` -- Verrouillage pessimiste `.with_for_update()`, conservation des stands sur remboursement partiel, et clé d'idempotence dynamique de remboursement.

## Tasks & Acceptance

**Execution:**
- [x] Mettre à jour `create_guest_order` dans `backend/app/api/v1/endpoints/public.py` pour éliminer la fuite PII et le détournement de commande.
- [x] Ajouter la validation Pydantic de `JWT_SECRET_KEY` dans `backend/app/core/config.py`.
- [x] Mettre à jour `scripts/install-ubuntu.sh` pour générer automatiquement `JWT_SECRET_KEY`.
- [x] Mettre à jour `stripe_service.py` pour le verrouillage `with_for_update()` et la logique de remboursement partiel.
- [x] Écrire des tests automatisés complets validant les 4 corrections dans `backend/tests/test_security_chantier_1.py`.
- [x] Lancer la revue de code BMAD (`bmad-code-review`) avec les 4 sous-agents de revue.
- [x] Traiter l'ensemble des retours critiques de la revue de code (gestion des conflits dans `hold_order_for_approval`, réconciliation de `cancellation_requested` sur remboursement partiel, extension de `locked_until` sur réutilisation de commande).
- [x] Valider l'ensemble des suites de tests automatisés (5/5 tests Chantier 1 passants, 52/52 tests régressions passants, build frontend vite réussi sans erreur).

