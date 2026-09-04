---
name: GVG (Gestion de Vide-Greniers)
description: Design System et identité visuelle de l'application web open-source de gestion de vide-greniers et brocantes.
colors:
  # Palette principale
  primary: '#166534'              # Vert Forêt / Plein air (fiable, rassurant, associatif)
  primary-foreground: '#FFFFFF'
  primary-light: '#DCFCE7'        # Vert menthe doux pour badges et fonds légers
  primary-dark: '#14532D'

  # Accent festif et commercial
  accent: '#D97706'               # Ambre solaire / Cuivre (action, dynamisme, fête)
  accent-foreground: '#FFFFFF'
  accent-light: '#FEF3C7'

  # États sémantiques des emplacements sur le plan interactif
  spot-available: '#10B981'       # Vert Émeraude : Emplacement libre à la vente
  spot-available-border: '#059669'
  spot-reserved: '#9CA3AF'        # Gris Neutre : Emplacement déjà vendu/occupé
  spot-reserved-border: '#6B7280'
  spot-locked: '#F59E0B'          # Ambre Doré : En cours de réservation (panier tiers)
  spot-locked-border: '#D97706'
  spot-selected: '#2563EB'        # Bleu Cobalt : Sélectionné dans mon panier actif
  spot-selected-border: '#1D4ED8'
  spot-disabled: '#E5E7EB'        # Gris très clair : Emplacement condamné/technique

  # Neutres & Fondations (ambiance lin & papier naturel)
  background: '#FBFBFA'           # Blanc cassé naturel (plus reposant qu'un blanc pur)
  foreground: '#1F2937'           # Gris ardoise foncé pour la lisibilité
  card: '#FFFFFF'
  card-foreground: '#1F2937'
  muted: '#F3F4F6'
  muted-foreground: '#6B7280'
  border: '#E5E7EB'
  input: '#E5E7EB'
  ring: '#166534'
  destructive: '#DC2626'
  destructive-foreground: '#FFFFFF'

typography:
  display:
    fontFamily: 'Outfit, Plus Jakarta Sans, sans-serif'
    fontSize: '32px'
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: '-0.02em'
  display-sm:
    fontFamily: 'Outfit, Plus Jakarta Sans, sans-serif'
    fontSize: '24px'
    fontWeight: '600'
    lineHeight: '1.25'
    letterSpacing: '-0.01em'
  body:
    fontFamily: 'Plus Jakarta Sans, Inter, sans-serif'
    fontSize: '16px'
    fontWeight: '400'
    lineHeight: '1.5'
  body-sm:
    fontFamily: 'Plus Jakarta Sans, Inter, sans-serif'
    fontSize: '14px'
    fontWeight: '400'
    lineHeight: '1.45'
  mono:
    fontFamily: 'JetBrains Mono, SF Mono, Consolas, monospace'
    fontSize: '14px'
    fontWeight: '600'

rounded:
  sm: '6px'
  md: '10px'
  lg: '14px'
  xl: '20px'
  full: '9999px'

spacing:
  # Échelle Tailwind standard (4px base)
  base: '4px'

components:
  button-primary:
    background: '{colors.primary}'
    foreground: '{colors.primary-foreground}'
    radius: '{rounded.md}'
    shadow: '0 2px 4px rgba(22, 101, 52, 0.15)'
  button-accent:
    background: '{colors.accent}'
    foreground: '{colors.accent-foreground}'
    radius: '{rounded.md}'
    shadow: '0 2px 4px rgba(217, 119, 6, 0.2)'
  spot-badge:
    radius: '{rounded.sm}'
    fontSize: '{typography.mono.fontSize}'
    fontWeight: '{typography.mono.fontWeight}'
  map-viewport:
    background: '#F0FDF4'          # Teinte herbeuse très pâle pour fond par défaut
    radius: '{rounded.lg}'
    border: '1px solid {colors.border}'
---

# GVG — Guide de Design Visuel (DESIGN.md)

## Brand & Style

**GVG (Gestion de Vide-Greniers)** s'inspire de l'authenticité et de la convivialité des dimanches de brocante et des fêtes de village. Le projet s'adresse à un public multigénérationnel : des bénévoles associatifs parfois peu familiers de la tech aux exposants du dimanche qui souhaitent réserver depuis leur smartphone au fond de leur jardin.

La posture de marque allie **chaleur champêtre** et **rigueur fonctionnelle** :
- **Pas d'effet gadget ni de design prétentieux** : Les éléments sont lisibles, contrastés, généreusement espacés et tactiles.
- **La clarté spatiale avant tout** : Le plan interactif est le héros de l'interface. Sa sémiologie graphique (vert = libre, ambre = bloqué, bleu = mon choix, gris = réservé) doit être comprise en 3 secondes chrono sans lire de notice.
- **Un univers rassurant et bienveillant** : Les formulaires évitent le jargon administratif rébarbatif et privilégient une formulation claire et humaine.

---

## Palette de Couleurs

Le code couleur s'organise autour d'un vert forêt plein air et d'un ocre chaleureux, complétés par la convention colorimétrique universelle du plan de réservation.

### 1. Teintes de Marque & Structure
- **Vert Forêt (`#166534`)** : Couleur identitaire primaire. Incarne l'esprit plein air, le terrain communal, la solidité associative. Utilisé pour les boutons d'action majeurs, les en-têtes et les indicateurs de confirmation.
- **Ocre Festif (`#D97706`)** : Couleur d'accent. Utilisée pour attirer l'œil sur les actions clés de conversion (ex: bouton *"Valider et payer mon stand"*), les notifications importantes et les bannières d'alerte.
- **Fond Papier Naturel (`#FBFBFA`)** : Évite la fatigue visuelle du blanc pur (`#FFFFFF`) et confère une texture douce et accessible à l'application.

### 2. Sémiologie des Emplacements sur le Plan Interactif
- **Disponible (`#10B981`, bordure `#059669`)** : Vert émeraude éclatant. Signal universel : "C'est libre, je peux cliquer".
- **Sélectionné par moi (`#2563EB`, bordure `#1D4ED8`)** : Bleu vif saturé avec contour contrasté. Permet à l'utilisateur de localiser instantanément ses stands choisis sur la carte.
- **Verrouillé temporairement (`#F59E0B`, bordure `#D97706`)** : Ambre chaleureux avec léger motif hachuré ou pulsation discrète : "Un autre exposant est en train de le réserver".
- **Réservé définitivement (`#9CA3AF`, bordure `#6B7280`)** : Gris doux apaisé : "Déjà attribué". Les détails du stand sont masqués pour respecter la vie privée des inscrits.

---

## Typographie

La typographie privilégie une lisibilité sans faille sur écran tactile en plein soleil.

- **Titres & Display (`Outfit`)** : Caractère sans-serif géométrique aux courbes douces et chaleureuses. Il apporte une touche contemporaine et conviviale sans rigidité institutionnelle.
- **Corps de texte & UI (`Plus Jakarta Sans`)** : Excellente lisibilité à petite taille sur mobile, haute distinction entre le `1`, le `l` et le `I`, idéal pour les consignes d'accès et les formulaires.
- **Codes d'emplacements & Tarifs (`JetBrains Mono`)** : Chiffres à largeur fixe (tabulaires) pour aligner parfaitement les numéros d'emplacements (`A-01`, `B-14`) et les prix en euros.

---

## Espacements & Mise en Page

- **Grille de base** : Multiple de 4px (Tailwind standard : 4, 8, 12, 16, 24, 32, 48px).
- **Cibles tactiles minimales** : Sur mobile, toute zone cliquable (notamment les stands sur le plan ou les boutons de zoom) mesure au strict minimum **44×44px** pour garantir une manipulation aisée avec le pouce.
- **Largeur de lecture** : Formulaires et pages informatives contraints à `max-w-xl` (576px) sur mobile/tablette pour ne jamais disperser l'attention.
- **Espace de travail de l'éditeur (Admin)** : Plein écran dynamique (`100vw`, `calc(100vh - 64px)`) pour offrir à Marc un plan de travail panoramique et confortable.

---

## Élévation & Profondeur

- **Niveau 0 (Fond de plan)** : La carte ou l'image satellite forme la base visuelle.
- **Niveau 1 (Stands dessinés)** : Ombres portées légères (`box-shadow: 0 1px 2px rgba(0,0,0,0.08)`) pour donner du relief aux emplacements par rapport au sol.
- **Niveau 2 (Commandes flottantes du plan)** : Zoom (+ / - / centrer) et compteur du panier flottant au-dessus du plan (`box-shadow: 0 4px 12px rgba(0,0,0,0.12)`).
- **Niveau 3 (Tiroir de commande / Cart Drawer)** : Volet inférieur mobile qui s'élève par-dessus la carte lors de la validation.

---

## Composants Clés

### 1. Le Stand Interactif (`spot-item`)
- Forme rectangulaire ou carrée avec coins légèrement adoucis (`radius: 4px`).
- Label textuel centré avec le numéro d'emplacement (`A12`).
- Effet de survol (desktop) : agrandissement subtil (+5%) et apparition d'un tooltip indiquant : *"Stand A12 • 2m • 8,00 €"*.
- Feedback tactile (mobile) : changement d'état immédiat vers le bleu (`spot-selected`) et déclenchement d'un micro-retour haptique.

### 2. Le Compteur de Verrouillage (`hold-timer`)
- Badge pill flottant en haut de l'écran lors du checkout :
  - Fond ambre pâle (`#FEF3C7`), bordure ambre (`#D97706`), texte foncé.
  - Icône sablier animée + décompte dynamique : *"Places réservées pendant 14:32"*.
  - En dessous de 2 minutes : la bordure pulse en rouge léger pour inciter sans paniquer.

### 3. Le Volet de Panier Mobile (`cart-drawer`)
- Bandeau fixe collé en bas de l'écran sur smartphone :
  - Affiche le nombre de places sélectionnées et le montant total : *"2 places (4m) • 16,00 €"*.
  - Bouton d'action large et proéminent : *"Continuer la réservation"*.

---

## Directives d'Application (Do's & Don'ts)

### ✅ À faire (Do)
- Toujours afficher la légende des 4 couleurs de stands bien en évidence à côté du plan.
- Fournir un bouton *"Recentrer la vue"* accessible en un tap pour ne jamais perdre l'utilisateur sur une carte dézoomée.
- Rassurer immédiatement l'exposant lors de la réservation : afficher clairement les horaires et le lieu dès le premier écran.
- Proposer des boutons d'incrémentation `+` et `-` de grande taille pour le métrage plutôt qu'un champ texte brut.

### ❌ À proscrire (Don't)
- Ne jamais surcharger le plan avec des icônes inutiles ou du texte illisible à fort dézoom.
- Ne pas exiger de mot de passe ni de confirmation d'email préalable pour réserver.
- Éviter les couleurs anxiogènes (ex: rouge vif clignotant pour les stands déjà pris ; préférer un gris neutre reposant).
- Ne jamais masquer le prix total : le tarif calculé au mètre doit être transparent à chaque instant.
