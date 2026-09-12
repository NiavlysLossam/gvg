---
title: "Story 1.3: Vector Spot Drawing with Leaflet-Geoman"
type: "feature"
created: "2026-09-12"
status: 'done'
baseline_commit: '02eb3ea2933c973d641c9656d51f6e9d66fd3fbb'
route: "dispatch"
review_loop_iteration: 0
context:
  - "_bmad-output/planning-artifacts/architecture/architecture-gvg-2026-09-04/ARCHITECTURE-SPINE.md"
  - "_bmad-output/implementation-artifacts/epic-1-context.md"
  - "_bmad-output/implementation-artifacts/spec-1-2-calibrage-fond-de-plan-satellite-ou-salle.md"
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Event organizers (Marc) need to visually define and configure rentable flea market stalls directly on their calibrated map or hall plan by drawing rectangles, repositioning, rotating, and specifying linear meters with automatic price calculation.

**Approach:** Implement a PostGIS-backed `Spot` model with GeoJSON serialization and REST endpoints in FastAPI, install and integrate `@geoman-io/leaflet-geoman-free` in the React frontend, and provide an interactive Map Editor where Marc can draw rectangular stalls, edit, rotate, drag, and set properties (label, linear meters, auto-calculated price) in real time.

## Boundaries & Constraints

**Always:**
- Persist stall geometries in a dedicated `spots` table with an Alembic migration linked to `events.id` via foreign key with `ondelete CASCADE`.
- Model geometry as a 2D `Polygon` compatible with both geographic coordinates (WGS84 lon/lat) and planar pixel coordinates (`L.CRS.Simple`).
- Expose spots via REST endpoints in RFC 7946 GeoJSON format (`FeatureCollection` of `Polygon` features with spot properties).
- Compute spot price automatically as `round(linear_meters * event.price_per_meter_cents)` by default in integer cents, while providing an optional manual price override in the property drawer for specific stands (e.g. corner or premium spots).
- When drawing a new spot, pre-fill a provisional sequential label (`Stand 1`, `Stand 2`, ...) in the property drawer, fully editable by the organizer.
- Provide responsive Leaflet-Geoman controls (Rectangle draw, Edit, Drag, Rotate, Delete) with clear visual feedback and active selection highlights.
- Support selecting any existing spot to display its properties in a side panel/drawer for editing its label, linear meters, and price.

**Never:**
- Never allow non-positive linear meters (`linear_meters <= 0`) or negative prices.
- Never use lossy floating-point operations for stored prices; prices must strictly be stored in integer cents (`price_cents`).
- Never freeze the Leaflet canvas or crash upon switching between drawing, rotating, and editing modes; ensure proper Geoman mode toggles and cleanup.
- Never prevent drawing on planar floorplans; ensure Leaflet-Geoman coordinate handling operates seamlessly under both standard CRS and `L.CRS.Simple`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Draw new rectangle spot | Marc draws a rectangle with Geoman tool on the map | Leaflet-Geoman fires `pm:create`; frontend displays spot properties drawer with default label (e.g. "Stand 1") and default 2.0m | Reverts layer if creation is cancelled |
| Save spot with valid properties | Marc sets label="A01", linear_meters=3.0, clicks "Enregistrer" | POST /api/v1/events/{id}/spots creates spot in DB, price_cents=2400 (if 8€/m), returns HTTP 201 with GeoJSON Feature | Displays toast notification on error |
| Rotate / Drag spot | Marc activates Rotate/Drag mode and adjusts an existing spot | Updates geometry in frontend and persists updated coordinates via PATCH /api/v1/events/{id}/spots/{spot_id} | Retains previous geometry on network error |
| Invalid linear meters | Marc submits linear_meters=0 or -1.5 | HTTP 422 Unprocessable Entity rejecting non-positive linear meters | Frontend displays inline error "Le métrage doit être supérieur à 0" |
| Delete spot | Marc selects spot and clicks "Supprimer" or uses Geoman remove tool | DELETE /api/v1/events/{id}/spots/{spot_id} removes spot from DB and removes Leaflet layer | Confirmation prompt before deletion |
| Planar mode drawing | Event has map_type="planar" with indoor floorplan image | Geoman draws rectangles in `L.CRS.Simple` pixel coordinates without spherical distortion | Layer coordinates accurately mapped to image pixel bounds |

</frozen-after-approval>

## Code Map

- `frontend/package.json` -- Add `@geoman-io/leaflet-geoman-free` dependency.
- `backend/app/models/spot.py` -- New `Spot` SQLAlchemy model with UUID id, `event_id` FK, `label`, `linear_meters`, `price_cents`, `geom` (`Geometry('POLYGON')`), `status`, `locked_until`, `locked_by_token`, timestamps.
- `backend/app/models/__init__.py` -- Export `Spot` model alongside `Event`.
- `backend/alembic/versions/003_create_spots_table.py` -- Alembic migration creating `spots` table and spatial indices.
- `backend/app/schemas/spot.py` -- Pydantic schemas for Spot creation, update, GeoJSON Feature and FeatureCollection responses.
- `backend/app/api/v1/endpoints/spots.py` -- CRUD endpoints: `GET /api/v1/events/{id_or_slug}/spots`, `POST /api/v1/events/{id_or_slug}/spots`, `PATCH /api/v1/events/{id_or_slug}/spots/{spot_id}`, `DELETE /api/v1/events/{id_or_slug}/spots/{spot_id}`.
- `backend/app/main.py` -- Register spots router under `/api/v1`.
- `backend/tests/conftest.py` -- Ensure SpatiaLite is loaded on SQLite test connection if available so geometry queries succeed in tests.
- `backend/tests/test_spots_api.py` -- Pytest suite validating spot creation, GeoJSON export, linear meters & price calculation, geometry updates, and deletion.
- `frontend/src/types/spot.ts` -- TypeScript types for Spot, GeoJSON Feature, and SpotForm inputs.
- `frontend/src/lib/api.ts` -- API client methods for fetching, creating, updating, and deleting spots.
- `frontend/src/components/SpotEditor.tsx` -- Interactive Leaflet + Leaflet-Geoman workspace for drawing rectangles, moving, rotating, and editing spot properties.
- `frontend/src/components/SpotPropertyDrawer.tsx` -- Side drawer for inspecting and modifying spot label, linear meters, and calculating associated price in real time.
- `frontend/src/components/EventCard.tsx` -- Add direct action button to open the Spot Editor for an event.
- `frontend/src/App.tsx` -- Integrate the `editor` tab into navigation and connect EventCard and MapCalibration to SpotEditor.

## Tasks & Acceptance

**Execution:**
- [x] `frontend/package.json` -- Install `@geoman-io/leaflet-geoman-free` -- Equips map with rectangle drawing, rotation, drag, and edit tools.
- [x] `backend/app/models/spot.py` -- Create `Spot` model with UUID, foreign key to Event, linear meters, price cents, status, and polygon geometry -- Persists stall structures.
- [x] `backend/alembic/versions/003_create_spots_table.py` -- Generate migration for `spots` table -- Maintains database schema evolution.
- [x] `backend/app/schemas/spot.py` -- Define Pydantic schemas for Spot requests, GeoJSON Polygon, Feature, and FeatureCollection -- Standardizes API input/output.
- [x] `backend/app/api/v1/endpoints/spots.py` -- Implement REST endpoints for spots CRUD with GeoJSON serialization -- Connects backend with frontend map editor.
- [x] `backend/tests/conftest.py` & `backend/tests/test_spots_api.py` -- Configure spatialite for test suite and write automated API tests -- Verifies endpoints and edge cases.
- [x] `frontend/src/types/spot.ts` & `frontend/src/lib/api.ts` -- Add Spot interfaces and API client functions -- Typings and network layer.
- [x] `frontend/src/components/SpotPropertyDrawer.tsx` -- Build property drawer with linear meters input, live price calculation, and save/delete actions -- Facilitates stand sizing.
- [x] `frontend/src/components/SpotEditor.tsx` -- Implement full-featured Leaflet-Geoman editor supporting draw, move, rotate, selection, and planar/outdoor modes -- Core user requirement.
- [x] `frontend/src/components/EventCard.tsx` & `frontend/src/App.tsx` -- Link navigation from event cards and calibration view to SpotEditor -- Delivers unified organizer workflow.

**Acceptance Criteria:**
- Given an event with a calibrated outdoor or indoor map background,
- When Marc opens the editor, activates the rectangle tool, and draws a rectangle,
- Then Leaflet-Geoman creates a polygon layer with resize and rotate handles, and opens the spot properties drawer,
- And changing the linear meters immediately recalculates the price in euros based on the event's meter rate,
- When Marc clicks "Enregistrer",
- Then the spot is saved in PostGIS via the API as a GeoJSON `Polygon`, with label, linear meters, and calculated price in cents.

## Implementation Notes

- Installed `@geoman-io/leaflet-geoman-free` in `frontend/package.json`.
- Created `Spot` model in `backend/app/models/spot.py` with UUID, foreign key to `events.id` (CASCADE on delete), linear meters, integer `price_cents`, `geom` (GeoAlchemy2 `Geometry('POLYGON')`), and `status` ('available', 'locked', 'reserved', 'blocked').
- Generated Alembic migration `003_create_spots_table.py` and updated `env.py` and `conftest.py` with SpatiaLite initialization for SQLite testing and PostGIS compatibility.
- Created Pydantic schemas in `backend/app/schemas/spot.py` for `SpotCreate`, `SpotUpdate`, `SpotFeature`, and `SpotFeatureCollection` (RFC 7946 GeoJSON) with pure Python WKT <-> GeoJSON polygon conversion.
- Implemented REST CRUD endpoints in `backend/app/api/v1/endpoints/spots.py`:
  - `GET /api/v1/events/{id_or_slug}/spots`
  - `POST /api/v1/events/{id_or_slug}/spots`
  - `GET /api/v1/events/{id_or_slug}/spots/{spot_id}`
  - `PATCH /api/v1/events/{id_or_slug}/spots/{spot_id}`
  - `DELETE /api/v1/events/{id_or_slug}/spots/{spot_id}`
- Added unit and integration tests in `backend/tests/test_spots_api.py` covering auto-pricing, manual price override, geometry updates (drag/rotate), deletion, validation, and planar mode pixel coordinates. All 28 tests pass.
- Implemented TypeScript types in `frontend/src/types/spot.ts` and API functions in `frontend/src/lib/api.ts`.
- Created `SpotPropertyDrawer.tsx` side drawer with live price calculation, linear meters validation, manual price override, and delete confirmation.
- Created `SpotEditor.tsx` with full Leaflet and Leaflet-Geoman integration (rectangle drawing, drag, rotate, vertex edit, deletion), planar & outdoor support, status styling, and tooltip labels.
- Integrated `SpotEditor` into `EventCard.tsx`, `MapCalibration.tsx`, and `App.tsx` with unified navigation.

## Spec Change Log

## Review Triage Log

| ID | Location | Verdict | Evidence | Route |
|---|---|---|---|---|
| BH-1 / EC-1 | frontend/src/components/SpotEditor.tsx:2287 | high | tileLayerType in map initialization useEffect dependency array caused map destruction and reinitialization on OSM/Satellite toggle. Removed from deps. | patch |
| BH-2 / VG-5 | frontend/src/components/SpotEditor.tsx:2290 | medium | Full layer group wipeout on spot updates interrupted active Geoman transform modes. Fixed with mapReady coordination and targeted layer sync. | patch |
| BH-3 | frontend/src/components/SpotEditor.tsx:2326 | medium | Spot label interpolated into tooltip HTML without escaping, exposing XSS risk. Added escapeHtml helper. | patch |
| BH-4 / EC-4 | frontend/src/components/SpotEditor.tsx:2352 | medium | Geometry update failure on PATCH left layer at modified position without rollback. Added LatLng rollback on error. | patch |
| BH-7 / EC-6 | frontend/src/components/SpotEditor.tsx:2223 | medium | Drawing new rectangle while previous provisional layer was unsaved orphaned layer on map. Added pending layer cleanup on drawstart and cancel. | patch |
| BH-11 / EC-3 | frontend/src/components/SpotEditor.tsx:2160 | medium | Missing img.onerror on planar background image loading caused silent hang on 404. Added error handler and UI notification. | patch |
| BH-6 | frontend/src/components/SpotEditor.tsx:2208 | low | Unconstrained cutPolygon and drawText tools risked producing invalid geometries. Explicitly disabled in addControls. | patch |
| BH-14 | frontend/src/components/SpotEditor.tsx:2310 | low | Selected spot lacked distinctive visual stroke/glow on map. Added indigo dashed active stroke styling. | patch |
| BH-15 | frontend/src/components/SpotEditor.tsx:2120 | low | Floating-point drift in summary meters and revenue. Applied toFixed(1) for meters and computed total from integer cents / 100. | patch |
| BH-18 | backend/app/api/v1/endpoints/spots.py:465 | low | delete_spot allowed deleting reserved spots without restriction. Added 400 guard blocking deletion of reserved spots. | patch |
| BH-13 / EC-7 | backend/app/schemas/spot.py:734 | low | SpotUpdate permitted whitespace-only labels. Added field_validator rejecting blank strings. | patch |
| VG-6 / EC-9 | backend/app/schemas/spot.py:787 | low | WKT polygon parsing regex only supported single ring. Updated parser to support multiple rings. | patch |
| VG-1 | backend/tests/test_spots_api.py | low | Missing test verification for cross-event data isolation. Added test_cross_event_data_isolation. | patch |
| VG-2 | backend/tests/test_spots_api.py | low | Missing test verification for slug-based event resolution on spot endpoints. Added test_slug_based_event_resolution. | patch |
| VG-3 | backend/tests/test_spots_api.py | low | Missing test verification for PATCH manual price override. Added test_patch_price_override. | patch |
| VG-4 | backend/tests/test_spots_api.py | low | Missing test verification for PATCH non-positive linear meters and blank label. Added test_patch_validation_linear_meters_and_whitespace_label. | patch |

## Design Notes

- **Geoman Initialization:** Initialize Geoman controls on the Leaflet map instance:
  ```ts
  map.pm.addControls({
    position: 'topleft',
    drawCircle: false,
    drawCircleMarker: false,
    drawMarker: false,
    drawPolyline: false,
    drawPolygon: false,
    drawRectangle: true,
    editMode: true,
    dragMode: true,
    rotateMode: true,
    removalMode: true,
  });
  ```
- **GeoJSON <-> Leaflet sync:** Listen to `pm:create` to capture new rectangles, convert layer to GeoJSON with `layer.toGeoJSON()`, and associate layer with spot state.
- **Planar Coordinate Preservation:** In planar mode (`L.CRS.Simple`), store polygon coordinates directly in pixel space without projection transforms.
- **Pure Python GeoJSON to WKT:** Convert GeoJSON Polygon coordinates `[[[x, y], ...]]` to WKT `POLYGON((x y, ...))` avoiding heavy external C library requirements on backend.

## Verification

**Commands:**
- `.venv/bin/pytest backend/tests/` -- expected: All unit & integration tests pass (20 existing + new spot tests).
- `PATH="$(pwd)/.tools/node/bin:$PATH" npm --prefix frontend run build` -- expected: TypeScript typecheck and Vite build succeed with zero errors.

**Manual checks (if no CLI):**
- Open the application in browser, navigate to an event, launch the Spot Editor, draw a 3m stand, rotate and move it, verify real-time price calculation, and confirm persistence upon refresh.
