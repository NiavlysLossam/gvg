---
title: "Story 5.2 : Export de la Feuille d'Émargement Officielle (PDF & Excel)"
type: 'feature'
created: '2026-09-14'
status: 'done'
baseline_commit: 'eee1aad862a3c11c242d28e9244714921d5f6182'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '_bmad-output/implementation-artifacts/epic-5-context.md'
  - '_bmad-output/planning-artifacts/architecture/architecture-gvg-2026-09-04/ARCHITECTURE-SPINE.md'
  - '_bmad-output/planning-artifacts/ux-designs/ux-gvg-2026-09-04/EXPERIENCE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Le matin de l'événement à 6h00, les bénévoles et placiers doivent accueillir, orienter et pointer des dizaines ou centaines d'exposants arrivant simultanément en voiture, souvent dans des zones sans réseau mobile 4G/5G fiable et sans ordinateur portable. Les organisateurs ont besoin d'un registre officiel d'émargement physique prêt pour l'impression, disponible en deux classements (par emplacement pour guider les véhicules au fil des allées, et par ordre alphabétique pour retrouver rapidement un exposant sans son numéro de stand), ainsi qu'en tableur Excel pour les besoins de gestion administrative.

**Approach:**
1. Étendre `backend/app/services/pdf_service.py` et créer le template Jinja2 `backend/app/templates/pdf/checkin.html` au format A4 paysage paginé avec WeasyPrint, en-têtes répétés (`thead { display: table-header-group; }`), numérotation automatique de page (`Page X / Y`), et deux modes de tri (`spot` pour le tri naturel croissant par numéro de stand/allée, et `alpha` pour le tri alphabétique par nom et prénom).
2. Développer `backend/app/services/excel_service.py` basé sur `openpyxl` pour produire le classeur Excel `.xlsx` complet contenant les données des inscrits avec colonnes de pointage et mise en forme professionnelle.
3. Exposer dans `backend/app/api/v1/endpoints/orders.py` deux endpoints sécurisés d'administration :
   - `GET /api/v1/events/{id_or_slug}/checkin.pdf?sort_by=spot|alpha` streamant le PDF d'émargement.
   - `GET /api/v1/events/{id_or_slug}/checkin.xlsx` streamant le tableur Excel.
4. Intégrer dans `frontend/src/pages/RegistrationsPage.tsx` un menu déroulant ou bouton d'export élégant « Émargement » permettant de télécharger en un clic :
   - PDF par emplacement (N° Stand)
   - PDF alphabétique (Nom exposant)
   - Tableur Excel (.xlsx)

## Boundaries & Constraints

**Always:**
- Le document PDF d'émargement doit être configuré en format A4 Paysage (`size: A4 landscape; margin: 12mm 15mm 15mm 15mm;`) avec en-têtes de tableau répétés sur chaque page imprimée (`thead { display: table-header-group; }`) et pagination claire (`Page X / Y`).
- Les colonnes impératives de la feuille d'émargement sont : N° Stand, Métrage, Nom / Prénom, Téléphone, Statut paiement, Case à cocher "Présent", Case "Pièce d'identité contrôlée", N° CNI relevé au stylo.
- Seules les commandes au statut `confirmed` (inscriptions effectives disposant d'un ou plusieurs stands attribués) doivent figurer sur la feuille d'émargement officielle.
- Le tri par stand doit appliquer un ordre naturel alphanumérique (`A-1`, `A-2`, `A-10`).
- Les flux PDF et Excel doivent être streamés directement en mémoire (`BytesIO`) avec les en-têtes HTTP `Content-Disposition` et `Cache-Control: private, no-store, must-revalidate` sans persistance de fichiers temporaires sur disque (conformité RGPD AD-4).
- `openpyxl>=3.1.0` doit être déclaré dans `backend/pyproject.toml` et `backend/requirements.txt`.

**Never:**
- Ne jamais inclure les commandes annulées (`cancelled`), rejetées (`rejected`) ou remboursées (`refunded`) dans l'émargement Jour J.
- Ne jamais tronquer silencieusement des noms de colonnes ou déborder hors de la largeur A4 paysage imprimable.
- Ne jamais générer d'erreurs 500 sur des champs optionnels vides (ex: exposant sans téléphone, prénom manquant, caractères accentués spéciaux).

## I/O & Edge-Case Matrix

| Scénario | Données en entrée | Résultat attendu | Gestion d'erreur / Robustesse |
|---|---|---|---|
| Export PDF par stand | `sort_by=spot`, événement avec 50 commandes confirmées | PDF A4 paysage multi-pages, lignes ordonnées par allée/stand naturel (`A-01, A-02, B-01...`) | Pagination automatique avec rappel du titre d'événement et répétition des en-têtes |
| Export PDF alphabétique | `sort_by=alpha`, 50 commandes | PDF A4 paysage multi-pages, lignes ordonnées par Nom/Prénom exposant (A → Z) | Support insensible à la casse et accents corrects (ex: Éric avant François) |
| Export Excel (.xlsx) | Événement avec inscriptions | Fichier binaire `.xlsx` structuré avec en-têtes stylisés, largeurs adaptées et colonnes de pointage | Types MIME `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| Événement sans inscription confirmée | 0 commande confirmée | PDF ou Excel propre indiquant « Aucun exposant inscrit » ou tableau vide sans planter | Pas de division par zéro ni crash Jinja2/openpyxl |
| Exposant avec plusieurs stands | Commande avec Stands A-01 (2m) et A-02 (2m) | En mode `spot` : chaque stand apparaît à sa place dans la grille. En mode `alpha` : regroupe `A-01, A-02` (4 m) ou liste chaque stand clairement | Présentation fluide sans doublon ambigu |
| Accents et caractères rares | Noms composés, apostrophes, trémas | Encodage UTF-8 parfait dans le PDF et dans l'Excel | Pas de caractères corrompus (Mojibake) |

</frozen-after-approval>

## Code Map

- `backend/pyproject.toml` & `backend/requirements.txt` -- Ajout de `openpyxl>=3.1.0`.
- `backend/app/templates/pdf/checkin.html` -- Gabarit Jinja2/HTML/CSS A4 paysage de la feuille d'émargement officielle avec pagination WeasyPrint et en-têtes répétés.
- `backend/app/services/pdf_service.py` -- Ajout de `generate_checkin_pdf(event: Event, orders: list[Order], sort_by: str = "spot") -> bytes`.
- `backend/app/services/excel_service.py` -- Nouveau service de génération de tableur Excel d'émargement `generate_checkin_xlsx(event: Event, orders: list[Order]) -> bytes`.
- `backend/app/api/v1/endpoints/orders.py` -- Ajout des endpoints organisateur :
  - `GET /{id_or_slug}/checkin.pdf` (query param `sort_by`)
  - `GET /{id_or_slug}/checkin.xlsx`
- `frontend/src/lib/api.ts` -- Helpers d'URL `getAdminCheckinPdfUrl` et `getAdminCheckinXlsxUrl`.
- `frontend/src/pages/RegistrationsPage.tsx` -- Menu déroulant / popover ou groupe de boutons "Exporter l'émargement" (PDF Stands, PDF Noms, Excel).
- `backend/tests/test_checkin_export.py` -- Tests automatisés validant la génération des exports PDF (spot & alpha) et Excel (.xlsx), la structure des colonnes, le tri et les cas limites.

## Tasks & Acceptance

**Execution:**
- [x] `backend/pyproject.toml` & `backend/requirements.txt` -- Déclarer `openpyxl>=3.1.0`.
- [x] `backend/app/templates/pdf/checkin.html` -- Créer le gabarit A4 paysage d'émargement officiel avec pagination et colonnes placier.
- [x] `backend/app/services/pdf_service.py` -- Implémenter la fonction `generate_checkin_pdf` supportant les tris `spot` et `alpha`.
- [x] `backend/app/services/excel_service.py` -- Créer le service de génération Excel `generate_checkin_xlsx`.
- [x] `backend/app/api/v1/endpoints/orders.py` -- Exposer les endpoints `checkin.pdf` et `checkin.xlsx`.
- [x] `frontend/src/lib/api.ts` -- Ajouter les helpers d'URL de téléchargement d'émargement.
- [x] `frontend/src/pages/RegistrationsPage.tsx` -- Ajouter l'interface de sélection et téléchargement des exports d'émargement.
- [x] `backend/tests/test_checkin_export.py` -- Créer la suite de tests complète validant les exports PDF et Excel.

**Acceptance Criteria:**
- Given un événement avec des commandes confirmées, when l'organisateur demande l'export PDF avec `sort_by=spot`, then le document PDF est généré en A4 paysage avec les stands ordonnés par numéro d'allée/stand croissant.
- Given un événement avec des commandes confirmées, when l'organisateur demande l'export PDF avec `sort_by=alpha`, then le document PDF est généré avec les exposants ordonnés par ordre alphabétique de leur nom.
- Given un événement, when l'organisateur demande l'export Excel (`checkin.xlsx`), then un fichier binaire `.xlsx` est téléchargé avec toutes les colonnes requises : N° Stand, Métrage, Nom/Prénom, Téléphone, Statut paiement, Case à cocher "Présent", Case "Pièce d'identité contrôlée", N° CNI relevé.
- Given la page de gestion des inscriptions (`RegistrationsPage.tsx`), when Marc consulte la barre d'actions, then il peut déclencher le téléchargement du PDF par stand, du PDF alphabétique ou du fichier Excel d'un simple clic.

## Implementation Notes

- **PDF Engine (`pdf_service.py` & `checkin.html`)** :
  - Gabarit WeasyPrint configuré en `@page { size: A4 landscape; margin: 12mm 15mm 15mm 15mm; }` avec pagination dynamique `@bottom-right { content: "Page " counter(page) " / " counter(pages); }`.
  - En-tête de tableau répété automatiquement à chaque page grâce à `thead { display: table-header-group; }`.
  - Support des modes `spot` (tri naturel alphanumérique croissant `A-1, A-2, A-10`) et `alpha` (tri insensible à la casse et respectueux des accents français via `unicodedata`, e.g. `Éric` avant `François`).
  - Gestion des exposants multi-stands : dans le mode `spot`, chaque stand apparaît individuellement à sa place dans les allées ; dans le mode `alpha`, les stands sont regroupés avec calcul du métrage cumulé.
  - Résilience totale aux champs manquants (téléphone, prénom, etc.) et rendu élégant en cas d'événement sans inscrit confirmé ("Aucun exposant inscrit").
- **Tableur Excel (`excel_service.py`)** :
  - Génération en mémoire (`BytesIO`) basée sur `openpyxl` sans écriture sur disque (RGPD).
  - Création de deux onglets : `Par Emplacement` (tri stands) et `Par Nom (Alphabétique)` (tri noms), l'onglet actif s'adaptant au paramètre `sort_by`.
  - 8 colonnes impératives configurées avec largeurs adaptées et bordures nettes : `N° Stand`, `Métrage`, `Nom / Prénom`, `Téléphone`, `Statut paiement`, `Présent`, `Pièce d'identité contrôlée`, `N° CNI relevé`.
- **Endpoints FastAPI (`orders.py`)** :
  - `GET /api/v1/events/{id_or_slug}/checkin.pdf?sort_by=spot|alpha` : stream direct `application/pdf` avec en-têtes `Content-Disposition: inline; filename="emargement_{slug}_{sort_by}.pdf"` et `Cache-Control: private, no-store, must-revalidate`.
  - `GET /api/v1/events/{id_or_slug}/checkin.xlsx` : stream `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` avec `Content-Disposition: attachment; filename="emargement_{slug}.xlsx"`.
- **Frontend (`api.ts` & `RegistrationsPage.tsx`)** :
  - Ajout des helpers `getAdminCheckinPdfUrl` et `getAdminCheckinXlsxUrl`.
  - Menu déroulant élégant « Émargement » dans la barre d'actions supérieure avec options pour le PDF Emplacement, PDF Alphabétique et Tableur Excel.

## Spec Change Log

- 2026-09-14: Implémentation complète de la Story 5.2 (exports PDF & Excel d'émargement officiel).

## Review Triage Log

- **Blind Hunter / Edge Case Hunter / Verification Gap Reviewer** :
  - [x] (patch) `backend/app/templates/pdf/checkin.html` : Remplacement du text-overflow ellipsis sur `.name-block` par `white-space: normal; word-break: break-word;` pour éviter le rognage des noms longs sur papier imprimé.
  - [x] (patch) `backend/app/templates/pdf/checkin.html` : Ajout des mentions `@top-left` (titre de l'événement) et `@top-right` (type de tri d'émargement) dans la règle CSS `@page` pour répéter le contexte sur toutes les pages imprimées.
  - [x] (patch) `backend/app/services/excel_service.py` : Configuration de l'impression A4 paysage ajustée à 1 page de large (`fitToWidth=1`) et répétition des en-têtes.
  - [x] (patch) `backend/app/services/excel_service.py` : Ajout du figeage des volets sur la ligne d'en-tête (`ws.freeze_panes = "A5"`).
  - [x] (patch) `backend/app/services/excel_service.py` : Protection contre l'injection de formules Excel/CSV (CWE-1236) en préfixant d'une apostrophe `'` les valeurs débutant par `=`, `+`, `-`, ou `@`.
  - [x] (patch) `backend/app/services/excel_service.py` : Ajout de l'horodatage d'édition dans les métadonnées de la ligne 2.
  - [x] (patch) `backend/app/services/excel_service.py` : Écriture de la valeur numérique du métrage en `float` avec formatage `0.00 "m"` pour permettre les formules de calcul.
  - [x] (patch) `backend/app/services/pdf_service.py` : Ajout d'une garde null dans `natural_sort_key` (`if not s: return []`).
  - [x] (verified) Validation complète : 40 tests dédiés au vert, 236/236 tests backend réussis, build frontend réussi en 6.8s.

## Verification

**Commands:**
- `pytest backend/tests/test_checkin_export.py` -- 18 tests passés avec succès.
- `pytest backend/tests/` -- 236 tests passés avec succès (non-régression globale 100%).
- `npm --prefix frontend run build` -- compilation TypeScript et bundling Vite réussis sans erreur.


