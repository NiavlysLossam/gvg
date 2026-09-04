---
title: Gestion de Vide-Greniers (GVG)
status: final
created: 2026-09-04
updated: 2026-09-04
---

# PRD: Gestion de Vide-Greniers (GVG)
*Plateforme web open-source de gestion d'événements de vente au déballage et brocantes*

## 0. Document Purpose
Ce document définit les exigences produit (Product Requirements Document) pour **GVG**, une application web open-source conçue pour moderniser et simplifier l'organisation de vide-greniers, brocantes et foires à tout. Il s'adresse aux développeurs, architectes, designers UX et parties prenantes du projet. Les termes clés sont définis dans le **Glossaire (§3)**, les fonctionnalités sont découpées en **Exigences Fonctionnelles (FR-1 à FR-N)** stables et traçables, et les hypothèses de cadrage sont signalées via les balises `[ASSUMPTION]`.

---

## 1. Vision

L'organisation d'un vide-grenier annuel repose encore aujourd'hui, dans une immense majorité d'associations et de comités des fêtes, sur des processus archaïques : permanences physiques en mairie, gestion manuelle de plans papier ou tableurs Excel disparates, réception de chèques par courrier et saisie fastidieuse du registre des vendeurs obligatoire. Ce fonctionnement génère une charge mentale et administrative disproportionnée pour les bénévoles, tout en imposant des frictions d'inscription considérables pour les exposants.

**GVG** ambitionne de devenir la solution web open-source de référence pour la gestion de vide-greniers. Elle offre aux organisateurs un outil intuitif pour configurer leur événement, dessiner un plan d'emplacements interactif sur photo aérienne ou plan de salle, et suivre les réservations en temps réel. Pour les exposants, la réservation et le paiement par carte bancaire se font en quelques clics sans compte obligatoire, avec garantie anti-collision sur les places. 

En automatisant les flux transactionnels (encaissement Stripe direct, e-mails de convocation et modèles d'attestation) et en fournissant une feuille d'émargement prête à l'emploi le Jour J, GVG élimine la corvée administrative pour que les organisateurs et les participants se concentrent sur la convivialité de leur fête de quartier ou de village.

---

## 2. Utilisateurs Cibles & Parcours

### 2.1 Jobs To Be Done (JTBD)
- **Organisateur associatif / Gestionnaire** : *"Quand j'organise le vide-grenier annuel de mon association, je veux créer mon plan, définir mes tarifs, encaisser les réservations en ligne et garder le contrôle total sur les validations et remboursements, afin de remplir mon événement sans stress et maîtriser la trésorerie."*
- **Exposant particulier** : *"Quand je décide de vider mon grenier le week-end, je veux repérer facilement un emplacement libre sur un plan, réserver et payer en 2 minutes depuis mon smartphone sans créer de compte compliqué, et pouvoir demander une annulation si j'ai un empêchement."*
- **Placier / Bénévole d'accueil le Jour J** : *"Quand j'accueille 150 voitures à 6h du matin, je veux disposer d'une liste papier claire et triée pour pointer l'arrivée, vérifier la pièce d'identité et orienter immédiatement le véhicule vers son allée."*

### 2.2 Non-Utilisateurs (v1)
- **Exposants professionnels / Brocanteurs professionnels** : Exclus du périmètre du MVP v1 (gestion des numéros de registre de commerce / SIRET / TVA spécifique différée en v2). Le MVP est 100% dédié aux exposants particuliers.
- **Grands festivals / Salons marchands avec billetterie multi-jours complexe** : Le MVP cible les vide-greniers d'un jour (ou un week-end simple).

### 2.3 Key User Journeys (UJ)

#### **UJ-1 : Marc configure son événement et dessine son plan interactif**
- **Persona & Contexte** : Marc, 48 ans, secrétaire du comité des fêtes. Il prépare le vide-grenier communal prévu dans 2 mois (120 emplacements prévus le long de la rue principale et sur la place de la mairie).
- **Point d'entrée** : Authentifié sur son espace administrateur GVG sur PC.
- **Parcours** :
  1. Marc clique sur "Créer un événement" : il saisit le nom ("Vide-Grenier de Printemps"), la date, les horaires d'accueil des exposants (6h-8h) et d'ouverture au public (8h-18h), l'adresse et le tarif de base au mètre linéaire (ex: 4 €/m).
  2. Il accède à l'Éditeur de Plan : il charge un fond de carte aérien (satellite OpenStreetMap / vue aérienne) centré sur la place du village, ou importe le fichier image du schéma de la salle des fêtes.
  3. Avec l'outil rectangle/carré, il trace les emplacements le long de la place par blocs d'allées. L'outil numérote automatiquement les stands (Allée A : 1 à 25, Allée B : 26 à 50...).
  4. Il configure la clé de son compte Stripe pour recevoir les fonds directement.
  5. Il clique sur "Publier l'événement" et récupère le lien public d'inscription qu'il partage sur la page Facebook de la commune et sur les affiches.
- **Climax** : Marc visualise son plan propre, interactif, prêt à recevoir des réservations publiques.
- **Résolution** : L'événement est en ligne. Le dashboard affiche 0/120 places réservées et attend les premières inscriptions.

#### **UJ-2 : Monique réserve son emplacement en ligne sans friction**
- **Persona & Contexte** : Monique, 58 ans, peu familière des outils numériques complexes, souhaite réserver 2 emplacements (4 mètres au total) pour vendre des vêtements d'enfants et de la vaisselle.
- **Point d'entrée** : Clique sur le lien Facebook partagé par le comité des fêtes depuis son smartphone.
- **Parcours** :
  1. Monique arrive sur la page publique de l'événement. Elle consulte la description, la date et le plan interactif avec les stands disponibles en vert.
  2. Elle tape sur l'emplacement A12, puis sur l'emplacement A13 (2x2m). Un indicateur l'informe que ces deux places lui sont temporairement réservées pendant 15 minutes.
  3. Elle clique sur "Finaliser ma réservation". Aucun mot de passe ne lui est demandé (parcours invité).
  4. Elle renseigne son nom, prénom, email, téléphone et adresse postale.
  5. Elle coche la mention légale attestant sur l'honneur qu'elle ne participe pas à plus de 2 ventes au déballage dans l'année civile.
  6. Elle paie 16 € par carte bancaire via le widget sécurisé Stripe.
- **Climax** : Écran de confirmation immédiat : *"Réservation confirmée pour les stands A12 et A13 !"*.
- **Résolution** : Monique reçoit immédiatement un email récapitulatif avec les horaires, son numéro d'emplacement, le lien pour télécharger son attestation pré-remplie, et un lien pour demander une annulation si besoin.

#### **UJ-3 : Monique demande une annulation et Marc la valide**
- **Persona & Contexte** : 10 jours avant l'événement, Monique a un empêchement familial et ne peut plus venir.
- **Point d'entrée** : Monique depuis son email de confirmation de réservation.
- **Parcours** :
  1. Monique clique sur le lien *"Demander l'annulation / le remboursement"* figurant au bas de son email.
  2. Sur la page dédiée, elle sélectionne son motif (ex: *"Imprévu personnel / santé"*), ajoute un commentaire facultatif et valide sa demande.
  3. Le système lui indique : *"Votre demande d'annulation a bien été transmise à l'organisateur. Elle sera examinée dans les meilleurs délais."* La réservation reste pour l'instant active.
  4. De son côté, Marc (gestionnaire) voit apparaître une pastille d'alerte sur son dashboard dans l'onglet *"Remboursements en attente"*.
  5. Marc consulte la demande de Monique, vérifie la date par rapport au règlement de l'événement et clique sur **"Valider le remboursement"**.
- **Climax** : Le remboursement Stripe est immédiatement déclenché vers la carte de Monique, les places A12 et A13 redeviennent instantanément vertes (disponibles) sur le plan public.
- **Résolution** : Monique reçoit un email confirmant l'acceptation de sa demande et le remboursement sur son compte bancaire sous 3 à 5 jours ouvrés.

#### **UJ-4 : Marc gère une réservation manuelle hors-ligne**
- **Persona & Contexte** : Marc reçoit la visite de M. Robert, 75 ans, venu déposer un chèque de 8 € pour réserver le stand B04.
- **Point d'entrée** : Marc sur son dashboard d'administration GVG.
- **Parcours** :
  1. Marc clique sur l'emplacement B04 sur le plan interactif.
  2. Il clique sur "Ajouter une réservation manuelle".
  3. Il saisit : Nom="Robert", Prénom="Jean", Téléphone="0600000000", Mode de paiement="Chèque (encaissé)".
  4. Il valide. L'emplacement passe immédiatement au statut "Réservé".
- **Climax** : La place B04 est verrouillée sur le site public en temps réel, évitant tout risque de double vente.
- **Résolution** : La commande apparaît dans le tableau de bord avec le tag `Paiement hors-ligne (Chèque)`.

#### **UJ-5 : Marc prépare et pilote le Jour J**
- **Persona & Contexte** : La veille du vide-grenier, Marc prépare les documents pour l'équipe de bénévoles qui sera sur le terrain dès 5h30.
- **Point d'entrée** : Espace administrateur GVG.
- **Parcours** :
  1. Marc clique sur "Exporter la feuille d'émargement".
  2. Il télécharge et imprime un document PDF prêt à l'emploi, trié par Allée / Numéro d'emplacement (et une copie triée par ordre alphabétique des noms).
  3. Le dimanche à 6h00, les bénévoles pointent chaque exposant qui arrive, récupèrent l'attestation papier signée et vérifient la pièce d'identité physique.
- **Climax** : Aucun litige de place en double, circulation fluide à l'entrée.
- **Résolution** : La manifestation démarre à l'heure dans la sérénité.

---

## 3. Glossaire

- **Événement** : Instance d'un vide-grenier, brocante ou foire à tout, défini par des dates, horaires, une adresse et un ensemble d'emplacements.
- **Gestionnaire (ou Organisateur Principal)** : Administrateur principal de l'événement détenant les droits de publication, de configuration financière Stripe et de validation/refus des remboursements.
- **Emplacement (ou Stand / Place)** : Entité spatiale délimitée sur le plan, dotée d'un identifiant unique (ex: A12), d'un métrage linéaire (en mètres), d'un tarif calculé et d'un statut (Libre, Verrouillé temporairement, Réservé, Bloqué).
- **Plan Interactif** : Représentation visuelle bidimensionnelle composée d'un fond de plan (carte satellite ou image importée) et de polygones/rectangles interactifs cliquables représentant les emplacements.
- **Verrou Temporaire (Hold Lock)** : Mécanisme d'invalidation temporaire (15 minutes) d'un emplacement sélectionné par un utilisateur dans son panier pour empêcher la surréservation (*race condition*).
- **Demande de Remboursement** : Requête initiée par un exposant depuis son email de confirmation, en attente d'arbitrage (approbation ou rejet) par le gestionnaire.
- **Exposant Particulier** : Personne physique effectuant une vente occasionnelle d'objets personnels et usagés, soumise à la limitation légale de 2 participations par an (Code de commerce art. L310-2).
- **Registre des Vendeurs** : Document réglementaire obligatoire en France (tenu à la disposition des autorités de police et des douanes pendant la manifestation) consignant l'identité et les justificatifs des participants.
- **Formulaire d'Attestation** : Document pré-rempli généré par la plateforme, à signer par l'exposant et à remettre physiquement à l'arrivée le Jour J.
- **Feuille d'Émargement** : Liste synthétique exportable (PDF/Excel) permettant le pointage physique des exposants le matin de l'événement.
- **Réservation Hors-Ligne** : Réservation saisie manuellement par l'organisateur (règlement en espèces ou par chèque) ne transitant pas par Stripe.

---

## 4. Fonctionnalités & Spécifications Détaillées

### 4.1 Module Événement & Éditeur de Plan Interactif
**Description :** Permet à l'organisateur de paramétrer son événement et de créer visuellement le plan de masse de ses stands. Réalise **UJ-1**.

#### FR-1 : Création et configuration d'un événement
L'organisateur peut créer un événement en renseignant les métadonnées essentielles : Titre, Description publique, Dates et créneaux horaires (installation vs public), Adresse physique, Contact organisateur, Règlement intérieur (texte ou PDF), et Tarif unitaire au mètre linéaire.
**Conséquences testables :**
- L'événement dispose d'une URL publique unique et partageable.
- Si la date de fin d'événement est passée, les réservations publiques sont automatiquement désactivées.

#### FR-2 : Import et calibrage du fond de plan
L'organisateur peut choisir comme fond de plan :
1. Une vue cartographique/satellite dynamique (tuiles OpenStreetMap / API cartographique) centrée sur l'adresse de l'événement.
2. L'import d'un fichier image personnalisé (formats PNG, JPEG ou SVG, ex: plan intérieur de gymnase ou dessin cadastral).
**Conséquences testables :**
- L'organisateur peut zoomer, se déplacer et ajuster la luminosité ou le contraste du fond pour faciliter le dessin.
- Le fond de plan est persisté et rechargé fidèlement sur tous les écrans (desktop et mobile).

#### FR-3 : Outil de dessin vectoriel des emplacements
L'organisateur peut dessiner des emplacements de forme rectangulaire ou carrée directement sur le fond de plan.
**Conséquences testables :**
- Chaque stand dessiné peut être déplacé, redimensionné ou pivoté.
- L'outil permet la duplication rapide d'un stand ou d'une rangée de stands identiques.
- Un clic sur un stand permet de définir son métrage linéaire (ex: 2m, 3m, 4m).

#### FR-4 : Numérotation automatique intelligente
L'organisateur peut générer automatiquement la numérotation d'une sélection de stands selon un préfixe (ex: "Allée A - "), un numéro de départ et une incrémentation séquentielle.
**Conséquences testables :**
- Le système garantit l'unicité des identifiants d'emplacements au sein d'un même événement.
- Possibilité de modifier unitairement le numéro ou label de n'importe quel emplacement en cas d'exception.

---

### 4.2 Module Réservation & Billetterie Exposant
**Description :** Interface grand public optimisée mobile permettant la sélection sur plan, la réservation et le paiement sécurisé. Réalise **UJ-2**.

#### FR-5 : Consultation interactive du plan public
Tout visiteur peut visualiser le plan de l'événement en temps réel, avec distinction claire des statuts par code couleur : Vert = Disponible, Gris = Déjà réservé, Jaune/Orange = En cours de commande (verrouillé).
**Conséquences testables :**
- Sur mobile, le plan supporte le pinch-to-zoom et le drag & drop tactile fluide.
- Un clic sur un emplacement affiche une infobulle indiquant son numéro, son métrage et son prix calculé (Métrage × Tarif au mètre).

#### FR-6 : Verrouillage temporaire anti-collision (Hold Lock)
Dès qu'un utilisateur sélectionne un ou plusieurs emplacements et clique sur "Réserver", le système applique un verrou temporaire d'une durée de 15 minutes `[ASSUMPTION: durée configurable par l'organisateur entre 10 et 20 min]`.
**Conséquences testables :**
- Tout autre utilisateur tentant de sélectionner cet emplacement voit un état "En cours de réservation" et ne peut pas l'ajouter à son panier.
- À l'expiration des 15 minutes sans paiement validé, le verrou est automatiquement libéré et le stand redevient vert en temps réel (via WebSocket ou polling court).

#### FR-7 : Réservation multi-emplacements
L'utilisateur peut sélectionner et réserver plusieurs emplacements au cours de la même commande, qu'ils soient contigus ou non.
**Conséquences testables :**
- Le montant total du panier correspond à la somme exacte des emplacements sélectionnés.

#### FR-8 : Parcours de commande invité (Guest Checkout)
La réservation s'effectue sans création de compte utilisateur préalable ni mot de passe.
**Conséquences testables :**
- Les champs obligatoires sont : Nom, Prénom, Adresse email valide, Numéro de téléphone mobile, Adresse postale complète.
- Une case à cocher obligatoire engage la responsabilité de l'exposant : *"Je certifie sur l'honneur être un particulier et ne pas avoir participé à plus de 2 ventes au déballage au cours de l'année civile en cours."*

#### FR-9 : Paiement sécurisé en ligne Stripe
Le règlement s'effectue directement via Stripe Elements (carte bancaire, Apple Pay, Google Pay).
**Conséquences testables :**
- L'organisateur reçoit les fonds directement sur son propre compte Stripe configuré.
- Dès confirmation du paiement par webhook Stripe, la commande passe au statut `Confirmée`, le verrou temporaire est converti en réservation définitive, et le stand passe en rouge/gris sur le plan.

---

### 4.3 Module Gestion & Administration Organisateur
**Description :** Outils de pilotage pour l'organisateur : suivi des ventes, ajout manuel, modération et arbitrages des remboursements. Réalise **UJ-3**, **UJ-4** et **UJ-5**.

#### FR-10 : Tableau de bord des inscriptions
L'organisateur dispose d'une vue consolidée listant toutes les réservations avec filtres (Confirmé, En attente, Annulé, Hors-ligne), recherche instantanée par nom ou numéro de stand, et jauge de remplissage globale (% et CA total).
**Conséquences testables :**
- Exportation des données de réservation au format CSV / Excel en un clic.

#### FR-11 : Saisie de réservations manuelles (Paiements Hors-ligne)
L'organisateur peut bloquer manuellement un ou plusieurs emplacements au profit d'un exposant sans passer par Stripe (paiement par chèque, espèces ou gratuité bénévole).
**Conséquences testables :**
- L'organisateur indique le moyen de paiement (Espèces, Chèque, Autre) et peut marquer la réservation comme "Payée" ou "En attente de règlement".
- Le stand est instantanément retiré des disponibilités publiques.

#### FR-12 : Workflow de modération optionnelle à l'inscription
L'organisateur peut activer une option "Validation manuelle requise" pour son événement.
**Conséquences testables :**
- Si activé : le paiement de l'exposant prend la forme d'une pré-autorisation bancaire (capture différée). L'organisateur dispose d'un bouton "Accepter" (qui déclenche la capture) ou "Refuser" (qui libère les fonds).
- Si désactivé (comportement par défaut) : la confirmation et l'encaissement sont instantanés dès le paiement.

#### FR-13 : Workflow de demande et validation des remboursements
Les remboursements ne sont jamais automatiques et doivent obligatoirement être validés par le gestionnaire (organisateur principal).
**Conséquences testables :**
1. **Initiation par l'exposant** : L'exposant peut soumettre une demande d'annulation depuis son lien dédié dans son email de confirmation en précisant un motif. La commande passe à l'état `Demande d'annulation en cours`.
2. **File d'attente du gestionnaire** : L'organisateur dispose d'un onglet dédié *"Demandes de remboursement"* affichant l'exposant, la date d'inscription, les stands concernés, le montant et le motif formulé.
3. **Approbation par le gestionnaire** : Un clic sur "Valider le remboursement" appelle l'API Stripe Refund, bascule la commande en `Remboursée`, libère immédiatement les stands associés sur le plan interactif (retour à l'état "Disponible"), et envoie un email de confirmation de remboursement à l'exposant.
4. **Refus par le gestionnaire** : Un clic sur "Rejeter la demande" maintient la réservation et les stands bloqués, permet de saisir un motif de rejet (ex: *"Délai légal dépassé"*), et notifie l'exposant par email.
5. **Remboursement groupé (Annulation globale de l'événement)** : En cas de force majeure ou météo, le gestionnaire peut déclencher le remboursement intégral de l'ensemble des réservations en ligne de l'événement en une seule opération avec double confirmation.

---

### 4.4 Module E-mailing & Communication
**Description :** Moteur de communication intégré permettant les envois transactionnels et les campagnes d'information aux participants. Réalise **UJ-2**, **UJ-3** et **UJ-5**.

#### FR-14 : E-mails transactionnels automatisés
Le système envoie automatiquement des e-mails lors des étapes clés du cycle de vie :
1. **Accusé de réception de commande** : Récapitulatif détaillé des stands réservés, montant payé, consignes d'accès, lien vers le formulaire d'attestation pré-rempli et lien de demande d'annulation.
2. **Gestion des remboursements** : Accusé de réception de la demande d'annulation, notification de validation avec détails du remboursement, ou notification de rejet avec motif.
3. **Rappels automatiques programmés** : Envoi automatique à J-7 et J-2 rappelant les horaires d'installation, l'adresse exacte, l'accès véhicules et les documents obligatoires à présenter le matin.
**Conséquences testables :**
- L'organisateur peut personnaliser le texte et les horaires d'envoi de ces messages types.

#### FR-15 : E-mails manuels de masse (Campagnes & Alertes)
L'organisateur peut rédiger et envoyer un email à l'ensemble des inscrits confirmés de son événement (ou filtrer par allée/zone).
**Conséquences testables :**
- Envoi asynchrone par file d'attente (queuing) avec suivi des statuts de délivrabilité (envoyé, échec).
- Idéal pour les alertes de dernière minute (ex: consignes météo, fermeture temporaire d'un accès routier).

#### FR-16 : Variables de personnalisation dynamiques
L'éditeur d'email permet l'insertion de tags dynamiques substitués à l'envoi : `{{exposant.prenom}}`, `{{exposant.nom}}`, `{{commande.emplacements}}`, `{{evenement.nom}}`, `{{evenement.date}}`, `{{evenement.horaires_installation}}`.
**Conséquences testables :**
- Chaque destinataire reçoit un email contenant ses données nominatives propres.

---

### 4.5 Module Conformité Légale & Jour J
**Description :** Outils concrets garantissant la conformité réglementaire française (Art. L310-2 du Code de commerce) et facilitant le travail de terrain. Réalise **UJ-5**.

#### FR-17 : Génération du formulaire d'attestation à imprimer
La plateforme génère pour chaque exposant un document PDF d'attestation sur l'honneur pré-rempli avec ses informations saisies (Nom, Prénom, Adresse, Numéro d'emplacement).
**Conséquences testables :**
- Le document comporte les mentions légales requises et un encart pour la signature manuscrite de l'exposant ainsi que l'émargement de la vérification d'identité le Jour J.
- Téléchargeable depuis l'email de confirmation.

#### FR-18 : Export de la feuille d'émargement officielle (PDF & Excel)
L'organisateur peut générer en un clic la feuille d'émargement prête à l'impression pour le jour J.
**Conséquences testables :**
- Deux tris disponibles au choix :
  1. Tri par Allée / Emplacement croissant (pour le guidage et l'accueil des véhicules à l'entrée).
  2. Tri alphabétique par Nom d'exposant (pour retrouver rapidement un participant).
- Colonnes incluses : N° Stand, Métrage, Nom/Prénom, Téléphone, Montant & Statut paiement, Case à cocher "Présent", Case à cocher "Pièce d'identité contrôlée", N° de pièce d'identité (à renseigner au stylo ou déjà noté).

---

## 5. Exigences Non Fonctionnelles Transverses (NFR)

### NFR-1 : Concurrence & Temps Réel
- Le système de verrouillage temporaire (Hold Lock) doit garantir qu'aucun emplacement ne puisse être vendu deux fois, y compris sous une charge de 500 utilisateurs consultant et réservant simultanément au lancement des inscriptions.
- Latence d'actualisation de l'état d'un emplacement sur le plan public < 1 seconde après pose d'un verrou ou validation de commande/remboursement.

### NFR-2 : Ergonomie & Responsive Web Design
- Le tunnel de réservation exposant (consultation du plan, saisie coordonnées, paiement, demande d'annulation) doit être conçu selon une approche strictement **Mobile-First**.
- Score de performance Google Lighthouse Mobile >= 90 pour la page publique de réservation.

### NFR-3 : Sécurité & RGPD
- Zéro stockage de pièces d'identité scannées ou photos sur les serveurs de l'application dans le MVP (contrôle physique déporté sur place).
- Données personnelles (coordonnées des exposants) stockées de manière chiffrée, accessibles uniquement par l'organisateur de l'événement concerné.
- Conformité PCI-DSS assurée par la délégation intégrale de la saisie bancaire à Stripe Elements (aucun numéro de carte bancaire ne transite par les serveurs GVG).

### NFR-4 : Architecture Open-Source & Auto-Hébergement
- L'application doit pouvoir être déployée facilement via conteneurs Docker (Docker Compose).
- Modularité des fournisseurs d'e-mails (support SMTP standard + API type Resend/Postmark/Sendgrid).
- Configuration simple par instance ou multi-tenant : un organisateur peut déployer sa propre instance pour son association, ou une fédération/commune peut héberger plusieurs événements.

---

## 6. Non-Objectifs Explicites (v1)

- **Gestion des exposants professionnels** : Pas de formulaires spécifiques avec numéro de registre de commerce, Kbis ou gestion de factures d'acompte HT/TTC pour les professionnels en v1.
- **Application mobile native (iOS / Android)** : GVG est une application 100% Web (Responsive Web App / PWA), accessible depuis n'importe quel navigateur sans téléchargement sur les stores.
- **Pointeur mobile en ligne avec scan de QR Code le Jour J** : Le pointage le Jour J s'appuie sur la feuille d'émargement papier (MVP simple et infaillible même en cas de zone blanche 4G sur le terrain).
- **Place de marché globale / Annuaire national géolocalisé de vide-greniers** : GVG fournit l'outil logiciel d'organisation et de billetterie, pas un portail public de référencement national concurrent de Brocabrac ou Vide-greniers.org en v1.

---

## 7. Périmètre du MVP (Scope)

### 7.1 In Scope (MVP v1)
- Création d'événement (dates, horaires, lieu, tarif au mètre).
- Éditeur de plan interactif : fond cartographique OpenStreetMap ou import image (salle/plan), dessin de rectangles/carrés, numérotation automatique.
- Visualisation publique du plan avec statuts en temps réel (disponible, verrouillé, réservé).
- Système de verrou temporaire (15 min) anti-surréservation.
- Réservation multi-emplacements.
- Tunnel de réservation "Invité" sans mot de passe réservé aux particuliers.
- Paiement sécurisé par carte bancaire via Stripe.
- Saisie manuelle de réservations hors-ligne (chèques/espèces) par l'organisateur.
- Workflow de demande d'annulation par l'exposant et validation/refus manuelle par le gestionnaire.
- Remboursement de masse en cas d'annulation globale de l'événement.
- E-mails transactionnels (confirmation, statut de remboursement, rappels programmés à J-7 et J-2).
- Envoi manuel d'e-mails groupés aux exposants inscrits avec tags dynamiques.
- Export de la feuille d'émargement officielle pour le Jour J (PDF et Excel).

### 7.2 Out of Scope (Différé à la v2 / v3)
- Gestion des exposants professionnels (SIRET, registre de commerce, régimes fiscaux).
- Application web de pointage terrain en direct sur smartphone avec scan QR Code.
- Tarification dynamique selon les zones du plan (ex: allée centrale plus chère qu'allée secondaire).
- Gestion des options additionnelles payantes (location de tables, chaises, café/croissant d'accueil).
- Portail multi-événements avec moteur de recherche public par code postal.

---

## 8. Métriques de Succès (Success Metrics)

### Primaires
- **SM-1 (Taux d'abandon de panier exposant)** : < 15% d'abandon entre la sélection de l'emplacement sur le plan et la finalisation du paiement (validé par FR-5, FR-8, FR-9).
- **SM-2 (Gain de temps organisateur)** : Réduction de plus de 80% du temps administratif passé par l'organisateur sur la gestion des réservations et la préparation du plan par rapport au format papier/chèque traditionnel.

### Secondaires
- **SM-3 (Zéro double attribution)** : 0 incident de collision ou de surréservation d'un même emplacement signalé le Jour J (validé par FR-6).
- **SM-4 (Taux de délivrabilité des emails)** : > 98% des emails de confirmation et de rappel reçus en boîte principale (validé par FR-14).

### Contre-Métrique (Ne pas sur-optimiser)
- **SM-C1 (Complexité du plan)** : Ne pas chercher à transformer l'éditeur de plan en un logiciel de CAO/DAO complexe (type AutoCAD). La simplicité de prise en main en moins de 10 minutes par un bénévole associatif non-technique prime sur la précision millimétrique des tracés.

---

## 9. Questions Ouvertes & Points d'Attention

1. **Choix de la bibliothèque cartographique / rendu visuel** : L'éditeur de plan interactif doit-il être bâti sur une surcouche type Leaflet / MapLibre (idéal pour les coordonnées géo et tuiles satellites) ou sur un moteur Canvas/SVG type Konva.js / Fabric.js (idéal pour le dessin précis et les plans intérieurs de salles) ? *(À trancher en phase Architecture)*.
2. **Fournisseur de messagerie par défaut en Open-Source** : Fournir une configuration simple pour du SMTP classique (Orange, Free, OVH, Gmail) en plus des API transactionnelles modernes (Resend, Brevo).

---

## 10. Index des Hypothèses `[ASSUMPTION]`

- `[ASSUMPTION §4.2 / FR-6]` : La durée du verrouillage temporaire lors de la réservation est fixée à 15 minutes par défaut, tout en restant ajustable par l'organisateur dans les paramètres de son événement.
- `[ASSUMPTION §4.1 / FR-1]` : La tarification se fait au mètre linéaire simple pour l'ensemble de l'événement dans le MVP, sans différenciation de prix selon l'exposition ou la zone.
- `[ASSUMPTION §4.5 / FR-17]` : Le contrôle physique des pièces d'identité et la récupération de l'attestation papier signée le Jour J sur le terrain sont juridiquement suffisants pour dédouaner la responsabilité de la plateforme logicielle vis-à-vis du Code de commerce.
