---
title: "Story 5.1 : Génération Automatique du Formulaire d'Attestation PDF"
type: 'feature'
created: '2026-09-14'
status: 'done'
baseline_commit: '7c87f10eb8355c7b760b885bdcfe08b5f21678c8'
route: 'dispatch'
review_loop_iteration: 1
context:
  - '_bmad-output/implementation-artifacts/epic-5-context.md'
  - '_bmad-output/planning-artifacts/architecture/architecture-gvg-2026-09-04/ARCHITECTURE-SPINE.md'
  - '_bmad-output/planning-artifacts/ux-designs/ux-gvg-2026-09-04/EXPERIENCE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** En vertu de l'article L310-2 du Code de commerce, chaque exposant particulier participant à une vente au déballage (vide-greniers) doit obligatoirement remettre aux organisateurs une attestation sur l'honneur signée certifiant sa non-participation à plus de deux ventes au déballage au cours de l'année civile et la vente exclusive d'objets personnels et usagés. Remplir ces formulaires à la main le matin à l'arrivée sous la pluie ou dans les véhicules ralentit l'accès, crée des contestations et dégrade la tenue du registre officiel.

**Approach:**
1. Développer un service de génération PDF (`backend/app/services/pdf_service.py`) basé sur **WeasyPrint** et Jinja2, compilant à la volée en mémoire un document PDF A4 vectoriel haute fidélité.
2. Concevoir le gabarit HTML/CSS d'attestation (`backend/app/templates/pdf/attestation.html`) strictement conforme aux exigences réglementaires françaises (Art. L310-2 et R310-8 du Code de commerce, Art. 441-7 du Code pénal), pré-rempli avec les coordonnées de l'exposant, les données de l'événement et les stands attribués, avec encart de signature exposant et cadre réservé au visa du placier.
3. Exposer deux routes de téléchargement streaming direct `application/pdf` : une route publique sécurisée par token passwordless HMAC (`/api/v1/public/events/{slug}/orders/{order_id}/attestation.pdf`) et une route d'administration (`/api/v1/events/{id_or_slug}/orders/{order_id}/attestation.pdf`).
4. Intégrer le déclencheur de téléchargement dans le portail exposant (`ConfirmationPage.tsx`) et dans le tableau de bord organisateur (`RegistrationsPage.tsx`).

## Boundaries & Constraints

**Always:**
- Le document généré doit être un PDF vectoriel au format standard A4 (210 × 297 mm) avec marges d'impression professionnelles, lisible et soigné.
- L'attestation doit être pré-remplie automatiquement avec : Nom, Prénom, Adresse postale complète, Téléphone, E-mail, Numéro de commande, Numéros des stands attribués, Métrage total, Titre de l'événement, Date et Lieu de la manifestation.
- Le document doit comporter les mentions réglementaires impératives : engagement sur l'honneur de ne pas avoir participé à plus de 2 ventes au déballage dans l'année civile, attestation de vente d'objets personnels et usagés, rappel des sanctions pénales pour fausse déclaration (Art. 441-7 du Code pénal), mention de présentation obligatoire d'une pièce d'identité originale le Jour J, encart de signature manuscrite de l'exposant, et encadré de contrôle réservé à l'organisateur (type de pièce, numéro CNI/passeport relevé, visa placier).
- La génération se fait en mémoire (`bytes`) sans stockage de fichiers temporaires sur disque (zéro déchet, zéro fuite de données).
- Seules les commandes au statut `confirmed` peuvent générer l'attestation légale (rejet HTTP 400 si la commande est annulée, rejetée ou non confirmée).
- L'accès public à l'attestation doit être strictement vérifié par le token HMAC de la commande (`?token=...`).

**Never:**
- Ne jamais stocker de copie de pièces d'identité sur le serveur (principe RGPD de minimisation et décision architecturale AD-4).
- Ne jamais autoriser le téléchargement d'une attestation d'un autre exposant sans jeton HMAC valide.
- Ne jamais planter sur des caractères accentués ou des champs facultatifs manquants (ex: téléphone absent, complément d'adresse vide).

## I/O & Edge-Case Matrix

| Scénario | Données en entrée | Résultat attendu | Gestion d'erreur / Robustesse |
|---|---|---|---|
| Téléchargement nominal exposant | `slug`, `order_id`, `token` valide, commande `confirmed` | Document PDF A4 streamé (`application/pdf`) pré-rempli avec toutes les informations | En-tête `Content-Disposition: inline; filename="attestation_GVG-2026-XXXX.pdf"` |
| Téléchargement administrateur | `event_id`, `order_id` depuis tableau de bord admin | Document PDF A4 streamé sans exigence de token exposant | Vérifie que l'ordre appartient bien à l'événement |
| Jeton d'accès invalide ou manquant | `token="invalide"` ou omis sur la route publique | Rejet immédiat HTTP 403 Forbidden | Aucun contenu PDF généré ni exposé |
| Commande non confirmée | Commande en statut `pending`, `refunded` ou `rejected` | Rejet HTTP 400 Bad Request avec message explicatif | L'attestation n'est délivrée qu'aux inscrits confirmés |
| Caractères spéciaux et accents | Nom avec cédille, apostrophe, tréma, tirets | Rendu typographique parfait en UTF-8 sans entités HTML résiduelles | Jinja2 et WeasyPrint configurés en UTF-8 natif |
| Stand multiple | Commande avec 3 stands (ex: Stand 11, 12, 13) | Concaténation claire des stands et cumul du métrage | Affichage synthétique sans débordement de page |
| Coordonnées partielles (guichet) | `phone=None`, `email=None` | Affichage d'une ligne de pointillés / mention non renseigné | Pas d'erreur `NoneType` ni de décalage de mise en page |

</frozen-after-approval>

## Code Map

- `backend/pyproject.toml` -- Dépendance `weasyprint>=62.0` ajoutée.
- `backend/app/templates/pdf/` -- Gabarits WeasyPrint :
  - `attestation.html` : Gabarit HTML/CSS A4 optimisé pour l'impression, mentions Art. L310-2, coordonnées pré-remplies, encarts de signature et cadre placier.
- `backend/app/services/pdf_service.py` -- Service de compilation PDF :
  - `generate_attestation_pdf(order: Order, event: Event) -> bytes` : Récupération des données, rendu Jinja2 et compilation WeasyPrint en mémoire.
- `backend/app/api/v1/endpoints/public.py` -- Endpoint public sécurisé :
  - `GET /api/v1/public/events/{slug}/orders/{order_id}/attestation.pdf` : Téléchargement exposant avec contrôle du token HMAC.
- `backend/app/api/v1/endpoints/orders.py` -- Endpoint d'administration :
  - `GET /api/v1/events/{id_or_slug}/orders/{order_id}/attestation.pdf` : Téléchargement organisateur.
- `frontend/src/lib/api.ts` -- URL helpers pour le téléchargement PDF :
  - `getPublicAttestationPdfUrl(slug: string, orderId: string, token: string): string`
  - `getAdminAttestationPdfUrl(eventIdOrSlug: string, orderId: string): string`
- `frontend/src/pages/ConfirmationPage.tsx` -- Bouton de téléchargement branché sur l'URL de l'attestation PDF.
- `frontend/src/pages/RegistrationsPage.tsx` -- Action de téléchargement d'attestation dans le tableau des commandes.
- `backend/tests/test_pdf_service.py` -- Tests automatisés de génération PDF, conformité légale, sécurité HMAC et gestion des statuts.

## Tasks & Acceptance

**Execution:**
- [x] `backend/pyproject.toml` -- Vérifier la présence de `weasyprint>=62.0`.
- [x] `backend/app/templates/pdf/attestation.html` -- Créer le gabarit HTML/CSS d'attestation sur l'honneur A4 conforme Art. L310-2.
- [x] `backend/app/services/pdf_service.py` -- Créer le service de génération PDF WeasyPrint.
- [x] `backend/app/api/v1/endpoints/public.py` -- Implémenter le endpoint de téléchargement exposant sécurisé par token HMAC.
- [x] `backend/app/api/v1/endpoints/orders.py` -- Implémenter le endpoint de téléchargement admin.
- [x] `frontend/src/lib/api.ts` -- Définir les fonctions d'obtention d'URL d'attestation PDF.
- [x] `frontend/src/pages/ConfirmationPage.tsx` -- Connecter le bouton "Télécharger mon attestation PDF" à l'endpoint.
- [x] `frontend/src/pages/RegistrationsPage.tsx` -- Ajouter l'accès au téléchargement d'attestation pour chaque commande confirmée.
- [x] `backend/tests/test_pdf_service.py` -- Créer la suite de tests automatisés validant la génération PDF, les en-têtes HTTP, la sécurité HMAC et les cas limites.

**Acceptance Criteria:**
- Given une commande confirmée, when Monique clique sur "Télécharger mon attestation PDF" sur la page de confirmation, then le navigateur télécharge ou affiche directement le document PDF A4.
- Given le document PDF généré, when Monique ou l'organisateur l'examine, then il contient son nom, prénom, adresse, numéro de stand, métrage, date et lieu de l'événement, les mentions légales de l'Art. L310-2 et les encarts de signature et de contrôle placier.
- Given une requête sur la route publique sans jeton HMAC valide, when un utilisateur tente d'accéder au PDF, then le serveur répond par une erreur 403 Forbidden.
- Given une commande au statut non confirmé (ex. `pending_approval` ou `refunded`), when le PDF est demandé, then le serveur renvoie une erreur 400 avec un message clair.

## Implementation Notes

- Développé le service `backend/app/services/pdf_service.py` avec WeasyPrint et Jinja2, compilant l'attestation en mémoire `bytes` sans écriture sur disque.
- Créé le gabarit `backend/app/templates/pdf/attestation.html` au format standard A4 portrait (1 page), contenant toutes les mentions légales requises (Art. L310-2 et R310-8 du Code de commerce, Art. 441-7 du Code pénal), l'encart exposant pour signature manuscrite "Lu et approuvé", et le cadre de contrôle physique d'identité pour le placier Jour J.
- Exposé l'endpoint public `GET /api/v1/public/events/{slug}/orders/{order_id}/attestation.pdf` vérifiant le jeton d'accès HMAC (403 si absent/invalide) et le statut `confirmed` (400 si non confirmé).
- Exposé l'endpoint admin `GET /api/v1/events/{id_or_slug}/orders/{order_id}/attestation.pdf` vérifiant l'appartenance à l'événement et le statut `confirmed`.
- Ajouté dans `frontend/src/lib/api.ts` les helpers `getPublicAttestationPdfUrl` et `getAdminAttestationPdfUrl`.
- Connecté le bouton de téléchargement direct sur `ConfirmationPage.tsx` pour l'exposant et ajouté l'action "Attestation" dans le tableau des commandes confirmées sur `RegistrationsPage.tsx`.
- Couvert l'ensemble par 19 tests automatisés dans `backend/tests/test_pdf_service.py`, validant la génération de bytes PDF, les en-têtes HTTP, la sécurité HMAC, les statuts non confirmés et les cas limites (champs nuls, accents, multi-stands).


## Spec Change Log

## Review Triage Log

- **Blind Hunter / Edge Case Hunter / Verification Gap Reviewer** :
  - [x] Garde sur `order.access_token is None` ajoutée avant `secrets.compare_digest` (retour 403 propre).
  - [x] Ajout des dépendances `weasyprint>=62.0`, `jinja2>=3.1.4` et `stripe>=15.0.0` dans `backend/requirements.txt`.
  - [x] Ajout du champ réglementaire « Délivrée le : » dans le cadre de vérification placier (Art. R. 310-8).
  - [x] En-têtes `Cache-Control: private, no-store, must-revalidate` ajoutés sur les flux PDF.
  - [x] Tri alphanumérique naturel des stands dans `pdf_service.format_spots_summary`.
  - [x] Règles CSS anti-débordement de page (`break-inside: avoid;`) et affichage propre de la ville sans rognage.
  - [x] Test automatisé vérifiant la contrainte stricte d'1 seule page A4 (`len(doc.pages) == 1`).
  - [x] 21 tests dédiés dans `test_pdf_service.py` et 217 tests backend au vert.

