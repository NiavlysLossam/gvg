---
title: 'Story 8.4 - Intégration des Flux Cartographiques WMS (IGN Géoplateforme & Saisie Libre)'
type: 'feature'
created: '2026-09-20'
status: 'done'
baseline_commit: 190d21fda4ab6f62d18e5f0135d0fac1d41ba31e
route: 'dispatch'
review_loop_iteration: 1
context:
  - _bmad-output/implementation-artifacts/epic-8-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** L'éditeur de plan cartographique Leaflet/Geoman ne propose actuellement que deux fonds de plan en dur dans le code source (OSM Standard et Satellite ESRI), sans possibilité de choisir les couches officielles françaises (Photos Aériennes HR IGN, Cadastre DGFIP) ni de brancher un flux WMS personnalisé de collectivité. Les organisateurs configurant un vide-grenier en extérieur ont besoin de la précision cadastrale ou orthophoto IGN pour placer leurs stands au millimètre.

**Approach:** Étendre le modèle `Event` avec deux nouveaux champs optionnels (`wms_url`, `wms_layer`) stockés en base et exposés par l'API REST. Ajouter une migration Alembic. Sur le frontend organisateur, proposer un menu déroulant dans `SpotEditor.tsx` (et le formulaire de paramètres avancés `EventSettingsPage.tsx` / `EventForm.tsx`) listant des couches pré-intégrées (IGN Géoplateforme WMTS : Orthophoto HR, Plan IGN, Cadastre, OSM) plus une option « Flux WMS personnalisé » permettant la saisie libre de l'URL et du nom de la couche. Répercuter le fond cartographique choisi dans `PublicMap.tsx` sur la vue de réservation publique.

## Boundaries & Constraints

**Always:**
- Stocker uniquement `wms_url` (URL du serveur WMTS/WMS, max 1024 chars) et `wms_layer` (nom de la couche, max 255 chars) sur le modèle `Event`.
- Les couches pré-intégrées IGN Géoplateforme utilisent le protocole **WMTS** (tuiles pré-calculées, plus performant que WMS pour Leaflet) :
  - **Orthophoto HR** : `https://wxs.ign.fr/decouverte/geoportail/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&FORMAT=image%2Fjpeg`
  - **Plan IGN** : `https://wxs.ign.fr/decouverte/geoportail/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&STYLE=normal&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&FORMAT=image%2Fpng`
  - **Cadastre** : `https://wxs.ign.fr/decouverte/geoportail/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=CADASTRALPARCELS.PARCELLAIRE_EXPRESS&STYLE=normal&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&FORMAT=image%2Fpng`
  - **OSM Standard** : `https://tile.openstreetmap.org/{z}/{x}/{y}.png` (déjà présent, intégré dans la liste)
  - **Satellite ESRI** : `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}` (déjà présent)
- L'option « Flux WMS personnalisé » permet de saisir librement une URL Leaflet-compatible (`{z}/{x}/{y}` ou URL WMS avec paramètres) et un nom de couche affiché.
- Les champs `wms_url` / `wms_layer` sont optionnels : si null, le comportement par défaut reste OSM Standard (pas de régression).
- Le changement de couche dans `SpotEditor.tsx` est **persisté en base** via `PATCH /api/v1/events/{id}` ; ce n'est pas un état local éphémère.
- La même couche est affichée sur `PublicMap.tsx` (vue de réservation exposant) si `map_type === 'geographic'`.

**Never:**
- Ne jamais utiliser L.WMS (couche WMS Leaflet) pour les couches IGN pré-intégrées : utiliser `L.tileLayer()` avec les URLs WMTS.
- Ne jamais stocker les identifiants WMTS (clé API IGN `decouverte`) en base : la clé publique `decouverte` est intégrée en dur dans le frontend, elle est publique et sans restriction.
- Ne jamais casser le mode `map_type === 'planar'` (image de fond uploadée).
- Ne jamais exiger la saisie de `wms_layer` pour les couches pré-intégrées (elle est informative uniquement pour les couches personnalisées).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Première configuration d'un flux pré-intégré | Organisateur ouvre `SpotEditor`, sélectionne « Photos Aériennes IGN » dans le menu | La couche WMTS IGN s'affiche immédiatement sur la carte ; un `PATCH /api/v1/events/{id}` persiste `wms_url` + `wms_layer` | Toast d'erreur si PATCH échoue |
| Saisie d'un flux WMS personnalisé | Organisateur sélectionne « Flux WMS personnalisé » et saisit son URL et son nom de couche | Les tuiles s'affichent (si URL valide), persistence via PATCH | Absence de validation serveur de l'URL WMS (client-side only) ; message d'erreur de chargement Leaflet natif si URL invalide |
| Passage d'une couche à une autre | Organisateur bascule de « Cadastre » à « OSM Standard » | L'ancienne couche est retirée de la carte, la nouvelle est ajoutée ; PATCH met à jour en base | N/A |
| Réinitialisation (mode par défaut) | `wms_url` null en base | La carte charge OSM Standard sans menu pré-sélectionné | N/A |
| Vue publique exposant | `event.wms_url` non-null dans `PublicMap.tsx` | La couche configurée par l'organisateur s'affiche en lieu et place des boutons OSM/Satellite | N/A |
| Événement en mode planar | `map_type === 'planar'` | La logique WMS est complètement ignorée ; l'image de fond continue de s'afficher | N/A |

</frozen-after-approval>

## Code Map

- `backend/app/models/event.py` -- Modèle `Event` : ajouter `wms_url` (String 1024, nullable) et `wms_layer` (String 255, nullable).
- `backend/alembic/versions/010_add_wms_fields_to_events.py` -- Migration Alembic ajoutant les colonnes `wms_url` et `wms_layer` à la table `events`.
- `backend/app/schemas/event.py` -- Schémas `EventBase`, `EventUpdate`, `EventRead` : ajouter `wms_url` et `wms_layer`.
- `backend/tests/test_events_api.py` -- Tests d'intégration : création avec `wms_url`, mise à jour de la couche, lecture et réinitialisation à null.
- `frontend/src/types/event.ts` -- Interfaces `EventModel`, `EventCreateInput`, `EventUpdateInput` : ajouter `wms_url?: string | null` et `wms_layer?: string | null`.
- `frontend/src/types/public.ts` -- Interfaces `PublicEvent`, `PublicEventDetail` : ajouter `wms_url?: string | null` et `wms_layer?: string | null`.
- `frontend/src/components/SpotEditor.tsx` -- Remplacer les boutons OSM/Satellite par un menu déroulant de couches pré-intégrées + option personnalisée ; persistance via PATCH à chaque changement ; initialisation depuis `event.wms_url` au montage.
- `frontend/src/components/public/PublicMap.tsx` -- Lire `event.wms_url` pour initialiser la couche de fond sur la vue publique ; supprimer le toggle OSM/Satellite (l'organisateur a déjà choisi).

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/models/event.py` -- Ajouter `wms_url` et `wms_layer` au modèle SQLAlchemy `Event`.
- [x] `backend/alembic/versions/010_add_wms_fields_to_events.py` -- Créer la migration Alembic (upgrade : ADD COLUMN, downgrade : DROP COLUMN).
- [x] `backend/app/schemas/event.py` -- Étendre `EventBase`, `EventUpdate` et `EventRead` avec `wms_url` / `wms_layer`.
- [x] `backend/tests/test_events_api.py` -- Ajouter tests de création/mise à jour/lecture/réinitialisation des champs WMS.
- [x] `frontend/src/types/event.ts` & `frontend/src/types/public.ts` -- Ajouter les champs optionnels `wms_url` et `wms_layer`.
- [x] `frontend/src/components/SpotEditor.tsx` -- Implémenter le sélecteur de couches avec couches pré-intégrées + personnalisée, persistance PATCH, initialisation au montage.
- [x] `frontend/src/components/public/PublicMap.tsx` -- Initialiser la couche de fond depuis `event.wms_url` ; retirer le toggle OSM/Satellite.

**Acceptance Criteria:**
- Given l'éditeur de plan en mode `geographic`, when l'organisateur ouvre le sélecteur de couche, then il voit au minimum : OSM, Photos Aériennes IGN, Plan IGN, Cadastre, Satellite ESRI, et Flux WMS personnalisé.
- Given l'organisateur sélectionne « Photos Aériennes IGN », when la couche est activée, then les tuiles IGN s'affichent et un PATCH persiste `wms_url` + `wms_layer` en base.
- Given l'organisateur sélectionne « Flux WMS personnalisé » et saisit une URL Leaflet valide, when il valide, then la couche s'affiche et est persistée.
- Given `event.wms_url` non-null, when un exposant ouvre la vue publique de réservation, then la même couche que l'éditeur est affichée.
- Given `event.wms_url` null, when l'éditeur ou la vue publique est ouverte, then OSM Standard s'affiche par défaut (pas de régression).
- Given `map_type === 'planar'`, when l'éditeur est ouvert, then aucune logique WMS n'est activée.

## Implementation Notes

- Les URLs WMTS IGN Géoplateforme utilisent la clé publique `decouverte` — aucune authentification requise pour les couches listées.
- L'attribution légale des couches IGN est : `© IGN Géoplateforme` ; celle d'OSM : `© OpenStreetMap contributors`.
- Pour les couches personnalisées, l'attribution par défaut peut être vide ou fixée à `© Source WMS personnalisée`.
- L'implémentation frontend doit extraire la logique de construction du `L.tileLayer` dans une constante `PRESET_LAYERS` ou équivalent pour éviter la duplication entre `SpotEditor.tsx` et `PublicMap.tsx`. Idéalement dans un fichier partagé `src/lib/mapLayers.ts`.

## Verification

**Commands:**
- `.venv/bin/pytest backend/tests/test_events_api.py -v -k "wms"` -- expected: tous les tests WMS passent.
- `export PATH="/home/sylvain/projets/gvg/gvg/.tools/node/bin:$PATH" && npm run build --prefix frontend` -- expected: 0 erreur TypeScript ou Vite.

### Review Findings

- [x] [Review][Decision] Sélecteur WMS dans EventSettingsPage / EventForm — Résolu : conservé uniquement dans SpotEditor.tsx (choix utilisateur Option 1).
- [x] [Review][Patch] Exposer wms_url et wms_layer dans PublicEventResponse et le endpoint public [backend/app/schemas/public.py:78]
- [x] [Review][Patch] Conserver wms_url et wms_layer lors de la duplication d'événement [backend/app/api/v1/endpoints/events.py:661]
- [x] [Review][Patch] Rollback de la couche affichée et appel de onEventUpdated si le PATCH échoue [frontend/src/components/SpotEditor.tsx:291]
- [x] [Review][Patch] Validation trim() sur l'URL WMS personnalisée [frontend/src/components/SpotEditor.tsx:273]

## Spec Change Log

<!-- Append-only. Populated during review loops. -->

## Review Triage Log

- Iteration 1 (2026-09-20):
  - 1 decision-needed, 4 patches, 0 defer, 2 rejected.
  - Rejected:
    - OGC WMS via L.WMS: Rejeté car la spécification interdit formellement L.WMS et impose L.tileLayer.
    - Re-création de la carte dans PublicMap: Rejeté car les données d'un événement public sont statiques pour les visiteurs (lecture seule).


