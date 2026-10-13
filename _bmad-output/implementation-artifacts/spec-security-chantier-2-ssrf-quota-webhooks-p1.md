---
title: 'Chantier Sécurité 2 - SSRF WeasyPrint, Quota Panier (Anti-Hoarding), Résilience Webhooks & Durcissement Uploads (P1)'
type: 'security'
created: '2026-10-13'
status: 'done'
baseline_commit: ef1571c
route: 'dispatch'
review_loop_iteration: 1
context:
  - _bmad-output/implementation-artifacts/epic-8-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:**
L'audit de sécurité multi-agents a identifié 4 vulnérabilités et risques de robustesse importants (P1) :
1. **SEC-P1-01 (Risque SSRF & Lecture de fichiers locaux dans la génération PDF WeasyPrint)** :
   `generate_attestation_pdf` et `generate_checkin_pdf` invoquent `weasyprint.HTML(string=...).write_pdf()` sans `url_fetcher` personnalisé. Bien que le HTML utilise du templating Jinja2, WeasyPrint par défaut tente de résoudre toute ressource externe (`http://`, `https://`, `file:///`, etc.), exposant le serveur à une lecture de métadonnées cloud (`http://169.254.169.254/`) ou de fichiers locaux.
2. **SEC-P1-02 (Déni de service par accaparement des stands / Cart Hoarding)** :
   Dans `lock_public_spot` (`backend/app/api/v1/endpoints/public.py`), aucune limite n'est imposée sur le nombre d'emplacements qu'une session peut verrouiller simultanément. Un attaquant muni d'un simple script ou d'un `session_token` peut verrouiller tous les stands d'un événement pendant 15 minutes à répétition.
3. **SEC-P1-03 (Résilience Stripe Webhook & Auto-remboursement sur conflit 409)** :
   Dans `webhooks.py`, si `confirm_order_from_payment_intent` ou `hold_order_for_approval` lève une exception `HTTPException(409, "Conflit de réservation")` (parce qu'un autre visiteur a confirmé le stand entre-temps), le webhook Stripe lève une exception HTTP non interceptée. Stripe reçoit une erreur 409/500 et réessaye indéfiniment en boucle. L'acheteur ayant payé reste bloqué sans commande valide et sans remboursement automatique.
4. **SEC-P1-04 (Durcissement des téléversements et restriction Swagger/OpenAPI en production)** :
   - `upload_background_image` dans `events.py` utilise l'extension fournie par le client plutôt qu'une extension strictement déduite des magic bytes validés (comme le fait déjà `upload_poster_image`).
   - Swagger/OpenAPI (`/docs`, `/redoc`) reste actuellement exposé par défaut quel que soit `ENVIRONMENT`.

**Approach:**
1. **Strict URL Fetcher dans WeasyPrint (`pdf_service.py`)** :
   Créer une classe `StrictURLFetcher` universelle et appelable qui interdit formellement tout accès réseau ou système de fichiers (`raise ValueError("External resource loading forbidden")`). Passer cette instance à tout appel `weasyprint.HTML(..., url_fetcher=strict_url_fetcher)`.
2. **Quota de stands par session (`public.py` & `config.py`)** :
   Définir une variable configurable `MAX_CART_SPOTS_PER_SESSION = 5` dans `Settings`. Dans `lock_public_spot` et `create_guest_order`, compter les stands actifs verrouillés par le `session_token`. Si le total dépasse le quota, lever `HTTP 400 Bad Request` avec un message explicite.
3. **Gestion des conflits 409 dans les webhooks Stripe (`webhooks.py`)** :
   Encadrer les appels `confirm_order_from_payment_intent` et `hold_order_for_approval` dans `webhooks.py`. En cas de `HTTPException(409)`, libérer immédiatement les stands verrouillés de la commande, déclencher un remboursement d'urgence via `stripe.Refund.create` (ou `stripe.PaymentIntent.cancel`), marquer la commande `refunded` avec la note `"[Système] Conflit de stand lors du webhook de paiement : remboursement automatique effectué."`, et retourner `{ "status": "conflict_refunded", "reason": "spot_already_taken" }` (200 OK pour Stripe). Si le remboursement Stripe échoue, lever 502 Bad Gateway pour contraindre Stripe à retenter.
4. **Durcissement des uploads & OpenAPI** :
   - Déduire strictement l'extension (`.png`, `.jpg`, `.webp`) à partir des magic bytes réels du fichier, normaliser le `Content-Type` (acceptant `image/jpg`), et vérifier qu'aucun autre événement n'utilise l'ancien fichier avant suppression sur disque.
   - Restreindre l'exposition de `docs_url` et `redoc_url` dans `main.py` lorsque `settings.ENVIRONMENT in ("production", "prod")`.

## Boundaries & Constraints

**Always:**
- Interdire strictement tout appel réseau ou accès fichier local lors du rendu PDF WeasyPrint.
- Limiter le nombre de stands verrouillables à 5 par session visiteur.
- Garantir qu'un client ayant payé sur Stripe dont le stand a été pris en collision soit remboursé automatiquement et immédiatement, sans blocage du webhook Stripe.
- Déduire l'extension des fichiers téléversés exclusivement depuis les magic bytes vérifiés.

**Never:**
- Ne jamais laisser Stripe boucler sur un webhook en échec permanent suite à un conflit de stands réservés.
- Ne jamais exposer la documentation interactive `/docs` en production publique si l'environnement est configuré en production.

</frozen-after-approval>

## Code Map

- `backend/app/core/config.py` -- Définition configurable de `MAX_CART_SPOTS_PER_SESSION = 5`.
- `backend/app/services/pdf_service.py` -- Implémentation de `StrictURLFetcher` interdisant les accès externes / locaux.
- `backend/app/api/v1/endpoints/public.py` -- Quota `MAX_CART_SPOTS_PER_SESSION` dans `lock_public_spot` et `create_guest_order`.
- `backend/app/api/v1/endpoints/webhooks.py` -- Capture 409, libération des stands, auto-remboursement Stripe et ack 200 OK.
- `backend/app/api/v1/endpoints/events.py` -- Extension stricte par magic bytes et protection contre suppression partagée.
- `backend/app/main.py` -- Désactivation conditionnelle de `/docs` et `/redoc` en production.
- `backend/tests/test_security_chantier_2.py` -- Suite de tests automatisés validant les 7 scénarios clés de Chantier 2.

## Tasks & Acceptance

**Execution:**
- [x] Implémenter `StrictURLFetcher` dans `pdf_service.py` et le passer à tous les appels `weasyprint.HTML`.
- [x] Ajouter la configuration et vérification du quota `MAX_CART_SPOTS_PER_SESSION` dans `public.py` et `create_guest_order`.
- [x] Implémenter la gestion du conflit 409 avec auto-remboursement Stripe, note d'audit et libération des stands dans `webhooks.py`.
- [x] Sécuriser l'extension d'upload de plan de salle dans `events.py` avec magic bytes et vérification des références partagées.
- [x] Désactiver `/docs` et `/redoc` en production dans `main.py`.
- [x] Créer `backend/tests/test_security_chantier_2.py` pour valider les comportements (7/7 passants).
- [x] Exécuter la revue multi-agents BMAD (`bmad-code-review`) avec 4 sous-agents indépendants.
- [x] Traiter les retours de la revue (callable fetcher, alignement des notes/raisons, gestion d'échec Stripe 502, libération des stands orphelins).
- [x] Valider la non-régression globale (64/64 tests passants, frontend build réussi).

