# Epic 7 Context: Portail Public, Vitrines d'Événements, Paramètres & Duplication

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Offrir une vitrine d'accueil grand public listant tous les vide-greniers publiés avec recherche par mot-clé et commune, une page de présentation vitrine dédiée par événement avec son affiche officielle (max 5 Mo) et accès direct à la billetterie, la gestion complète des paramètres généraux de l'événement pour les organisateurs, et un moteur de duplication de plan de masse permettant de reconduire l'événement l'année suivante en 1 clic.

## Stories

- Story 7.1 : Portail d'Accueil Public Multi-Événements
- Story 7.2 : Page Vitrine par Événement avec Affiche Officielle
- Story 7.3 : Édition des Paramètres Généraux & Upload d'Affiche (Max 5 Mo)
- Story 7.4 : Moteur de Duplication d'un Vide-Grenier pour l'Édition Suivante

## Requirements & Constraints

- **Portail Public Racine (`/`)** : Accès sans authentification à la liste de tous les événements au statut `published` dont la date de fin est future ou égale à la date du jour.
- **Vignettes Événements & Recherche** : Chaque carte d'événement présente son titre, dates, lieu/commune, affiche/visuel miniature, tarif indicatif, nombre de stands disponibles et un bouton d'accès vers la vitrine ou la réservation. Barre de recherche instantanée par mot-clé ou commune.
- **Page Vitrine Événement (`/events/:slug`)** : Présentation riche et responsive des détails de l'événement : visuel affiche grand format, adresse, horaires d'installation et d'ouverture publique, description, consignes/commodités, et bouton d'appel à l'action (CTA) proéminent "Consulter le plan & Réserver mes emplacements".
- **Upload d'Affiche Officielle (Max 5 Mo)** : Formats acceptés JPEG, PNG, WebP avec validation stricte de la taille (max 5 Mo) côté frontend et backend. Stockage dans le répertoire des médias et exposition sécurisée.
- **Édition des Paramètres Généraux** : Modification en temps réel par l'organisateur propriétaire (ou super-admin) des informations d'événement : titre, description, dates/horaires, tarifs de base, coordonnées.
- **Duplication d'Événement en 1 Clic** : Clonage d'un événement existant vers une nouvelle édition en statut `draft` avec titre suffixé ("- Copie"), nouveau slug unique, duplication exacte de la configuration spatiale et des stands (géométrie, numéros, allées, métrages, tarifs), sans dupliquer aucune commande, inscription, paiement ou log e-mail.

## Technical Decisions

- **Modèle de données & API Événements Publics** :
  - `GET /api/v1/public/events` : Endpoint public retournant la liste des événements publiés futurs avec calcul agrégé des stands totaux et disponibles (`total_spots`, `available_spots`).
  - `GET /api/v1/public/events/{slug}` : Endpoint public retournant la fiche détaillée de l'événement.
- **Frontend Routing & Pages** :
  - `frontend/src/pages/HomePage.tsx` : Portail public d'accueil multi-événements avec hero section, filtres de recherche et grille de cartes d'événements.
  - `frontend/src/pages/EventShowcasePage.tsx` : Vitrine publique d'un événement avec affiche grand format, détails pratiques et lien direct vers le plan de réservation (`/events/:slug/map`).
  - `frontend/src/pages/EventSettingsPage.tsx` : Console d'édition des paramètres généraux et téléversement de l'affiche officielle (max 5 Mo).
- **Moteur de Duplication (`POST /api/v1/events/{id_or_slug}/duplicate`)** :
  - Endpoint réservé au propriétaire de l'événement ou au super-admin (`check_event_ownership`).
  - Clonage en transaction DB de l'objet `Event` et de tous les `Spot` associés en réinitialisant les clés primaires `UUID`, `order_id=None`, `status="available"`, dates remises à zéro et statut de l'événement `draft`.

## Cross-Story Dependencies

- **Story 7.1** établit la page d'accueil publique (`/`) et l'endpoint API des événements publiés avec calcul des disponibilités.
- **Story 7.2** implémente la page vitrine (`/events/:slug`) vers laquelle les cartes de la Story 7.1 redirigent.
- **Story 7.3** ajoute l'interface d'édition des paramètres d'événement et le téléversement de l'affiche (champ `poster_url` ou `background_image_url`).
- **Story 7.4** s'appuie sur le modèle d'événement et les stands pour fournir l'action de clonage instantané.

