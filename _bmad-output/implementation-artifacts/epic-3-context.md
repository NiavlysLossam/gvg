# Epic 3 Context: Pilotage des Inscriptions & Gestion des Remboursements

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Donner à l'organisateur (Marc) une maîtrise totale sur le suivi des ventes en ligne et hors-ligne, la saisie des règlements manuels en mairie (espèces, chèques), le filtrage et la recherche des inscrits, ainsi que le traitement humain et sécurisé des demandes d'annulation et des remboursements (unitaires ou groupés).

## Stories

- Story 3.1: Tableau de Bord Administrateur & Saisie Manuelle Hors-Ligne
- Story 3.2: Workflow de Modération Optionnelle à l'Inscription
- Story 3.3: Portail de Demande d'Annulation pour l'Exposant
- Story 3.4: Arbitrage des Remboursements & Remboursement Groupé par le Gestionnaire

## Requirements & Constraints

- **Tableau de bord des inscriptions (FR-10) :** Vue consolidée des réservations pour l'organisateur avec filtres d'état (`all`, `confirmed`, `pending`, `cancelled`, `offline`), recherche instantanée (par nom d'exposant ou numéro de stand), et jauge globale de remplissage (% de places réservées et chiffre d'affaires total cumulé).
- **Réservations manuelles hors-ligne (FR-11) :** Possibilité pour l'organisateur d'ajouter manuellement une réservation pour un exposant sans passer par Stripe (moyens de paiement : Espèces, Chèque, Autre/Gratuité). Le ou les stands associés passent immédiatement au statut `reserved` et portent la mention/tag "Hors-ligne" pour éviter toute double vente.
- **Workflow de modération optionnelle (FR-12) :** Paramètre par événement permettant la capture différée (pré-autorisation Stripe) avec validation manuelle par l'organisateur ("Accepter" $\to$ capture, "Refuser" $\to$ annulation sans débit).
- **Gestion et arbitrage des remboursements (FR-13) :**
  - Demande d'annulation initiée par l'exposant via un lien sécurisé dans son email avec motif.
  - File d'attente d'arbitrage côté administrateur avec boutons de validation (appel Stripe Refund, libération instantanée des stands en `available`, notification email) ou de refus avec motif.
  - Remboursement groupé d'urgence avec double confirmation en cas d'annulation de l'événement.
- **Authentification & Sécurité :** Toutes les routes d'administration (`/admin/*` et `/api/v1/admin/*` ou endpoints protégés) requièrent l'authentification organisateur. Les opérations financières (remboursements, saisies) sont strictement tracées.

## Technical Decisions

- **Modèles de données & Relations existantes :**
  - `Order` : contient déjà `event_id`, `guest_name`, `guest_email`, `guest_phone`, `guest_address`, `amount_cents`, `status`, `stripe_payment_intent_id`, `booking_items`.
  - Extension pour Story 3.1 : champ `payment_method` (ex: `stripe`, `cash`, `check`, `other`), note/référence interne (ex: numéro de chèque), et possibilité pour l'admin d'affecter un stand directement en `reserved`.
- **API Admin :**
  - Endpoints réservations : liste paginée/filtrable des commandes d'un événement (`GET /api/v1/events/{id}/orders`), statistiques de remplissage et CA (`GET /api/v1/events/{id}/stats` ou intégré dans l'événement), et création manuelle de commande hors-ligne (`POST /api/v1/events/{id}/orders/offline` ou `POST /api/v1/events/{id}/manual-booking`).
- **Frontend Admin :**
  - Page `/admin/events/:id/inscriptions` (ou vue dédiée dans l'espace admin) : Jauge visuelle de remplissage, cartes de KPIs (Total stands, Réservés, Taux %, CA en ligne vs hors-ligne), table réactive des inscrits avec filtres et recherche, modale/drawer d'ajout d'une réservation manuelle avec sélection de stand libre et moyen de paiement.

## UX & Interaction Patterns

- **Surface Admin Desktop-Optimized :** Interface ergonomique et claire sur grand écran, conçue pour un organisateur bénévole (Marc).
- **Jauge de remplissage :** Barre de progression visuelle ou jauge circulaire avec ratio clair (ex: "84 / 120 stands réservés — 70%").
- **Tableau des inscriptions :** Tri par date, nom, stand, montant. Badges de couleur pour les statuts (`Confirmé` vert, `Hors-ligne (Chèque)` bleu ardoise, `Hors-ligne (Espèces)` ambre, `Annulé` rouge).
- **Formulaire de réservation manuelle :** Clic sur un stand libre sur le plan ou sélection dans une liste déroulante $\to$ saisie rapide du contact $\to$ choix Espèces/Chèque $\to$ validation immédiate avec retour visuel.

## Cross-Story Dependencies

- **Story 3.1** pose les fondations du tableau de bord d'inscriptions, des statistiques de l'événement et de la gestion des commandes manuelles hors-ligne.
- **Story 3.2** s'appuiera sur ce tableau de bord pour afficher les commandes en attente de modération (`pending_approval`).
- **Story 3.3** fournira l'interface exposant pour soumettre une demande d'annulation qui alimentera la file de remboursement.
- **Story 3.4** ajoutera les actions d'arbitrage Stripe Refund et remboursement groupé sur l'interface d'administration.

