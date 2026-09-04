---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-gvg-2026-09-04/prd.md
  - _bmad-output/planning-artifacts/architecture/architecture-gvg-2026-09-04/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/ux-designs/ux-gvg-2026-09-04/DESIGN.md
  - _bmad-output/planning-artifacts/ux-designs/ux-gvg-2026-09-04/EXPERIENCE.md
---

# GVG (Gestion de Vide-Greniers) - Epic Breakdown

## Overview

Ce document définit le découpage complet en Épics et User Stories pour **GVG (Gestion de Vide-Greniers)**, en transformant les exigences fonctionnelles et non-fonctionnelles du PRD, les décisions d'architecture (FastAPI, PostGIS, Leaflet, Stripe) et les spécifications UX en unités de développement concrètes, indépendantes et testables.

---

## Requirements Inventory

### Functional Requirements

- **FR-1**: Création et configuration d'un événement (Titre, description, dates, horaires d'installation vs public, adresse, règlement, tarif unitaire au mètre linéaire).
- **FR-2**: Import et calibrage du fond de plan (tuiles OpenStreetMap/satellite ou import d'un fichier image personnalisé PNG/JPEG de salle ou gymnase).
- **FR-3**: Outil de dessin vectoriel des emplacements (rectangles ou carrés sur le fond de plan avec métrage linéaire, déplacement, rotation et duplication).
- **FR-4**: Numérotation automatique intelligente des stands (sélection par bloc, préfixe d'allée et incrémentation séquentielle avec garantie d'unicité).
- **FR-5**: Consultation interactive du plan public (rendu Leaflet temps réel avec statuts de stands : Disponible, Verrouillé, Réservé, et infobulles détaillées).
- **FR-6**: Verrouillage temporaire anti-collision (Hold Lock de 15 minutes dès l'ajout au panier, libération automatique si expiration sans paiement).
- **FR-7**: Réservation multi-emplacements dans un même panier (contigus ou non).
- **FR-8**: Parcours de commande invité sans mot de passe (Nom, prénom, email, téléphone, adresse postale et attestation sur l'honneur particulière obligatoire).
- **FR-9**: Paiement sécurisé en ligne via Stripe Elements (confirmation transactionnelle par webhook Stripe).
- **FR-10**: Tableau de bord des inscriptions (vue consolidée des commandes avec filtres, recherche instantanée et export CSV/Excel).
- **FR-11**: Saisie manuelle de réservations hors-ligne (chèques, espèces) avec retrait immédiat des stands de la disponibilité publique.
- **FR-12**: Workflow de modération optionnelle (pré-autorisation bancaire et capture différée après validation de l'organisateur).
- **FR-13**: Workflow de demande et validation des remboursements (demande exposant avec motif, arbitrage manuel obligatoire par le gestionnaire, et remboursement groupé en cas d'annulation de l'événement).
- **FR-14**: E-mails transactionnels automatisés (confirmation avec attestation PDF, notifications de statut de remboursement, rappels programmés à J-7 et J-2).
- **FR-15**: E-mails manuels de masse (campagnes d'information et alertes météo avec file d'attente asynchrone).
- **FR-16**: Variables de personnalisation dynamiques dans les emails (`{{exposant.prenom}}`, `{{commande.emplacements}}`, etc.).
- **FR-17**: Génération automatique du formulaire d'attestation légale pré-rempli au format PDF (pour contrôle physique sur place le Jour J).
- **FR-18**: Export de la feuille d'émargement officielle le Jour J (formats PDF et Excel, tri par allée ou nom d'exposant).

### NonFunctional Requirements

- **NFR-1 (Concurrence & Temps Réel)** : Zéro double réservation sous charge concurrente d'inscriptions, actualisation de l'état du plan < 1s.
- **NFR-2 (Ergonomie & Responsive Web)** : Approche strictement Mobile-First pour le tunnel exposant, score Google Lighthouse Mobile >= 90.
- **NFR-3 (Sécurité & RGPD)** : Zéro stockage de pièces d'identité scannées sur serveur, données exposants chiffrées, conformité bancaire PCI-DSS via Stripe.
- **NFR-4 (Architecture Open-Source & Déploiement)** : Déploiement conteneurisé Docker Compose ET script d'installation natif pour Ubuntu 22.04 / 24.04 LTS.

### Additional Requirements (Architecture)

- **ARCH-1**: Backend en Python 3.12 avec FastAPI, Pydantic v2 et ORM SQLAlchemy 2.0 + GeoAlchemy2.
- **ARCH-2**: Base de données PostgreSQL 16 avec extension PostGIS 3.4 (`geometry(Polygon, 4326)` et coordonnées planaires).
- **ARCH-3**: Frontend en React (Vite) + Leaflet 1.9 + plugin `@geoman-io/leaflet-geoman-free` pour le dessin vectoriel.
- **ARCH-4**: API GeoJSON RFC 7946 native (`SELECT ST_AsGeoJSON(geom)`).
- **ARCH-5**: Verrouillage atomique 15 min via requête SQL `UPDATE spots SET locked_until = NOW() + 15 min ... RETURNING id` (sans Redis).
- **ARCH-6**: Webhooks Stripe cryptographiquement vérifiés comme unique source de vérité financière.
- **ARCH-7**: Authentification exposant sans mot de passe via tokens signés HMAC (Magic Tokens dans l'email).
- **ARCH-8**: Moteur PDF WeasyPrint exécuté en tâche de fond asynchrone (`FastAPI BackgroundTasks`).
- **ARCH-9**: Double packaging officiel : `docker-compose.yml` (multi-conteneur) ET `scripts/install-ubuntu.sh` (natif avec systemd et Nginx).

### UX Design Requirements

- **UX-DR1**: Palette de couleurs sémantique des stands (Vert `#10B981`, Bleu `#2563EB`, Ambre `#F59E0B`, Gris `#9CA3AF`) avec motifs hachurés pour accessibilité daltonienne.
- **UX-DR2**: Navigation tactile mobile fluide sur le plan (pinch-to-zoom, pan, tap unique de sélection avec micro-vibration haptique, bouton flottant de recentrage).
- **UX-DR3**: Tiroir de panier mobile rétractable (Cart Drawer) affichant le nombre de stands, le métrage cumulé et le tarif total.
- **UX-DR4**: Compteur de verrouillage temporaire (Hold Timer) affiché sous forme de pill flottante avec compte à rebours `14:59` et alerte visuelle à < 2 min.
- **UX-DR5**: Éditeur de plan desktop avec palette Geoman (dessin rectangle, rotation, poignées de redimensionnement, duplication rapide × 10 et magnétisme Snap-to-Grid).
- **UX-DR6**: Numérotation automatique séquentielle en 1 clic par sélection d'un bloc de stands.
- **UX-DR7**: Portail dédié de demande d'annulation exposant accessible par lien direct sans mot de passe.
- **UX-DR8**: Interface administrateur pour l'arbitrage des remboursements en 1 clic avec motif de rejet optionnel.

---

### FR Coverage Map

| Exigence | Épic assignée | Description & Portée |
|---|---|---|
| **FR-1** | **Epic 1** | Création et configuration d'un événement |
| **FR-2** | **Epic 1** | Fond de plan (satellite / image de salle) |
| **FR-3** | **Epic 1** | Outil de dessin vectoriel de stands |
| **FR-4** | **Epic 1** | Numérotation automatique intelligente |
| **FR-5** | **Epic 2** | Consultation interactive du plan public |
| **FR-6** | **Epic 2** | Verrouillage temporaire anti-collision (15 min) |
| **FR-7** | **Epic 2** | Réservation multi-emplacements |
| **FR-8** | **Epic 2** | Commande invitée sans mot de passe |
| **FR-9** | **Epic 2** | Paiement sécurisé en ligne Stripe |
| **FR-10** | **Epic 3** | Tableau de bord des réservations |
| **FR-11** | **Epic 3** | Réservations manuelles hors-ligne (chèque/espèces) |
| **FR-12** | **Epic 3** | Workflow de modération optionnelle |
| **FR-13** | **Epic 3** | Workflow de validation des remboursements |
| **FR-14** | **Epic 4** | E-mails transactionnels automatisés |
| **FR-15** | **Epic 4** | E-mails manuels de masse (broadcast) |
| **FR-16** | **Epic 4** | Variables dynamiques de personnalisation |
| **FR-17** | **Epic 5** | Attestation sur l'honneur PDF pré-remplie |
| **FR-18** | **Epic 5** | Feuille d'émargement officielle Jour J (PDF/Excel) |

---

## Epic List

### Epic 1 : Configuration d'Événement & Éditeur de Plan Interactif
Permettre à l'organisateur (Marc) de créer son événement, d'importer son fond de plan (satellite OpenStreetMap ou schéma de salle) et de concevoir son plan de masse avec tracé de stands et numérotation automatique.
**FRs couvertes :** FR-1, FR-2, FR-3, FR-4

### Epic 2 : Réservation Grand Public & Billetterie en Ligne
Permettre à l'exposante (Monique) de consulter le plan interactif sur smartphone, de sélectionner ses emplacements avec verrou temporaire anti-collision (15 min), et de régler par carte bancaire via Stripe sans créer de compte.
**FRs couvertes :** FR-5, FR-6, FR-7, FR-8, FR-9

### Epic 3 : Pilotage des Inscriptions & Gestion des Remboursements
Permettre à l'organisateur de suivre les réservations, d'enregistrer des paiements hors-ligne (chèques/espèces), d'activer la modération optionnelle, et d'arbitrer les demandes d'annulation avec déclenchement des remboursements Stripe (unitaire ou groupé).
**FRs couvertes :** FR-10, FR-11, FR-12, FR-13

### Epic 4 : Module de Communication & E-mailing
Automatiser les communications clés (emails de confirmation de commande, suivi des remboursements, rappels à J-7 et J-2 avec consignes) et permettre l'envoi d'annonces de masse personnalisées avec variables dynamiques.
**FRs couvertes :** FR-14, FR-15, FR-16

### Epic 5 : Conformité Réglementaire, Émargement Jour J & Déploiement
Fournir l'attestation légale pré-remplie en PDF (Art. L310-2), générer la feuille d'émargement officielle pour le pointage terrain à 6h du matin (PDF/Excel), et fournir les scripts de déploiement (Docker Compose et script natif Ubuntu).
**FRs couvertes :** FR-17, FR-18

---

## Epic 1 : Configuration d'Événement & Éditeur de Plan Interactif

**Objectif :** Fournir à l'organisateur une interface ergonomique pour déclarer les métadonnées de son vide-grenier, configurer la zone géographique ou la salle, et dessiner/numéroter avec précision les emplacements de vente.

### Story 1.1 : Initialisation du projet & Création d'Événement
En tant qu'**organisateur (Marc)**,  
Je veux **créer un événement en renseignant son nom, ses dates, son adresse, ses horaires et son tarif au mètre linéaire**,  
Afin que **mon vide-grenier soit enregistré en base et prêt à être cartographié**.

**Acceptance Criteria:**
- **Given** Marc accède à l'interface d'administration de GVG,
- **When** il saisit le titre, la description, les dates de début/fin, les horaires (installation 6h-8h / public 8h-18h), l'adresse et le tarif au mètre (ex: 4,00 €),
- **Then** l'API FastAPI persiste l'événement dans la table `events` de PostgreSQL avec un identifiant UUID unique et un slug d'URL public,
- **And** l'événement apparaît dans le tableau de bord avec le statut "Brouillon / Configuration du plan".

### Story 1.2 : Calibrage du Fond de Plan (Satellite OSM ou Image de Salle)
En tant qu'**organisateur (Marc)**,  
Je veux **choisir entre une vue satellite OpenStreetMap géoréférencée ou téléverser un fichier image (schéma de salle des fêtes)**,  
Afin d'**avoir le support visuel exact sur lequel tracer mes allées et stands**.

**Acceptance Criteria:**
- **Given** un événement existant sans plan configuré,
- **When** Marc choisit "Vue Aérienne / Satellite" et tape une adresse communale,
- **Then** le composant Leaflet centre la vue cartographique en projection Web Mercator standard,
- **When** Marc choisit "Plan de Salle / Intérieur" et téléverse une image PNG/JPEG,
- **Then** l'image est enregistrée sur le serveur et affichée dans Leaflet via le mode plan `L.CRS.Simple` avec zoom et panoramique fluides.

### Story 1.3 : Dessin Vectoriel des Emplacements avec Leaflet-Geoman
En tant qu'**organisateur (Marc)**,  
Je veux **dessiner des rectangles d'emplacements sur la carte, les déplacer, les faire pivoter et spécifier leur métrage linéaire**,  
Afin de **matérialiser visuellement chaque stand disponible**.

**Acceptance Criteria:**
- **Given** le fond de plan affiché dans l'éditeur,
- **When** Marc active l'outil rectangle de Leaflet-Geoman et clique-glisse sur la carte,
- **Then** un polygone s'affiche avec des poignées de redimensionnement et de rotation,
- **And** une boîte de propriétés permet d'indiquer le métrage (ex: 2m, 3m) et calcule automatiquement le prix associé (`métrage × tarif_au_mètre`),
- **And** la géométrie est sauvegardée dans PostGIS via l'API en format GeoJSON `Polygon`.

### Story 1.4 : Duplication Rapide, Snap-to-Grid & Numérotation Automatique
En tant qu'**organisateur (Marc)**,  
Je veux **dupliquer des rangées de stands avec alignement magnétique et générer automatiquement leur numérotation séquentielle**,  
Afin de **configurer des allées entières de 30 stands en quelques clics sans risque d'erreur humaine**.

**Acceptance Criteria:**
- **Given** un stand de 2m sélectionné sur le plan,
- **When** Marc clique sur "Dupliquer × N" en indiquant une direction,
- **Then** les N stands sont créés et magnétiquement alignés bord à bord (Snap-to-Grid),
- **When** Marc sélectionne un groupe de stands et indique le préfixe "Allée A - " et le départ "1",
- **Then** le système affecte séquentiellement les labels `Allée A - 01`, `Allée A - 02`, etc.,
- **And** l'unicité des numéros d'emplacements au sein de l'événement est strictement garantie par une contrainte d'unicité SQL.

---

## Epic 2 : Réservation Grand Public & Billetterie en Ligne

**Objectif :** Permettre aux particuliers de consulter le plan public en temps réel, de réserver un ou plusieurs emplacements avec garantie anti-collision, et de payer en toute sécurité sans création de mot de passe.

### Story 2.1 : Consultation Interactive du Plan Public Mobile-First
En tant qu'**exposante (Monique)**,  
Je veux **consulter le plan interactif sur mon smartphone avec une légende de couleurs claire et une gestuelle tactile fluide**,  
Afin de **repérer facilement les emplacements libres et leurs tarifs**.

**Acceptance Criteria:**
- **Given** Monique ouvre l'URL publique `/e/:slug` sur son smartphone,
- **When** la carte Leaflet se charge,
- **Then** les stands disponibles s'affichent en vert émeraude (`#10B981`), les réservés en gris hachuré (`#9CA3AF`) et les verrouillés en ambre (`#F59E0B`),
- **And** le pinch-to-zoom tactile à deux doigts est fluide et un bouton flottant permet de recentrer la vue en 1 tap,
- **And** un tap sur un stand vert affiche une infobulle : numéro, métrage linéaire et prix en euros.

### Story 2.2 : Sélection Multi-Places & Verrouillage Temporaire (Hold Lock 15 min)
En tant qu'**exposante (Monique)**,  
Je veux **sélectionner une ou plusieurs places et bénéficier d'un verrou temporaire de 15 minutes**,  
Afin que **personne d'autre ne puisse acheter mes places le temps que je finalise ma commande**.

**Acceptance Criteria:**
- **Given** Monique tape sur le stand A12 puis sur le stand A13,
- **When** les stands passent en bleu de sélection,
- **Then** une requête atomique PostgreSQL verrouille les stands pour 15 minutes au profit du token de session de Monique,
- **And** un bandeau panier rétractable (Cart Drawer) s'affiche en bas d'écran : "2 stands (4m) • 16,00 €",
- **And** un compteur dynamique (Hold Timer) affiche le décompte "14:59 restant",
- **And** si un autre visiteur clique sur A12 pendant ce temps, une notification toast indique "Ce stand est en cours de commande par un autre visiteur".

### Story 2.3 : Formulaire Invité & Attestation sur l'Honneur
En tant qu'**exposante (Monique)**,  
Je veux **saisir mes coordonnées et valider l'attestation sur l'honneur sans avoir à créer de compte avec mot de passe**,  
Afin de **finaliser mon inscription en moins de 2 minutes sans friction technique**.

**Acceptance Criteria:**
- **Given** Monique clique sur "Finaliser ma réservation" depuis son panier,
- **When** le formulaire s'affiche,
- **Then** seuls les champs essentiels sont demandés : Nom, Prénom, Email, Téléphone portable, Adresse postale,
- **And** une case à cocher obligatoire stipule : "Je certifie sur l'honneur être un particulier et ne pas participer à plus de 2 ventes au déballage dans l'année (art. L310-2 du Code de commerce)",
- **And** le système ne demande aucun mot de passe ni téléversement de scan de pièce d'identité.

### Story 2.4 : Paiement Sécurisé Stripe & Confirmation par Webhook
En tant qu'**exposante (Monique)**,  
Je veux **régler ma commande par carte bancaire ou Apple Pay via un composant bancaire sécurisé**,  
Afin d'**obtenir immédiatement ma confirmation de réservation**.

**Acceptance Criteria:**
- **Given** le formulaire validé avec le verrou de 15 minutes actif,
- **When** Monique renseigne ses coordonnées bancaires dans Stripe Elements et valide le paiement,
- **Then** le webhook Stripe `payment_intent.succeeded` reçu par FastAPI convertit la commande en statut `confirmed` et les stands en statut `reserved`,
- **And** Monique est redirigée vers l'écran de succès affichant son numéro de réservation, ses emplacements et un bouton de téléchargement de l'attestation légale.

---

## Epic 3 : Pilotage des Inscriptions & Gestion des Remboursements

**Objectif :** Donner à l'organisateur une maîtrise totale sur le suivi des ventes, la saisie des règlements hors-ligne, et le traitement humain des demandes d'annulation et remboursements.

### Story 3.1 : Tableau de Bord Administrateur & Saisie Manuelle Hors-Ligne
En tant qu'**organisateur (Marc)**,  
Je veux **visualiser toutes les réservations dans un tableau de bord et enregistrer manuellement des paiements par chèque ou espèces**,  
Afin d'**intégrer les exposants venus déposer leur règlement en mairie et bloquer leurs stands sur le plan**.

**Acceptance Criteria:**
- **Given** Marc connecté sur son espace administrateur,
- **When** il consulte le tableau de bord de l'événement,
- **Then** il visualise le taux de remplissage (ex: 84/120 stands), le chiffre d'affaires cumulé, et la liste triable des inscrits,
- **When** Marc clique sur un stand libre et choisit "Ajouter une réservation manuelle",
- **Then** il saisit l'identité de l'exposant et sélectionne le moyen "Chèque" ou "Espèces",
- **And** le stand passe instantanément au statut `reserved` avec le tag "Hors-ligne" sur la carte publique.

### Story 3.2 : Workflow de Modération Optionnelle à l'Inscription
En tant qu'**organisateur (Marc)**,  
Je veux **pouvoir activer un mode de validation manuelle pour mon événement**,  
Afin d'**examiner chaque demande avant d'autoriser l'encaissement effectif des fonds**.

**Acceptance Criteria:**
- **Given** l'option "Validation manuelle requise" cochée dans les paramètres de l'événement,
- **When** un exposant paie en ligne,
- **Then** Stripe effectue une pré-autorisation bancaire (capture différée) et la commande est marquée `pending_approval`,
- **When** Marc clique sur "Accepter", la capture Stripe est déclenchée et la commande est confirmée,
- **When** Marc clique sur "Refuser", la pré-autorisation est annulée sans débit et le stand est libéré sur le plan.

### Story 3.3 : Portail de Demande d'Annulation pour l'Exposant
En tant qu'**exposante (Monique)**,  
Je veux **accéder à un formulaire d'annulation via un lien sécurisé dans mon email et indiquer mon motif d'empêchement**,  
Afin de **demander un remboursement à l'organisateur sans démarche téléphonique compliquée**.

**Acceptance Criteria:**
- **Given** Monique clique sur le lien "Demander une annulation" dans son email de confirmation,
- **When** la page s'ouvre avec son token d'accès signé,
- **Then** elle peut choisir un motif (ex: "Empêchement médical", "Imprévu personnel", "Autre") et ajouter un commentaire facultatif,
- **When** elle valide, la commande passe à l'état `cancellation_requested`,
- **And** un message confirme que sa demande a bien été transmise à l'organisateur pour arbitrage.

### Story 3.4 : Arbitrage des Remboursements & Remboursement Groupé par le Gestionnaire
En tant qu'**organisateur principal (Marc / Gestionnaire)**,  
Je veux **examiner la file d'attente des demandes de remboursement pour valider ou rejeter chaque dossier, ou lancer un remboursement général en cas d'annulation de l'événement**,  
Afin de **maîtriser les sorties de trésorerie et la libération des stands sur le plan**.

**Acceptance Criteria:**
- **Given** une pastille rouge sur l'onglet "Remboursements" indiquant des demandes en attente,
- **When** Marc clique sur "Valider le remboursement" sur le dossier de Monique,
- **Then** l'API Stripe Refund est appelée, la commande passe en `refunded`, et les stands A12/A13 redeviennent instantanément verts (disponibles) sur le plan public,
- **When** Marc clique sur "Refuser" et saisit un motif (ex: "Délai de prévenance dépassé"), la commande reste active et Monique est notifiée par email,
- **When** en cas d'intempérie majeure, Marc clique sur "Annuler l'événement & Rembourser tous les inscrits",
- **Then** une modale avec double confirmation sécurisée déclenche le remboursement automatique de l'ensemble des commandes Stripe de l'événement.

---

## Epic 4 : Module de Communication & E-mailing

**Objectif :** Automatiser la transmission des informations clés par email et offrir un canal d'annonces groupées personnalisées pour l'organisateur.

### Story 4.1 : E-mails Transactionnels Automatisés (Confirmation & Remboursements)
En tant qu'**exposante (Monique)**,  
Je veux **recevoir des emails automatiques confirmant ma commande, mon récapitulatif et le suivi de mon remboursement**,  
Afin de **garder une trace écrite claire de ma réservation et de ses évolutions**.

**Acceptance Criteria:**
- **Given** une commande confirmée par carte bancaire,
- **When** la transaction est validée,
- **Then** un email HTML élégant est envoyé à Monique avec le récapitulatif de ses stands, ses horaires d'accès, le lien vers son attestation PDF et son lien de demande d'annulation,
- **When** sa demande d'annulation est validée ou refusée par Marc,
- **Then** un email de notification est envoyé immédiatement avec le statut et le motif éventuel.

### Story 4.2 : Rappels Automatiques Programmés J-7 et J-2
En tant qu'**exposante (Monique)**,  
Je veux **recevoir un rappel automatique 7 jours puis 2 jours avant l'événement avec les consignes d'arrivée**,  
Afin de **ne rien oublier pour le jour de la brocante (pièce d'identité, horaires d'installation, accès)**.

**Acceptance Criteria:**
- **Given** un événement programmé,
- **When** l'échéance J-7 puis J-2 est atteinte,
- **Then** le système exécute une tâche planifiée qui envoie à tous les exposants confirmés un email de rappel contenant l'itinéraire d'accès, les horaires d'ouverture des barrières et le rappel d'apporter l'attestation signée et la pièce d'identité originale.

### Story 4.3 : Envoi Manuel d'E-mails Groupés avec Variables Dynamiques
En tant qu'**organisateur (Marc)**,  
Je veux **rédiger un message et l'envoyer à l'ensemble de mes inscrits en insérant des tags de personnalisation**,  
Afin de **diffuser une consigne météo ou un changement d'accès de dernière minute**.

**Acceptance Criteria:**
- **Given** Marc sur la page "Communication" de son événement,
- **When** il rédige un email et insère les tags `{{exposant.prenom}}` et `{{commande.emplacements}}`,
- **Then** un aperçu en direct montre le rendu avec un exemple d'exposant,
- **When** Marc clique sur "Envoyer aux 84 inscrits",
- **Then** les messages sont envoyés de manière asynchrone par file d'attente (BackgroundTasks) sans bloquer l'interface, et chaque destinataire reçoit un message personnalisé à son nom.

---

## Epic 5 : Conformité Réglementaire, Émargement Jour J & Déploiement

**Objectif :** Assurer la stricte conformité légale (Art. L310-2), garantir un accueil sans accroc sur le terrain le matin de l'événement, et fournir des outils de déploiement universels.

### Story 5.1 : Génération Automatique du Formulaire d'Attestation PDF
En tant qu'**exposante (Monique)**,  
Je veux **télécharger mon attestation sur l'honneur pré-remplie au format PDF**,  
Afin de **l'imprimer, la signer et la présenter aux bénévoles à mon arrivée le dimanche matin**.

**Acceptance Criteria:**
- **Given** une commande validée,
- **When** Monique clique sur le bouton "Télécharger mon attestation PDF" (sur le site ou dans son email),
- **Then** le moteur WeasyPrint compile un document PDF A4 aux normes légales françaises (Art. L310-2 du Code de commerce),
- **And** le document contient déjà : Nom, Prénom, Adresse, Numéro d'emplacement attribué, date du vide-grenier et un encart réservé à la signature manuscrite et au visa du placier.

### Story 5.2 : Export de la Feuille d'Émargement Officielle (PDF & Excel)
En tant qu'**organisateur (Marc)**,  
Je veux **générer la feuille d'émargement officielle de mon événement prête à l'impression en PDF et en tableur Excel**,  
Afin de **permettre aux bénévoles d'accueillir et pointer les véhicules à 6h00 sans ordinateur ni connexion internet**.

**Acceptance Criteria:**
- **Given** les inscriptions clôturées la veille de l'événement,
- **When** Marc clique sur "Exporter la feuille d'émargement",
- **Then** il peut télécharger :
  1. Un document PDF paginé trié par numéro d'allée/stand croissant (pour guider les véhicules au fur et à mesure de l'arrivée).
  2. Un document PDF trié par ordre alphabétique des noms (pour retrouver un exposant qui ne connaît plus son stand).
  3. Un fichier Excel complet (.xlsx).
- **And** le document comporte les colonnes : N° Stand, Métrage, Nom/Prénom, Téléphone, Statut paiement, Case à cocher "Présent", Case "Pièce d'identité contrôlée", N° CNI relevé au stylo.

### Story 5.3 : Scripts de Déploiement (Docker Compose & Script Natif Ubuntu)
En tant qu'**administrateur système ou bénévole associatif**,  
Je veux **déployer GVG en conteneur ou directement sur un serveur Ubuntu vierge via un script bash d'installation**,  
Afin d'**installer la plateforme en quelques minutes sur n'importe quel hébergeur sans compétence DevOps avancée**.

**Acceptance Criteria:**
- **Given** un environnement avec Docker et Docker Compose,
- **When** l'administrateur exécute `docker compose up -d`,
- **Then** les conteneurs PostgreSQL (PostGIS) et FastAPI/React démarrent, exécutent les migrations de schéma et sont accessibles sur le port configuré.
- **Given** un serveur Ubuntu 22.04 ou 24.04 LTS vierge sans Docker,
- **When** l'administrateur exécute `bash scripts/install-ubuntu.sh`,
- **Then** le script installe PostgreSQL 16, PostGIS, Python 3.12, Nginx et les dépendances WeasyPrint,
- **And** configure le service systemd `gvg.service` et le reverse-proxy Nginx avec succès.
