# Epic 5 Context: Conformité Réglementaire, Émargement Jour J & Déploiement

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Assurer la stricte conformité légale (Article L310-2 du Code de commerce régissant le registre des brocantes et vide-greniers), garantir un accueil fluide et sans blocage sur le terrain le matin de l'événement grâce à l'émargement physique sans connexion internet, et fournir des solutions de déploiement universelles et conteneurisées pour les associations et collectivités.

## Stories

- Story 5.1 : Génération Automatique du Formulaire d'Attestation PDF
- Story 5.2 : Export de la Feuille d'Émargement Officielle (PDF & Excel)
- Story 5.3 : Scripts de Déploiement (Docker Compose & Script Natif Ubuntu)

## Requirements & Constraints

- **Zéro upload de pièces d'identité (AD-4 / RGPD)** : La plateforme ne stocke aucun document d'identité numérique (CNI/Passeport). La conformité légale repose sur la présentation physique de la pièce originale lors de l'arrivée et la remise de l'attestation sur l'honneur signée.
- **Modèle légal conforme Art. L310-2** : L'attestation sur l'honneur au format A4 doit comporter toutes les mentions obligatoires : non-participation à plus de 2 ventes au déballage dans l'année civile, coordonnées complètes de l'exposant, stands réservés, date et lieu de l'événement, encart signature manuscrite et visa du placier/organisateur.
- **Génération PDF vectorielle WeasyPrint** : Utilisation de WeasyPrint pour compiler des templates HTML/CSS Jinja2 en documents PDF A4 haute résolution prêts pour l'impression.
- **Accès passwordless sécurisé** : L'exposant peut télécharger son attestation directement depuis la page publique de confirmation (`/e/:slug/confirmation/:orderId?token=...`) ou via le lien inclus dans les e-mails de confirmation et de rappel.
- **Tolérance aux pannes & Performance** : La génération de documents PDF doit être fluide et optimisée.

## Technical Decisions

- **Moteur PDF (`backend/app/services/pdf_service.py`)** :
  - Centralisation de la compilation WeasyPrint à partir de templates Jinja2 sous `backend/app/templates/pdf/`.
  - Template `attestation.html` : Document A4 avec mise en page soignée, mentions réglementaires, coordonnées de l'exposant et de l'événement, encarts de signature.
  - Streaming ou retour de fichier direct `Response(content=pdf_bytes, media_type="application/pdf")` avec en-tête `Content-Disposition: inline; filename="attestation-...pdf"`.
- **Endpoints de téléchargement** :
  - `GET /api/v1/public/events/{slug}/orders/{order_id}/attestation.pdf?token=...` : téléchargement direct par l'exposant avec vérification HMAC du token.
  - `GET /api/v1/events/{id_or_slug}/orders/{order_id}/attestation.pdf` : téléchargement par l'organisateur depuis le tableau de bord d'administration.
- **Frontend** :
  - Bouton "Télécharger mon attestation PDF" sur la page de confirmation exposant (`ConfirmationPage.tsx`).
  - Action "Télécharger attestation" dans le tableau de bord organisateur (`RegistrationsPage.tsx`).

## Cross-Story Dependencies

- **Story 5.1** établit l'infrastructure de génération PDF (`pdf_service.py`, dépendances WeasyPrint et gabarits Jinja2 PDF).
- **Story 5.2** s'appuiera sur cette infrastructure pour compiler la feuille d'émargement multi-pages ordonnée par stand et alphabétique, et ajoutera l'export Excel `.xlsx`.
- **Story 5.3** inclura les dépendances système de WeasyPrint (`libcairo2`, `libpango-1.0-0`, etc.) dans les conteneurs Docker et le script d'installation Ubuntu.

