---
title: 'Story 7.2: Page Vitrine par Événement avec Affiche Officielle'
type: 'feature'
created: '2026-09-18'
status: 'done'
baseline_commit: '8e8f9998df9a80397fbff3a71b262d169b1875e5'
route: 'dispatch'
review_loop_iteration: 0
context:
  - _bmad-output/planning-artifacts/epics.md
  - _bmad-output/planning-artifacts/architecture/architecture-gvg-2026-09-04/ARCHITECTURE-SPINE.md
  - backend/app/models/event.py
  - backend/app/schemas/public.py
  - backend/app/api/v1/endpoints/public.py
  - frontend/src/types/public.ts
  - frontend/src/pages/PublicEventPage.tsx
  - frontend/src/App.tsx
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** When exhibitors or visitors open a specific event link (`/events/:slug` or `/e/:slug`), they are currently dropped directly onto the Leaflet map without seeing the event's official poster, opening hours, exhibitor setup schedule, full description, amenities (buvette, sanitaires, parking), or practical rules beforehand.

**Approach:** Build a rich, responsive event showcase page (`EventShowcasePage.tsx`) accessible at `/e/:slug` and `/events/:slug`, displaying the official event poster, practical schedule, location, pricing, availability stats, amenities, and regulations, with a prominent call-to-action button directing exhibitors to the interactive map (`/e/:slug/map`).

## Boundaries & Constraints

**Always:**
- Accessing `/events/:slug` or `/e/:slug` renders the showcase page for published events without requiring authentication.
- Provide a clear, prominent CTA "Consulter le plan & Réserver mes emplacements" leading directly to `/e/:slug/map`.
- Preserve direct navigation to the interactive map when `/map` is in the path (`/e/:slug/map` or `/events/:slug/map`).
- Display the official poster (`poster_image_url`) in large format, with an elegant fallback (background image or branded cover card) when no poster is uploaded.
- Include practical schedule details: exhibitor installation (`setup_start_time` - `setup_end_time`), public hours (`public_start_time` - `public_end_time`), pricing per linear meter, remaining spots counter, location address, amenities, and organizer rules/contact.
- Maintain responsive mobile ergonomics, including a sticky bottom action bar on mobile devices.

**Never:**
- Never break existing reservation flows, cart state, or confirmation links.
- Never expose unpublished or draft events to unauthenticated public visitors.
- Never require user registration or login to view the event showcase page.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Visitor visits `/e/:slug` | Published event | Displays `EventShowcasePage` with poster, dates, times, price, amenities, and CTA to map | 404 error page if event not found or unpublished |
| Visitor visits `/e/:slug/map` | Published event | Directly renders `PublicEventPage` (interactive Leaflet map) | Same as above |
| Event has `poster_image_url` | Event with uploaded poster | Renders poster image in hero section with zoom/preview support | Fallback to default card if poster fails to load |
| Event without `poster_image_url` | `poster_image_url=None` | Displays styled thematic event banner with map background or SVG badge | Graceful fallback without broken `<img>` tags |
| Click "Consulter le plan & Réserver" | Button click on showcase | Smoothly navigates to `/e/:slug/map`, opening the interactive stall picker | N/A |
| Event has 0 available spots | All spots reserved/locked | Displays "Complet" badge, disables or warns on reservation CTA | Banner indicating event is fully booked |

</frozen-after-approval>

## Code Map

- `backend/app/models/event.py` -- Add `poster_image_url` column to `Event` model.
- `backend/alembic/versions/009_add_poster_image_url_to_events.py` -- Migration adding `poster_image_url` to `events` table.
- `backend/app/schemas/public.py` -- Update `PublicEventResponse` to include `poster_image_url`, `total_spots`, and `available_spots`.
- `backend/app/api/v1/endpoints/public.py` -- Update `get_public_event` to compute and return spot capacity metrics and poster URL.
- `backend/tests/test_public_api.py` -- Add tests verifying `PublicEventResponse` fields (`poster_image_url`, `total_spots`, `available_spots`).
- `backend/tests/test_migrations.py` -- Add assertion verifying `poster_image_url` in migration test suite.
- `frontend/src/types/public.ts` -- Update `PublicEventResponse` interface with `poster_image_url`, `total_spots`, `available_spots`.
- `frontend/src/pages/EventShowcasePage.tsx` -- New showcase page component with poster, schedule, amenities, rules, and map CTA.
- `frontend/src/App.tsx` -- Update `PublicRouteState` view to `'showcase' | 'map' | 'reservation' | 'confirmation' | 'cancellation'`, route `/e/:slug` to showcase and `/e/:slug/map` to map.

## Tasks & Acceptance

1. [x] Create spec document `spec-7-2-page-vitrine-par-evenement-affiche-officielle.md`.
2. [x] Backend: Add `poster_image_url` column and Alembic migration 009.
3. [x] Backend: Update `PublicEventResponse` schema and `get_public_event` endpoint with spot counts and poster URL.
4. [x] Backend: Update test suite (`test_public_api.py`, `test_migrations.py`).
5. [x] Frontend: Update `types/public.ts` and routing in `App.tsx` for showcase vs map views.
6. [x] Frontend: Implement `EventShowcasePage.tsx` with poster, timetable, amenities, rules, and responsive CTA.
7. [x] Verification: Run all backend pytest tests and verify frontend Vite build.

