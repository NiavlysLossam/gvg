---
title: "Story 1.2: Map Background Calibration (Satellite OSM or Indoor Floorplan)"
type: "feature"
created: "2026-09-06"
status: 'done'
baseline_commit: 'c84670291336dbfc0bf4c4a16994313a091e6dd2'
route: "dispatch"
review_loop_iteration: 0
context:
  - "_bmad-output/planning-artifacts/architecture/architecture-gvg-2026-09-04/ARCHITECTURE-SPINE.md"
  - "_bmad-output/implementation-artifacts/epic-1-context.md"
  - "_bmad-output/implementation-artifacts/spec-1-1-initialisation-projet-creation-evenement.md"
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** An event organizer (Marc) needs to configure the visual foundation on which stall spots will be drawn in Story 1.3, choosing between an outdoor georeferenced satellite/street map centered on the event venue or an indoor schematic floor plan (PNG/JPEG of a gym or village hall).

**Approach:** Implement image upload and static serving on the FastAPI backend with calibration coordinates persistence, install Leaflet in the React frontend, and build an interactive Map Calibration workspace supporting both Web Mercator OSM tile exploration and `L.CRS.Simple` indoor planar image overlays with smooth pan & zoom.

## Boundaries & Constraints

**Always:**
- Persist map configuration (`map_type`, `background_image_url`, `center_latitude`, `center_longitude`, `default_zoom`) in the PostgreSQL `events` table with an Alembic migration.
- Validate uploaded background image files: allow only image MIME types (`image/png`, `image/jpeg`, `image/webp`), enforce a maximum file size limit (10 MB), and generate collision-safe filenames.
- Serve uploaded background images through FastAPI's `StaticFiles` handler mounted at `/uploads`.
- Ensure the Leaflet container dynamically resizes and invalidates its map size on render/tab switch.
- In `planar` mode, calibrate coordinates using `L.CRS.Simple` with bounds matching the uploaded image's native pixel aspect ratio, preventing distortion.

**Never:**
- Never require third-party paid map API keys; use free OpenStreetMap tile servers (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`) and open Nominatim geocoding.
- Never block or freeze the UI during image upload or address search; provide clear loading states and error feedback.
- Never break backward compatibility with events created in Story 1.1; default coordinates center gracefully on standard French metropolitan coordinates (e.g. 46.603354, 1.888334, zoom 6) or geocoded address when unspecified.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Outdoor map calibration | Marc selects "Extérieur", enters address or moves map, clicks Save | Saves `map_type='geographic'`, `center_latitude`, `center_longitude`, and `default_zoom` via PATCH API | Displays notification if network fails |
| Valid indoor image upload | Marc uploads a 2MB PNG floorplan of the village hall | HTTP 201 with uploaded file URL (`/uploads/backgrounds/{uuid}.png`), updates `background_image_url`, displays in Leaflet `L.CRS.Simple` | Displays upload progress indicator |
| Invalid image file type | Marc uploads a `.pdf` or executable file | HTTP 415 Unsupported Media Type or 422 with clear rejection error message | Frontend displays "Format non supporté (PNG, JPEG, WebP uniquement)" |
| Image exceeding 10 MB | Marc uploads a 25 MB high-resolution image | HTTP 413 Content Too Large with clear size limit message | Rejected before upload or caught by backend limit |
| Address geocoding search | Marc enters "Place de la République Paris" in map search | Nominatim resolves coordinates, map smoothly pans and zooms to the location | Fallback to manual pan/zoom if geocoder returns 0 results |
| Missing image in planar mode | Event has `map_type='planar'` but no image uploaded yet | Displays placeholder dropzone prompting Marc to upload the schematic image | Clean UI state without Leaflet crash |

</frozen-after-approval>

## Code Map

- `backend/requirements.txt` / `backend/pyproject.toml` -- Add `python-multipart` for handling file upload endpoints.
- `backend/app/models/event.py` -- Add calibration columns (`center_latitude`, `center_longitude`, `default_zoom`) to the `Event` model.
- `backend/alembic/versions/002_add_map_calibration_to_events.py` -- Alembic migration script adding calibration columns.
- `backend/app/schemas/event.py` -- Update `EventResponse`, `EventUpdate`, and `EventCreate` with calibration fields.
- `backend/app/api/v1/endpoints/events.py` -- Add `POST /api/v1/events/{id_or_slug}/background-image` endpoint for image upload and update PATCH handler.
- `backend/app/main.py` -- Mount `StaticFiles` on `/uploads` directory to serve user-uploaded background plans.
- `backend/tests/test_map_calibration_api.py` -- Pytest test suite testing background image upload, file type/size validation, and calibration metadata updates.
- `frontend/package.json` -- Add `leaflet` (v1.9) and `@types/leaflet` dependencies.
- `frontend/src/types/event.ts` -- Update `EventModel` and `EventCreateInput` with calibration fields.
- `frontend/src/lib/api.ts` -- Add `uploadBackgroundImage(eventIdOrSlug: string, file: File)` helper function.
- `frontend/src/components/MapCalibration.tsx` -- Interactive Leaflet component supporting switching between OSM Web Mercator and `L.CRS.Simple` planar mode with image upload and address search.
- `frontend/src/App.tsx` -- Add navigation/action from the event card to open the Map Calibration view for any draft event.

## Tasks & Acceptance

**Execution:**
- [x] `backend/requirements.txt` -- Add `python-multipart` dependency -- Enables FastAPI `UploadFile` processing.
- [x] `backend/app/models/event.py` -- Extend `Event` model with `center_latitude`, `center_longitude`, `default_zoom` -- Stores map viewpoint calibration.
- [x] `backend/alembic/versions/002_add_map_calibration_to_events.py` -- Create migration for map calibration columns -- Preserves database schema integrity.
- [x] `backend/app/main.py` -- Ensure `uploads/backgrounds/` directory exists and mount `StaticFiles(directory="uploads")` on `/uploads` -- Exposes uploaded floorplans to frontend.
- [x] `backend/app/api/v1/endpoints/events.py` -- Implement `POST /api/v1/events/{id_or_slug}/background-image` with file validation (MIME type, size limit) -- Provides secure file upload.
- [x] `backend/tests/test_map_calibration_api.py` -- Write automated tests for image upload, file validation, and calibration persistence -- Validates backend robustness.
- [x] `frontend/` -- Install `leaflet` and `@types/leaflet` -- Provides mapping engine for vector and raster layouts.
- [x] `frontend/src/components/MapCalibration.tsx` -- Build Map Calibration view with Leaflet: OSM satellite/street tiles for outdoor, Nominatim address search, and `L.CRS.Simple` image overlay for indoor floorplans -- Fulfills Marc's calibration requirements.
- [x] `frontend/src/App.tsx` -- Connect Event Dashboard cards to Map Calibration view with save & back actions -- Completes the user flow from Story 1.1 into 1.2.

**Acceptance Criteria:**
- Given an existing event without a configured map background,
- When Marc opens "Configurer le plan" and selects "Extérieur", typing a venue address,
- Then Leaflet centers the map at the geocoded coordinates in Web Mercator projection with smooth zoom and pan, and clicking "Enregistrer" persists the viewpoint coordinates,
- When Marc selects "Plan de Salle / Intérieur" and uploads a PNG/JPEG plan,
- Then the image is uploaded to `/uploads/backgrounds/`, persisted in the database, and rendered in Leaflet using `L.CRS.Simple` with zoom/pan controls, ready for stall drawing in Story 1.3.

## Implementation Notes

- Added `python-multipart` dependency in `backend/requirements.txt` and `backend/pyproject.toml`.
- Extended `Event` model and Pydantic schemas with `center_latitude`, `center_longitude`, and `default_zoom`.
- Generated Alembic migration `002_add_map_calibration_to_events.py` for map calibration columns.
- Mounted FastAPI `StaticFiles` at `/uploads` backed by persistent `uploads/backgrounds/` storage.
- Implemented `POST /api/v1/events/{id_or_slug}/background-image` with MIME type enforcement (PNG, JPEG, WebP), size limit (10 MB), and UUID collision-safe filenames.
- Added comprehensive pytest test suite `backend/tests/test_map_calibration_api.py` covering all upload, validation, and calibration endpoints (all 19 tests pass).
- Installed `leaflet` and `@types/leaflet` on frontend and built `MapCalibration.tsx` component with:
  - Outdoor OSM Web Mercator mode with satellite toggle, Nominatim address search, and marker drag & drop.
  - Indoor `L.CRS.Simple` planar mode with drag & drop file upload, aspect-ratio preservation, and boundary clamping.
  - Smooth pan/zoom synchronization, proper Leaflet cleanup (`map.remove()`), and dynamic size invalidation.
- Connected EventCard dashboard to MapCalibration workspace with save and back navigation in `App.tsx`.

## Spec Change Log

## Review Triage Log

| ID | Location | Verdict | Evidence | Route |
|---|---|---|---|---|
| EC-1 | frontend/src/components/MapCalibration.tsx:243 | medium | Async image loading race condition and duplicate Leaflet map instantiation on container. Added active mounted flag. | patch |
| EC-2 | frontend/src/components/MapCalibration.tsx:273 | medium | Missing img.onerror handler when background image URL fails to load. Added error callback and user feedback. | patch |
| EC-3 | frontend/src/components/MapCalibration.tsx:397 | low | User zooming out to level 0 causes backend HTTP 422 validation failure on default_zoom < 1. Clamped default_zoom to [1, 22]. | patch |
| EC-4 | frontend/src/components/MapCalibration.tsx:396 | low | Horizontal map pan past antimeridian (-180 or 180 degrees) causes HTTP 422 on center_longitude. Wrapped longitude to [-180, 180]. | patch |
| EC-5 | frontend/src/components/MapCalibration.tsx:690 | low | File input onChange does not fire when re-selecting the same file. Added e.target.value = ''. | patch |
| EC-6 | frontend/src/components/MapCalibration.tsx:205 | low | Marker dragging conflicts with map moveend resetting marker to map center. Added map.panTo on dragend. | patch |
| BH-1 | backend/app/api/v1/endpoints/events.py:270 | medium | MIME type check relied solely on client Content-Type header. Added magic byte verification for PNG, JPEG, WebP. | patch |
| BH-2 | backend/app/api/v1/endpoints/events.py:275 | low | Blocking synchronous file write and lack of rollback on database commit failure. Added run_in_threadpool and file cleanup. | patch |
| BH-3 | frontend/src/components/MapCalibration.tsx:389 | low | Submitting planar mode without an uploaded image saves planar with null background_image_url. Added frontend validation check. | patch |
| BH-4 | frontend/src/components/MapCalibration.tsx:147 | low | Auto-geocoding strict null equality failed on undefined. Added null or undefined check. | patch |
| BH-5 | frontend/src/components/MapCalibration.tsx:470 | low | Internal agile identifier 'Story 1.2' displayed in user-facing header. Replaced with 'Fond de plan'. | patch |
| BH-6 | frontend/src/components/MapCalibration.tsx | low | Non-existent Tailwind classes shadow-xs and backdrop-blur-xs. Replaced with shadow-sm and backdrop-blur-sm. | patch |
| BH-7 | backend/tests/test_map_calibration_api.py | low | Missing test verifying rejection of spoofed image MIME type. Added test_upload_spoofed_mime_type_fails_magic_bytes. | patch |
| BH-8 | backend/app/models/event.py | low | Planar native pixel dimensions not stored in database. Defer to Story 1.3 vector drawing if needed. | defer |
| BH-9 | backend/app/api/v1/endpoints/events.py | low | Orphan file accumulation upon repeated background image replacement. Defer to future maintenance cron. | defer |


## Design Notes

- **Leaflet in React:** Wrap the map in a container with a unique ID or `useRef<HTMLDivElement>`, handling cleanup (`map.remove()`) and triggering `map.invalidateSize()` after mounting or switching modes.
- **Planar Coordinate System (`L.CRS.Simple`):** Load image natural dimensions `(naturalWidth, naturalHeight)`. Set map bounds `[[0, 0], [naturalHeight, naturalWidth]]`, set `maxBounds`, and invoke `map.fitBounds(bounds)` with `minZoom: -2` to enable comfortable zooming.
- **Geocoding:** Use standard fetch to OpenStreetMap Nominatim `https://nominatim.openstreetmap.org/search?format=json&q=...` with appropriate user-agent header.
