# Epic 2 Context: Réservation Grand Public & Billetterie en Ligne

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Permettre aux exposantes et exposants (particuliers comme Monique) de consulter le plan interactif sur smartphone ou ordinateur, de sélectionner un ou plusieurs emplacements avec un verrouillage temporaire anti-collision de 15 minutes, et de régler en toute sécurité par carte bancaire via Stripe en mode invité (sans mot de passe).

## Stories

- Story 2.1: Consultation Interactive du Plan Public Mobile-First
- Story 2.2: Sélection Multi-Places & Verrouillage Temporaire (Hold Lock 15 min)
- Story 2.3: Formulaire Invité & Attestation sur l'Honneur
- Story 2.4: Paiement Sécurisé Stripe & Confirmation par Webhook

## Requirements & Constraints

- **Consultation publique sans authentification :** Les routes publiques `/e/:slug` et les endpoints correspondants doivent être librement accessibles sans clé d'API ni session admin.
- **Règles visuelles et charte de statut :**
  - Vert émeraude (`#10B981` / `#047857`) pour les stands disponibles (`available`).
  - Ambre (`#F59E0B` / `#B45309`) pour les stands temporairement verrouillés (`locked`).
  - Gris hachuré (`#9CA3AF` / `#374151`) pour les stands réservés (`reserved`) ou bloqués (`blocked`).
  - Indigo / Bleu vif (`#4F46E5` / `#6366F1`) pour les stands sélectionnés dans le panier en cours.
- **Ergonomie Mobile-First :** Le plan doit être parfaitement manipulable au doigt sur écran tactile (pinch-to-zoom fluide, tap réactif, bouton flottant de recentrage, infobulle d'information claire avec métrage et tarif en euros).
- **Anti-collision (Hold Lock 15 min) :** Sélection d'un stand libre enclenche un verrou atomique en base avec horodatage d'expiration `locked_until = now() + 15 min` et token de session (`session_id`). Les requêtes concurrentes sur un stand verrouillé reçoivent une alerte explicite sans écraser la sélection.
- **Paiement Stripe sécurisé :** Stripe Elements pour la saisie bancaire, le webhook `payment_intent.succeeded` étant la source unique de vérité financière pour la conversion en `reserved`.
- **Zéro stockage de documents d'identité :** Seule une attestation sur l'honneur à cocher obligatoire est requise (art. L310-2 du Code de commerce), aucun téléversement de CNI.

## Technical Decisions

- **Modèle de données & Statuts :**
  - Entité `Spot` : `status` enum (`available`, `locked`, `reserved`, `blocked`), `locked_until: datetime`, `session_token: str | None`.
  - Entité `Order` : créée lors de la réservation avec référence Stripe `payment_intent_id`, montant `amount_cents`, statut (`pending`, `confirmed`, `cancelled`).
  - Expiration de verrou : requête SQL ou validation paresseuse vérifiant `locked_until < now()` pour traiter automatiquement les verrous expirés comme `available`.
- **API Publique :**
  - `GET /api/v1/public/events/{slug}` : Récupération des détails publics de l'événement (titre, dates, adresse, fond de plan, coordonnées de cadrage).
  - `GET /api/v1/public/events/{slug}/spots` : Récupération de la `FeatureCollection` GeoJSON avec statuts temps réel et prix.
- **Gestion des sessions exposant :** Génération d'un `session_id` persistant dans `localStorage` côté client pour associer les verrous et le panier.

## UX & Interaction Patterns

- **Affichage Mobile Dédié :** Interface responsive pleine page, suppression des barres d'outils d'édition admin, accent mis sur la lisibilité des numéros et des disponibilités.
- **Infobulle & Tiroir Panier (Cart Drawer) :** Tap sur un stand affiche sa fiche (numéro, dimension, tarif). Bandeau rétractable en bas d'écran avec total en mètres et en euros et décompte dynamique du verrou 15 min.
- **Bouton de recentrage :** Accès rapide en 1 tap pour réaligner le zoom sur l'ensemble de l'événement.

## Cross-Story Dependencies

- **Story 2.1** fournit la vue cartographique publique mobile-first et les endpoints de lecture publique pour les stands et l'événement.
- **Story 2.2** s'appuie sur la carte publique pour ajouter la sélection interactive, le verrouillage 15 min et le panier.
- **Story 2.3** ajoute le formulaire de contact sans mot de passe déclenché depuis le panier.
- **Story 2.4** finalise la commande via Stripe Elements et le webhook serveur.

