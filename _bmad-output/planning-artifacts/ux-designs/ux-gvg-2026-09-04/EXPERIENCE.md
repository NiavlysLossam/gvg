---
name: GVG (Gestion de Vide-Greniers)
status: draft
sources:
  - _bmad-output/planning-artifacts/prds/prd-gvg-2026-09-04/prd.md
updated: 2026-09-04
---

# GVG — Spécifications d'Expérience Utilisateur (EXPERIENCE.md)

## Foundation

GVG est une application web responsive moderne conçue avec une double posture ergonomique :
1. **Côté Exposant (Grand Public / Monique)** : Expérience **Mobile-First absolue**. L'exposant accède au site depuis un lien Facebook ou un QR Code sur une affiche. L'interface est simplifiée au maximum : consultation du plan tactile, sélection des places, checkout invité sans mot de passe et paiement Stripe en 3 écrans.
2. **Côté Organisateur (Gestionnaire / Marc)** : Expérience **Desktop-Optimized**. Marc conçoit son plan interactif avec le confort d'un grand écran (glisser-déposer de rectangles, numérotation automatique, vue tabulaire des inscriptions et exports papier).

---

## Architecture de l'Information (IA)

### 1. Surfaces Exposant (Publiques & Mobiles)

| Surface | URL / Accès | Rôle & Contenu |
|---|---|---|
| **Vue Événement & Plan** | `/e/:slug` | Présentation de l'événement (date, lieu, horaires, règlement), plan interactif avec stands disponibles/occupés, légende et tiroir de panier flottant. |
| **Tunnel de Réservation** | `/e/:slug/reservation` | Saisie des coordonnées (parcours invité sans mot de passe), attestation sur l'honneur à cocher, paiement sécurisé Stripe Elements avec timer de verrouillage actif (15 min). |
| **Confirmation de Commande** | `/e/:slug/confirmation/:orderId` | Écran de succès : récapitulatif des stands réservés, téléchargement immédiat de l'attestation PDF pré-remplie, bouton d'ajout au calendrier et lien *"Demander une annulation"*. |
| **Portail d'Annulation** | `/e/:slug/annulation/:orderId` | Page dédiée permettant à l'exposant de solliciter un remboursement auprès du gestionnaire en choisissant un motif et un commentaire. |

### 2. Surfaces Organisateur (Espace Admin)

| Surface | URL / Accès | Rôle & Contenu |
|---|---|---|
| **Tableau de bord Événements** | `/admin` | Liste des vide-greniers organisés par l'association, jauge globale de remplissage et bouton de création d'événement. |
| **Éditeur de Plan Interactif** | `/admin/e/:id/plan` | Espace de dessin du plan : sélection fond satellite ou upload image, palette d'outils (rectangle, carré, duplication, alignement, numérotation auto). |
| **Gestion des Réservations** | `/admin/e/:id/inscriptions` | Tableau de bord des inscrits : recherche par stand/nom, bouton *"Ajouter une réservation manuelle (chèque/espèces)"*, boutons d'export de la feuille d'émargement PDF/Excel. |
| **File des Remboursements** | `/admin/e/:id/remboursements` | Liste des demandes d'annulation en attente d'arbitrage par le gestionnaire : boutons *"Valider le remboursement"* (Stripe instantané) ou *"Refuser"*. |
| **Module E-mailing** | `/admin/e/:id/emails` | Éditeur d'emails de masse avec tags dynamiques (`{{exposant.prenom}}`, `{{commande.emplacements}}`) et historique des envois. |

---

## Voix & Micro-copies (Voice & Tone)

Le ton est chaleureux, bienveillant et direct. On évite le vocabulaire administratif froid au profit de formules simples qui rassurent.

| Contexte | À privilégier (Do) | À éviter (Don't) |
|---|---|---|
| **Sélection stand** | *"Stand A12 sélectionné (2m) — 8,00 €"* | *"Entité spatiale ID_42 ajoutée au panier."* |
| **Verrouillage panier** | *"Cette place vous est réservée pendant 15 minutes, le temps de finaliser."* | *"Session lock timeout initialized: 900s."* |
| **Attestation légale** | *"Je certifie sur l'honneur participer à moins de 2 vide-greniers par an (obligation légale)."* | *"Engagement contractuel art. L310-2 du Code de commerce sous peine de sanctions pénales."* |
| **Confirmation** | *"Bravo Monique, votre stand est réservé ! Pensez à imprimer votre attestation pour dimanche."* | *"Transaction validée avec succès. Référence commande #98453."* |
| **Annulation demandée** | *"Votre demande d'annulation a bien été envoyée à Marc. Vous recevrez un email dès sa validation."* | *"Requête enregistrée en statut pending_review."* |

---

## Modèles d'Interactions & Gestuelle (Interaction Primitives)

### 1. Sur le Plan Interactif Mobile (Monique)
- **Pinch-to-zoom & Pan** : Navigation fluide à deux doigts pour zoomer sur une rue ou une allée spécifique.
- **Tap unique** : Sélectionne un stand libre. S'il est vert, il devient bleu et une micro-fiche apparaît en bas : *"Stand A12 • 2m • 8 € • Ajouter"*.
- **Tap sur stand déjà réservé (gris)** : Affiche une infobulle discrète *"Déjà réservé"*.
- **Recentrage automatique** : Un bouton flottant flottant *"Recentrer le plan"* remet la vue d'ensemble à l'échelle de l'écran.

### 2. Sur l'Éditeur de Plan Desktop (Marc)
- **Dessin direct en glisser-déposer** : Marc clique sur l'outil "Rectangle", clique-glisse sur le fond de carte pour matérialiser l'emplacement.
- **Outil Rangée / Duplication rapide** : Marc sélectionne un stand de 2m et clique sur *"Dupliquer × 10"* : 10 stands s'alignent automatiquement le long de l'axe choisi.
- **Numérotation intelligente en 1 clic** : Marc trace une boîte de sélection englobant 20 stands, indique préfixe `A-` et début `1` : les stands sont numérotés de `A-01` à `A-20` dans l'ordre du tracé.
- **Magnétisme d'alignement (Snap-to-Grid)** : Guide magnétique automatique pour coller les stands bord à bord proprement sans trou de métrage.

---

## Modèles d'États (State Patterns)

| État | Surface | Comportement & Retour Utilisateur |
|---|---|---|
| **Collision au clic (Stand pris à la seconde près)** | Plan public | Notification toast immédiate : *"Oups, ce stand vient d'être sélectionné par un autre visiteur. Veuillez en choisir un autre."* Le stand passe immédiatement en ambre sur le plan. |
| **Expiration du verrou 15 min** | Tunnel de réservation | Modal courtois : *"Votre temps de réservation de 15 minutes est écoulé. Les places ont été libérées. Souhaitez-vous les sélectionner à nouveau ?"* |
| **Chargement du plan** | Page événement | Affichage d'un squelette doux (skeleton loader) avec mention *"Chargement du plan du vide-grenier..."* (< 1 seconde). |
| **Paiement Stripe en cours** | Checkout | Bouton en état de chargement désactivé avec spinner : *"Validation sécurisée en cours..."* pour empêcher tout double clic. |
| **Demande de remboursement reçue** | Dashboard organisateur | Pastille badge rouge sur l'onglet *"Remboursements"* avec compteur `(1)`. Ligne mise en avant avec motif et montant. |

---

## Socle d'Accessibilité (Accessibility Floor)

- **Contraste des textes** : Conforme aux critères WCAG 2.1 AA (ratio minimal de 4.5:1 pour le texte courant, 3:1 pour les grands titres).
- **Indicateurs visuels non basés uniquement sur la couleur** : Pour les personnes daltoniennes, les stands ne sont pas uniquement différenciés par le vert/rouge/ambre :
  - Stand disponible : Contour continu vert vif + icône discrète ou label lisible.
  - Stand réservé : Grisé avec motif de hachures diagonales.
  - Stand sélectionné : Contour épais bleu avec coche blanche `✓`.
- **Navigation clavier complète sur l'espace exposant** : Les personnes naviguant au clavier peuvent passer d'un champ de formulaire au bouton de paiement via la touche `Tab` sans piège de focus.
- **Support des lecteurs d'écran** : Attributs `aria-label="Emplacement A12, 2 mètres, disponible pour 8 euros"` sur chaque polygone interactif du plan SVG/Canvas.

---

## Parcours Utilisateurs Détaillés (Key Flows)

### Flow 1 : Réservation mobile de Monique (Exposante)
1. **Écran 1 (Découverte & Plan)** : Monique ouvre le lien sur son smartphone. Elle zoome sur la place de l'église, repère le stand A12 près d'un arbre. Elle tape dessus. Le stand devient bleu. Le bandeau inférieur affiche : *"1 stand sélectionné (2m) • 8,00 €"*. Elle clique sur *"Réserver ma place"*.
2. **Écran 2 (Coordonnées & Déclaration)** : Un timer discret indique *"Réservé pendant 14:59"*. Monique saisit son nom, prénom, email, téléphone et adresse. Elle coche la case attestant sur l'honneur être un particulier.
3. **Écran 3 (Paiement)** : Le composant Stripe apparaît (saisie du numéro de carte ou bouton Apple Pay en un clic). Monique valide son paiement de 8,00 €.
4. **Écran 4 (Succès)** : *"Merci Monique ! Votre place A12 est validée."* Un bouton vert proéminent propose : *"Télécharger mon attestation à signer (PDF)"*. Monique reçoit simultanément son email de confirmation.

### Flow 2 : Création de plan par Marc (Organisateur)
1. **Écran 1 (Création)** : Marc nomme son événement, fixe la date et le tarif (ex: 4 € / mètre).
2. **Écran 2 (Éditeur)** : Marc tape l'adresse communale. La vue satellite s'affiche. Marc active l'outil rectangle, trace la rangée d'arbres et aligne 30 stands de 2m. Il lance la numérotation automatique : la rangée devient `A01` à `A30`. Il clique sur *"Sauvegarder et Publier"*.

### Flow 3 : Traitement d'une demande de remboursement par Marc
1. Marc reçoit une notification email : *"Monique a demandé l'annulation de sa réservation A12"*.
2. Marc se connecte à GVG et ouvre l'onglet *"Remboursements en attente"*.
3. Il lit le motif : *"Empêchement de santé"*. Il reste 12 jours avant l'événement.
4. Marc clique sur **"Valider le remboursement"**.
5. Une modale confirme : *"Rembourser 8,00 € via Stripe et libérer le stand A12 sur le plan public ?"* -> Marc clique sur Confirmer.
6. Le remboursement est initié immédiatement. Le stand A12 redevient vert sur le plan en direct.
