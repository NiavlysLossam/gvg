# Epic 8 Context: Ergonomie Inscriptions (Onglets & Fiche), Verrouillage Prix & Cartographie WMS

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Optimiser le quotidien de l'organisateur avec une refonte modulaire de la "Gestion des inscriptions" en onglets thématiques, une fiche d'inscription individuelle modifiable avec bloc-notes interne et réexpédition d'attestation, le verrouillage strict des prix des stands réservés, et l'intégration cartographique des flux WMS de l'IGN.

## Stories

- Story 8.1: Découpage en Onglets de la Gestion des Inscriptions (done)
- Story 8.2: Fiche Détaillée d'Inscription Modifiable & Notes Internes (done)
- Story 8.3: Verrouillage Strict des Prix des Stands Réservés (backlog)
- Story 8.4: Intégration des Flux Cartographiques WMS (IGN Géoplateforme & Saisie Libre) (backlog)

## Requirements & Constraints

- **FR-23 (Onglets Gestion Inscriptions)** : Navigation modulaire par onglets thématiques (Inscriptions, Guichet sur place, Modération & Litiges, Communications) avec synchronisation URL (`?tab=...`).
- **FR-24 (Fiche Inscription Modifiable & Notes Internes)** :
  - Consultation détaillée de l'inscription : état civil, coordonnées, stands attribués, paiements, statut modération/arbitrage, logs d'émargement/e-mails.
  - Modification des coordonnées de contact (e-mail avec validation RFC et téléphone) pour corriger les fautes de frappe des exposants.
  - Champ de texte libre "Notes & Commentaires internes" (`admin_notes`), persistant en base et strictement invisible de l'exposant.
  - Action "Renvoyer l'attestation par e-mail" permettant l'expédition immédiate de l'attestation sur l'honneur PDF à l'adresse e-mail corrigée.
- **FR-25 (Intégrité Tarifaire)** : Verrouillage strict de la modification de prix d'un stand dès lors qu'il est réservé ou rattaché à une commande active.

## Technical Decisions

- **FastAPI Backend (`orders.py`)** :
  - Endpoint `PATCH /api/v1/events/{id_or_slug}/orders/{order_id}` pour mettre à jour les coordonnées (`email`, `phone`) et le champ `admin_notes`.
  - Endpoint `POST /api/v1/events/{id_or_slug}/orders/{order_id}/resend-attestation` pour régénérer l'attestation légale PDF et l'envoyer par e-mail via `email_service` / `BackgroundTasks`.
- **Modèle de données (`Order`)** :
  - Colonne `admin_notes` (Text) déjà présente sur le modèle `Order`.
- **Frontend Organisateur** :
  - Panneau latéral (Drawer / Slide-over) ou modale complète `OrderDetailsModal` / `OrderDetailsDrawer` accessible depuis le tableau des inscriptions.
  - Validation du format e-mail côté client et gestion des états de chargement / notifications de succès.
  - Synchronisation en direct des modifications sur la liste des commandes sans rechargement complet de la page.

## UX & Interaction Patterns

- Clic sur une ligne du tableau Inscriptions ou sur un bouton d'action dédié "Voir la fiche" ouvrant le panneau latéral avec animations soignées.
- Possibilité d'éditer l'e-mail, le téléphone et les notes sans fermer le volet.
- Bouton de renvoi de l'attestation affichant un état d'envoi et un message de confirmation vert.

## Cross-Story Dependencies

- Fait suite à la Story 8.1 qui a découpé la page en 4 onglets, la fiche détaillée s'intègre directement dans le tableau de l'onglet `Inscriptions` (`RegistrationsTab.tsx`).

