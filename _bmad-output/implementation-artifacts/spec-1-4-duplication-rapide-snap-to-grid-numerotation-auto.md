---
title: "Story 1.4: Rapid Duplication, Snap-to-Grid & Automatic Numbering"
type: "feature"
created: "2026-09-12"
status: 'done'
baseline_commit: '61ade62b2ec0a29ebe514ca0748bf8afee17e3c5'
route: "dispatch"
review_loop_iteration: 1
context:
  - "_bmad-output/planning-artifacts/architecture/architecture-gvg-2026-09-04/ARCHITECTURE-SPINE.md"
  - "_bmad-output/implementation-artifacts/epic-1-context.md"
  - "_bmad-output/implementation-artifacts/spec-1-3-dessin-vectoriel-emplacements-leaflet-geoman.md"
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Configuring an entire flea market venue containing dozens or hundreds of stalls by drawing each rectangle individually is slow, tedious, and error-prone. Organizers (Marc) need to quickly duplicate rows of aligned stalls with edge-to-edge magnetic snapping and sequentially number entire aisles in seconds.

**Approach:** Implement batch creation and atomic renumbering endpoints on the FastAPI backend, integrate Geoman magnetic snapping (`snappable`), and add a fast duplication toolbar & multi-stand renumbering dialog in the React Spot Editor, ensuring absolute SQL uniqueness of stall numbers within each event.

## Boundaries & Constraints

**Always:**
- Ensure strict database uniqueness of spot labels per event enforced by the existing SQL unique constraint `uq_spots_event_id_label`.
- Provide edge-to-edge duplication ("Dupliquer × N") aligning new stalls along the orientation vector of the selected stand (or cardinal directions) with 0-gap edge snapping by default.
- Support batch creation via `POST /api/v1/events/{id}/spots/batch` creating $N$ stalls atomically in a single database transaction.
- Support batch renumbering via `POST /api/v1/events/{id}/spots/batch-renumber` with customizable aisle prefix (e.g. "Allée A - "), start index, and 2-digit zero-padding.
- Enable Geoman magnetic snapping (`snappable: true`, configurable snap distance) on drag and draw operations to automatically snap stall edges and vertices to adjacent stands.
- When an automatic or manual renumbering collides with an existing label within the same event, return HTTP 409 Conflict with an informative message and roll back atomically.

**Never:**
- Never create overlapping duplicate stalls when edge-to-edge duplication is requested.
- Never leave orphan or partially inserted stalls if a batch operation fails midway; all batch operations must be atomic transactions.
- Never allow batch operations on spots belonging to another event (enforce strict event ownership).
- Never allow non-positive linear meters or negative prices on duplicated stalls; each clone inherits the source stand's linear meters and recalculates or preserves price.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Duplicate × N along aisle | Marc selects 2m stand, clicks "Dupliquer × 10", direction "Droite (Axe stand)", prefix "Allée A - ", start "1" | 10 new 2m stands created edge-to-edge aligned with source, labeled `Allée A - 01` to `Allée A - 10`, HTTP 201 with FeatureCollection | Rolls back all 10 stands if any label conflicts |
| Magnetic snapping on drag | Marc moves a stand close to another stand's border | Geoman magnetizes the vertex/edge to the neighbor within snap distance (e.g. 15px) | Snapping smoothly releases when dragged beyond snap threshold |
| Batch renumbering of selected stands | Marc selects 5 stands and submits prefix="Allée B - ", start=1, pad=2 | Labels updated to `Allée B - 01` ... `Allée B - 05` via atomic batch endpoint | Reverts all updates if conflict occurs |
| Duplicate label conflict | Duplication or renumbering generates a label that already exists in the event | HTTP 409 Conflict with message indicating the conflicting label (e.g. "Le stand « Allée A - 01 » existe déjà") | Frontend displays explicit alert without desynchronizing map |
| Planar mode duplication | Event is in planar indoor mode (hall floorplan) | Duplication offsets pixel coordinates along planar geometry without coordinate transformation | Stalls properly positioned on image coordinates |
| Multi-stand selection | Marc holds Shift or activates "Sélection multiple" tool and clicks several stands | Selected stands display highlighted active boundary and can be batch renumbered or batch deleted | Clicking map background clears multi-selection |

</frozen-after-approval>

## Code Map

- `backend/app/schemas/spot.py` -- Add `SpotBatchCreate` and `SpotBatchRenumber` request and response schemas.
- `backend/app/api/v1/endpoints/spots.py` -- Implement `POST /api/v1/events/{id_or_slug}/spots/batch` and `POST /api/v1/events/{id_or_slug}/spots/batch-renumber`.
- `backend/tests/test_spots_api.py` -- Add test cases for atomic batch creation, duplicate collision rollback, batch renumbering, and multi-event isolation.
- `frontend/src/types/spot.ts` -- Add types for `SpotBatchCreateInput`, `SpotBatchRenumberInput`, and duplicate direction options.
- `frontend/src/lib/api.ts` -- Add `createSpotsBatch` and `renumberSpotsBatch` API methods.
- `frontend/src/components/SpotEditor.tsx` -- Enable Geoman snapping (`snappable: true`), add duplication modal/controls, multi-selection handling, and toolbar buttons.
- `frontend/src/components/DuplicateSpotModal.tsx` -- Interactive dialog for configuring duplication count $N$, direction (stand axis vs cardinal), spacing, and sequential numbering prefix.
- `frontend/src/components/BatchRenumberModal.tsx` -- Modal for renumbering currently selected stands with preview of generated labels.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/schemas/spot.py` -- Define schemas for batch spot creation and batch renumbering -- Standardizes batch I/O payload validation.
- [x] `backend/app/api/v1/endpoints/spots.py` -- Implement atomic batch creation and batch renumbering endpoints with SQL uniqueness enforcement -- Prevents partial inserts and duplicate labels.
- [x] `backend/tests/test_spots_api.py` -- Add comprehensive tests for batch creation, batch renumbering, rollback on unique constraint violation, and planar coordinate support -- Validates backend robustness.
- [x] `frontend/src/types/spot.ts` & `frontend/src/lib/api.ts` -- Define batch interfaces and API client functions -- Extends frontend network layer.
- [x] `frontend/src/components/DuplicateSpotModal.tsx` -- Create duplication dialog with count $N$, stand axis/cardinal direction, spacing, and numbering prefix -- Implements "Dupliquer × N" requirement.
- [x] `frontend/src/components/BatchRenumberModal.tsx` -- Create batch renumbering modal with prefix, start index, zero-padding, and label preview -- Implements sequential aisle numbering.
- [x] `frontend/src/components/SpotEditor.tsx` -- Integrate Geoman snapping options (`snappable: true`), multi-selection mode, and connect duplication and renumbering modals -- Completes end-to-end user workflow.

**Acceptance Criteria:**
- Given a calibrated event with a 2m stand selected on the map,
- When Marc clicks "Dupliquer × N", specifies count 10, selects stand axis direction, and enters prefix "Allée A - " with start 1,
- Then 10 new 2m stands are created edge-to-edge in a single atomic request, sequentially numbered `Allée A - 01` to `Allée A - 10`,
- And dragging any stand near another snaps magnetically to its edges without overlapping,
- When Marc selects a group of stands and submits batch renumbering with prefix "Allée B - " and start 1,
- Then all selected stands are sequentially updated, with database uniqueness strictly guaranteed.

## Implementation Notes

- Added `SpotBatchCreate`, `SpotBatchCreateResponse`, `SpotRenumberItem`, `SpotBatchRenumber`, and `SpotBatchRenumberResponse` Pydantic schemas in `backend/app/schemas/spot.py`.
- Implemented `POST /api/v1/events/{id_or_slug}/spots/batch` and `POST /api/v1/events/{id_or_slug}/spots/batch-renumber` in `backend/app/api/v1/endpoints/spots.py`:
  - Enforced atomic single-transaction execution with automatic rollback on duplicate label collision.
  - Implemented two-phase atomic renumbering using temporary unique UUID labels to prevent intermediate unique constraint collisions when swapping or shifting numbers.
  - Verified strict event ownership and returned GeoJSON `FeatureCollection` responses.
- Added comprehensive pytest test cases in `backend/tests/test_spots_api.py` covering batch creation, duplicate collision rollback within batch and against existing spots, planar coordinates, sequential renumbering with prefix/padding, two-phase shift/swap renumbering, conflict rollback, and cross-event isolation. All 43 backend tests pass.
- Added batch and duplication TypeScript interfaces in `frontend/src/types/spot.ts` and API functions `createSpotsBatch` and `renumberSpotsBatch` in `frontend/src/lib/api.ts`.
- Created `DuplicateSpotModal.tsx` supporting duplication count $N$, stand axis orientation vector calculation (with 0-gap edge snapping or custom spacing), cardinal directions, sequential label prefix/start/padding, and live label preview.
- Created `BatchRenumberModal.tsx` for multi-stand renumbering with customizable prefix, start index, zero-padding, and before/after mapping preview.
- Integrated magnetic snapping (`snappable: true`, configurable distance 10-30px), multi-selection mode (Shift-click and toolbar toggle), and floating batch actions bar into `SpotEditor.tsx`.
- Successfully verified full TypeScript compilation and Vite build with zero errors.

## Spec Change Log

## Review Triage Log

- **Patch:** Added explicit `price_cents` override persistence verification in `backend/tests/test_spots_api.py` to ensure custom stall pricing is preserved over fallback meter calculation.
- **Patch:** Added multi-spot atomic rollback verification under label conflict in `backend/tests/test_spots_api.py`.
- **Patch:** Enforced `max_length=500` on batch payloads and `max_length=80` on renumbering prefix in `backend/app/schemas/spot.py`.
- **Patch:** Enforced duplicate spot ID validation in `SpotBatchRenumber` schema (HTTP 422).
- **Patch:** Enforced label length validation ($\le 100$ characters) in `SpotBatchRenumber` to prevent database `DataError`.
- **Patch:** Sanitized cross-event rejection error messages to avoid disclosing stall labels from foreign events.
- **Patch:** Preserved user selection click order when passing spots to `BatchRenumberModal` in `SpotEditor.tsx`.
- **Patch:** Improved client-side partial failure resilience in `handleBatchDelete` in `SpotEditor.tsx`.
- **Patch:** Fixed floating action bar horizontal centering animation CSS conflict in `SpotEditor.tsx`.
- **Defer:** Server-side atomic batch delete endpoint (deferred to Epic 2/3 as individual deletion with client-side synchronization satisfies current requirements).

## Design Notes

- **Stand-Relative Vector Offset:**
  Given a 4-point rectangle polygon $[(x_0, y_0), (x_1, y_1), (x_2, y_2), (x_3, y_3), (x_0, y_0)]$, the primary width vector is $\vec{u} = (x_1 - x_0, y_1 - y_0)$. Shifting by $k \cdot \vec{u}$ creates perfectly adjacent edge-to-edge stands regardless of stand rotation angle.
- **Two-Phase Atomic Renumbering:**
  To renumber stands without triggering intermediate unique constraint violations (e.g. when shifting or swapping existing numbers like 1->2 and 2->3), execute in two phases within a single transaction: first assign temporary unique UUID prefixes (`__tmp_{uuid}_1`), then update to final formatted labels.

## Verification

**Commands:**
- `.venv/bin/pytest backend/tests/` -- expected: All unit & integration tests pass on PostgreSQL PostGIS.
- `PATH="$(pwd)/.tools/node/bin:$PATH" npm --prefix frontend run build` -- expected: TypeScript typecheck and Vite build succeed with zero errors.

**Manual checks (if no CLI):**
- Open Spot Editor, select a stand, duplicate 10 times along aisle with prefix "Allée A - ", test magnetic edge snapping, and verify labels `Allée A - 01` through `Allée A - 10`.

