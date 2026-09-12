---
title: "Story 2.1: Public Interactive Map Consultation (Mobile-First)"
type: "feature"
created: "2026-09-12"
status: 'done'
baseline_commit: '43dc3c5a729bdca5c0825ba42c6436853ccc6930'
route: "dispatch"
review_loop_iteration: 0
context:
  - "_bmad-output/planning-artifacts/architecture/architecture-gvg-2026-09-04/ARCHITECTURE-SPINE.md"
  - "_bmad-output/implementation-artifacts/epic-2-context.md"
  - "_bmad-output/planning-artifacts/ux-designs/ux-gvg-2026-09-04/DESIGN.md"
  - "_bmad-output/planning-artifacts/ux-designs/ux-gvg-2026-09-04/EXPERIENCE.md"
  - "_bmad-output/planning-artifacts/epics.md"
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Prospective exhibitors (like Monique) and event attendees need to view the live flea market venue map on their smartphones or computers without being required to log in or create an account. They must easily locate available stalls, understand pricing and dimensions, and navigate the map intuitively with standard touch gestures.

**Approach:** Expose dedicated unauthenticated public REST endpoints (`GET /api/v1/public/events/{slug}` and `GET /api/v1/public/events/{slug}/spots` with automatic lazy lock expiration), and implement a dedicated responsive, mobile-first public map view in React (`/e/:slug`) featuring semantic status coloring (Emerald `#10B981` for available, Amber `#F59E0B` for locked, Slate `#9CA3AF` for reserved), fluid pinch-to-zoom navigation, a 1-tap floating recenter button, and a touch-friendly stall detail infobulle / bottom drawer.

## Boundaries & Constraints

**Always:**
- Ensure all public endpoints (`/api/v1/public/events/*`) are accessible without authentication, tokens, or cookies.
- Return effective real-time stall statuses: if a stall has `status == 'locked'` but `locked_until < now()`, return it with effective status `'available'`.
- Support both outdoor maps (satellite imagery / OpenStreetMap) and indoor floorplans (`L.CRS.Simple`) seamlessly based on the event's calibration metadata.
- Follow Sally's UX semantic palette (`DESIGN.md`):
  - Available: Emerald green (`#10B981`, border `#059669`)
  - Locked (in another user's cart): Amber (`#F59E0B`, border `#D97706`)
  - Reserved / Blocked: Slate gray (`#9CA3AF`, border `#6B7280`)
- Implement a floating 1-tap recenter button (`fitBounds`) allowing users to easily re-align the map view to the venue bounding box.
- Tap/click on an available stall displays an infobulle / bottom sheet showing: stall label, linear meters, and total price in euros formatted in French locale (`4,00 €`).
- Provide an accessible status legend (Available, Under reservation, Reserved) directly visible on mobile and desktop.
- Support URL routing for `/e/:slug` directly in the React frontend application.

**Never:**
- Never display organizer editing controls, Geoman palettes, or administrative buttons on the public map page.
- Never expose sensitive private data (such as exhibitor personal details, session tokens, or transaction IDs) in the public GeoJSON response.
- Never block mobile touch scrolling outside the map; the map container must handle pinch-to-zoom and pan smoothly with standard Leaflet touch event listeners.
- Never mutate database records during read-only public queries; expired locks are computed dynamically during query time.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Public page load | Visitor navigates to `/e/vide-grenier-saint-michel` | Loads event details and renders public map centered on event bounds with all stalls colored by status | Shows user-friendly 404 screen if event slug does not exist |
| Expired lock query | Stall has `status='locked'` and `locked_until = now() - 2 min` | GeoJSON properties return `status: "available"` without waiting for a cleanup worker | Computed via SQL `CASE WHEN status = 'locked' AND locked_until < NOW() THEN 'available' ELSE status END` |
| Tap on available stall | Visitor taps a green stall (`#10B981`) on smartphone | Highlights stall boundary, opens bottom sheet / popup with label, meters, price, and "Disponible" badge | Tap outside dismisses sheet |
| Tap on reserved stall | Visitor taps a gray stall (`#9CA3AF`) | Opens popup showing label and "Emplacement déjà réservé" message without pricing CTA | Non-interactive for purchase |
| Tap on locked stall | Visitor taps an amber stall (`#F59E0B`) | Opens popup showing "Réservation en cours (verrouillé temporairement)" | Informs visitor that the stall might become available if unpaid |
| Indoor hall event | Event configured with `background_type: 'indoor'` | Renders using `L.CRS.Simple` with indoor image overlay and bounds | Prevents geographic tile loading errors |
| Recenter button click | Visitor pans/zooms away from stalls | Clicking floating target button resets map view with smooth animation to `fitBounds(allStalls)` | If 0 stalls exist, centers on event default location |
| Network error during refresh | Visitor clicks refresh or network drops | Displays discreet toast/banner "Impossible de rafraîchir le plan" while preserving current map view | Retains cached state |

</frozen-after-approval>

## Code Map

- `backend/app/schemas/public.py` -- Public Pydantic schemas: `PublicEventResponse`, `PublicSpotProperties`, `PublicSpotFeature`, and `PublicSpotFeatureCollection`.
- `backend/app/api/v1/endpoints/public.py` -- Public unauthenticated endpoints:
  - `GET /api/v1/public/events/{slug}`: Public event metadata (title, dates, hours, location, background settings).
  - `GET /api/v1/public/events/{slug}/spots`: GeoJSON `FeatureCollection` with effective statuses and pricing.
- `backend/app/api/v1/router.py` -- Mount `/public` router in FastAPI v1 API.
- `backend/tests/test_public_api.py` -- Comprehensive Pytest suite testing public event retrieval, GeoJSON spot generation, lazy lock expiration, and 404 handling.
- `frontend/src/types/public.ts` -- TypeScript interfaces for public event details, public spot features, and status types.
- `frontend/src/lib/api.ts` -- Add `fetchPublicEvent(slug)` and `fetchPublicSpots(slug)`.
- `frontend/src/components/public/PublicMap.tsx` -- Dedicated Leaflet map component with status coloring, touch gestures, fitBounds floating button, and indoor/outdoor support.
- `frontend/src/components/public/PublicHeader.tsx` -- Clean public header with event title, dates, address, hours, and legend bar.
- `frontend/src/components/public/SpotDetailDrawer.tsx` -- Mobile-first bottom sheet / popover displaying stall label, linear meters, price, and availability status.
- `frontend/src/pages/PublicEventPage.tsx` -- Public page orchestrating header, map, legend, and spot detail view.
- `frontend/src/App.tsx` -- URL detection for `/e/:slug` or `?slug=...` to render `PublicEventPage` when accessed publicly.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/schemas/public.py` -- Create public Pydantic schemas guaranteeing zero leak of private exhibitor or token data `[Source: ARCHITECTURE-SPINE.md#AD-1, AD-2]`.
- [x] `backend/app/api/v1/endpoints/public.py` -- Implement `GET /api/v1/public/events/{slug}` and `GET /api/v1/public/events/{slug}/spots` with SQL lazy lock expiration `[Source: ARCHITECTURE-SPINE.md#AD-2, epic-2-context.md#Technical-Decisions]`.
- [x] `backend/app/api/v1/router.py` -- Register public router under `/public` prefix `[Source: ARCHITECTURE-SPINE.md#Architecture-Overview]`.
- [x] `backend/tests/test_public_api.py` -- Add automated tests for public endpoints, lazy unlock, GeoJSON compliance, and invalid slug handling `[Source: ARCHITECTURE-SPINE.md#Testing-Strategy]`.
- [x] `frontend/src/types/public.ts` & `frontend/src/lib/api.ts` -- Define public TypeScript models and API client functions `[Source: ARCHITECTURE-SPINE.md#Frontend-Architecture]`.
- [x] `frontend/src/components/public/PublicHeader.tsx` -- Create public header with event summary and status color legend (Emerald/Amber/Gray) `[Source: DESIGN.md#colors, EXPERIENCE.md#Mobile-First]`.
- [x] `frontend/src/components/public/SpotDetailDrawer.tsx` -- Create responsive mobile bottom sheet / desktop popover for stall inspection `[Source: DESIGN.md#components, EXPERIENCE.md]`.
- [x] `frontend/src/components/public/PublicMap.tsx` -- Implement public Leaflet viewer supporting indoor/outdoor, semantic styling, smooth pinch-to-zoom, and floating recenter button `[Source: DESIGN.md#colors, EXPERIENCE.md]`.
- [x] `frontend/src/pages/PublicEventPage.tsx` & `frontend/src/App.tsx` -- Wire `/e/:slug` route into React application with loading state and not-found view `[Source: ARCHITECTURE-SPINE.md]`.
- [x] Verification -- Run full backend test suite (`pytest`) and frontend production build (`npm run build`) to ensure zero regressions.

**Acceptance Criteria:**
- Given Monique opens the public URL `/e/:slug` on her smartphone,
- When the Leaflet map loads,
- Then available stalls are displayed in Emerald green (`#10B981`), reserved stalls in Slate gray (`#9CA3AF`), and locked stalls in Amber (`#F59E0B`),
- And pinch-to-zoom and two-finger touch gestures are fluid with zero admin tools displayed,
- And clicking the floating recenter button smoothly animates the map to enclose all event stalls,
- And tapping any stall opens a detail view with stall label, linear meters, and price in euros formatted with French locale.

## Dev Notes & Architecture Traceability

### Data Models & Lazy Lock Expiration
In `backend/app/api/v1/endpoints/public.py`:
- Expired locks MUST be handled dynamically during the query so visitors immediately see abandoned carts as available:
  ```python
  effective_status = case(
      (and_(Spot.status == "locked", Spot.locked_until < func.now()), "available"),
      else_=Spot.status
  ).label("effective_status")
  ```
- Public response schemas must omit `locked_by_token` and any order/exhibitor foreign keys.

### UI & Styling Guidelines
- Primary background: Natural off-white `#FBFBFA` (`DESIGN.md`).
- Spot color map:
  - `available`: fill `#10B981` (opacity 0.65), stroke `#059669` (weight 2)
  - `locked`: fill `#F59E0B` (opacity 0.65), stroke `#D97706` (weight 2)
  - `reserved`: fill `#9CA3AF` (opacity 0.4), stroke `#6B7280` (weight 1.5, dashed/striped)
  - `blocked`: fill `#E5E7EB` (opacity 0.3), stroke `#9CA3AF` (weight 1)
- Recenter floating action button: `bg-white text-gray-700 shadow-md rounded-full p-3 hover:bg-gray-50 active:scale-95 transition`.
- Mobile ergonomics:
  - Maximum zoom level 22 outdoors, 6 indoors.
  - Safe area padding for bottom drawers on iOS Safari.

## Verification Plan

### Automated Tests
- Run `pytest backend/tests/test_public_api.py -v` to verify:
  - Successful public event lookup by slug.
  - 404 response on non-existent slug.
  - GeoJSON FeatureCollection generation with `effective_status`.
  - Stalls with expired `locked_until` reported as `available`.
  - Multi-tenant isolation between events.
- Run `npm run build` in `frontend/` to ensure full TypeScript type checking and Vite bundle compilation.

### Manual Verification
1. Start backend (`uvicorn app.main:app --port 8000`) and frontend (`npm run dev`).
2. Create and calibrate an event in the admin dashboard.
3. Draw a few spots, assign prices and linear meters.
4. Navigate to `http://localhost:5173/e/<slug>`.
5. Verify on mobile resolution (Chrome DevTools device toolbar iPhone 14):
   - Map renders without admin controls.
   - Stalls display with correct Emerald green color.
   - Tapping a stall opens the bottom sheet with exact dimensions and pricing.
   - Panning away and tapping the recenter button smoothly reframes the venue.

## Implementation Notes

- **Backend Public API:**
  - Implemented `backend/app/schemas/public.py` with `PublicEventResponse`, `PublicSpotProperties`, `PublicSpotFeature`, and `PublicSpotFeatureCollection`. Guaranteed zero leak of session tokens (`locked_by_token`) or private IDs.
  - Implemented `backend/app/api/v1/endpoints/public.py` exposing `GET /api/v1/public/events/{slug}` and `GET /api/v1/public/events/{slug}/spots`.
  - Implemented dynamic SQL lazy lock expiration (`effective_status` computed via SQL `CASE WHEN status = 'locked' AND locked_until < func.now() THEN 'available' ELSE status END`) ensuring expired locks are immediately released for visitors without mutating database rows during read-only queries.
  - Mounted `/public` endpoints under `/api/v1/public` in `backend/app/api/v1/router.py`.
- **Backend Automated Tests:**
  - Added 9 unit and integration tests in `backend/tests/test_public_api.py` covering slug resolution, 404 responses, GeoJSON FeatureCollection format, dynamic lazy lock expiration, active locks, multi-tenant event isolation, and zero sensitive data leak. All 52 backend tests pass.
- **Frontend Public Map & Mobile-First Experience:**
  - Defined TypeScript models in `frontend/src/types/public.ts` and API methods `fetchPublicEvent` and `fetchPublicSpots` in `frontend/src/lib/api.ts`.
  - Created `PublicHeader.tsx` displaying event details, dates, hours, meter pricing badge, manual refresh button, and accessible status legend.
  - Created `SpotDetailDrawer.tsx` responsive mobile bottom sheet / popover with French currency formatting (`4,00 €`), dimensions, status badge, and safe-area insets.
  - Created `PublicMap.tsx` supporting both outdoor geographic tiles (OSM/satellite toggle) and indoor floorplans (`L.CRS.Simple`), semantic status coloring (`#10B981` available, `#F59E0B` locked, `#9CA3AF` reserved, `#E5E7EB` blocked), active selection ring, floating 1-tap recenter button (`fitBounds`), and smooth pinch-to-zoom touch gestures with zero admin tools.
  - Created `PublicEventPage.tsx` orchestrating public components with skeleton loading, user-friendly 404 screen, and 10s auto-refresh polling.
  - Connected `/e/:slug` routing in `frontend/src/App.tsx` and added "Vue publique" quick action on `EventCard.tsx`.
  - Verified full TypeScript compilation and Vite build with zero errors.

## Spec Change Log

## Review Triage Log

- **patch:** `frontend/src/App.tsx` — Malformed percent-encoding in URL can throw uncaught `URIError` in `decodeURIComponent` — Wrap in `try ... catch`.
- **patch:** `frontend/src/App.tsx` — `loadEvents()` called unconditionally on mount even on public `/e/:slug` — Only fetch admin events when not on public route.
- **patch:** `frontend/src/components/public/PublicMap.tsx` — Custom `flatten` coordinate check can throw `TypeError` if layer coordinates array is empty — Use `L.geoJSON(spots).getBounds()`.
- **patch:** `frontend/src/components/public/PublicMap.tsx` — Planar mode recenter with 0 stalls does not fit to floorplan image bounds — Use `imageBoundsRef.current` as fallback.
- **patch:** `frontend/src/components/public/PublicMap.tsx` — Missing `img.onerror` in planar image loading leaves mapReady false without error feedback — Add `img.onerror` handler.
- **patch:** `frontend/src/components/public/PublicMap.tsx` — Map bounds not reset when navigating between public events due to static `_initialFitDone` — Reset on `event.id` change.
- **patch:** `frontend/src/pages/PublicEventPage.tsx` — Non-404 initial fetch failure renders blank screen with null event — Add full-page error view with retry button.
- **patch:** `frontend/src/pages/PublicEventPage.tsx` — Polling interval re-fetches static event metadata and re-instantiates timer every cycle — Isolate spot polling with stable interval.
- **patch:** `frontend/src/pages/PublicEventPage.tsx` — Fixed height calculation `h-[calc(100vh-145px)]` risks map controls cutoff on mobile — Use `flex-1 min-h-0 w-full`.
- **patch:** `frontend/src/pages/PublicEventPage.tsx` — Polling continues in background when browser tab is hidden — Check `document.visibilityState === 'visible'`.
- **patch:** `frontend/src/components/public/SpotDetailDrawer.tsx` — Reserved and blocked stalls show prominent green price badge instead of unavailable note — Conditionally display pricing only for available/locked stalls.
- **patch:** `backend/app/api/v1/endpoints/public.py` — Unbounded lock if `locked_until` is NULL — Treat `locked_until == None` as expired lock in dynamic SQL status.
