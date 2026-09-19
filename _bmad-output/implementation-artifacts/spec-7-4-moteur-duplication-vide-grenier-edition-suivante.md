---
title: 'Story 7.4: Moteur de Duplication d''un Vide-Grenier pour l''Édition Suivante'
type: 'feature'
created: '2026-09-19'
status: 'done'
baseline_commit: '23e5343b5543cf2621a09ee1901f6b4d0a40d150'
route: 'dispatch'
review_loop_iteration: 1
context:
  - _bmad-output/planning-artifacts/epics.md
  - _bmad-output/planning-artifacts/architecture/architecture-gvg-2026-09-04/ARCHITECTURE-SPINE.md
  - backend/app/models/event.py
  - backend/app/models/spot.py
  - backend/app/schemas/event.py
  - backend/app/api/v1/endpoints/events.py
  - frontend/src/types/event.ts
  - frontend/src/lib/api.ts
  - frontend/src/components/EventCard.tsx
  - frontend/src/components/DuplicateEventModal.tsx
  - frontend/src/App.tsx
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Organizers preparing a new edition of a flea market (vide-grenier) currently face a tedious barrier if they have to re-configure all parameters, re-calibrate floor plans, and re-draw dozens or hundreds of polygonal spots from scratch. They need a 1-click duplication feature that clones the entire event structure and spatial map with all spots and attributes, while resetting all registrations, bookings, orders, and emails to a clean slate.

**Approach:**
1. Backend:
   - Provide endpoint `POST /api/v1/events/{id_or_slug}/duplicate`:
     - Authenticated and authorized via `check_event_ownership(source_event, current_user)`.
     - Accepts optional JSON body `EventDuplicate` with `title`, `start_date`, `end_date`.
     - Defaults:
       - Title: `f"{source_event.title} - Copie"` if not provided.
       - Dates: shifted by +1 year (365 days preserving duration) if not provided, or custom dates if provided (with `end_date >= start_date`).
     - Generates a unique collision-safe slug via `generate_unique_slug(db, new_title)`.
     - Preserves: `owner_id`, `description`, `map_type`, `center_latitude`, `center_longitude`, `default_zoom`, `price_per_meter_cents`, `setup_start_time`, `setup_end_time`, `public_start_time`, `public_end_time`, `location_address`, `organizer_email`, `stripe_account_id`, `manual_approval_required`, `rules_text`.
     - Safely clones media assets on disk if present (`poster_image_url`, `background_image_url`) to new UUID filenames in `uploads/` so operations on one event do not affect the other.
     - Status is strictly set to `draft`.
     - Clones all `Spot` records associated with `source_event.id`:
       - Preserves `label`, `linear_meters`, `price_cents`, and exact spatial geometry `geom`.
       - Status of all duplicated spots is initialized strictly to `available` (no locks, no tokens, no bookings).
     - Strictly zero orders, booking items, payment transactions, or email logs duplicated.
     - Commits atomically in a single database transaction.
     - Returns `EventResponse` with HTTP 201 Created.
2. Frontend:
   - Add `duplicateEvent(idOrSlug: string, data?: EventDuplicateInput)` in `frontend/src/lib/api.ts`.
   - Create `DuplicateEventModal.tsx` allowing the organizer to review the source title, adjust the new edition's title (prefilled with `[Titre] - Copie`), optionally select new dates, and submit.
   - Add a "Dupliquer" button with a `Copy` icon in `EventCard.tsx`.
   - Wire up modal in `App.tsx`: upon completion, display a success notification and refresh events list or open the new event.

## Boundaries & Constraints

**Always:**
- Strictly enforce ownership (`check_event_ownership`): only the event owner or a super-admin can duplicate an event.
- Initialize duplicated event status strictly to `draft`.
- Reset all duplicated spots to status `available` with `locked_until=None` and `locked_by_token=None`.
- Copy all spots with their exact spatial coordinates and geometries (`geom`).
- Clone floorplan and poster files on disk to independent filenames to prevent cross-deletion side effects.
- Generate a new, unique slug for the duplicated event.
- Strictly guarantee that 0 orders, 0 bookings, 0 payments, and 0 email logs are copied over.

**Never:**
- Never duplicate attendee/exhibitor personal data, orders, payments, or registrations.
- Never duplicate an event to `published` status directly.
- Never allow non-owners to duplicate someone else's event.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Basic Duplication | Existing event with 50 spots, no body | Creates new draft event `[Titre] - Copie`, 50 spots copied in `available` status, dates shifted +1 year, status `draft` | 201 Created |
| Custom Title and Dates | `{"title": "Vide-Grenier 2027", "start_date": "...", "end_date": "..."}` | New draft event named "Vide-Grenier 2027" with specified dates and 50 spots | 201 Created |
| End date < Start date | `end_date` before `start_date` | Rejection with HTTP 422 | HTTP 422 Unprocessable Entity |
| Non-existent source event | Non-existent UUID or slug | Returns 404 Not Found | HTTP 404 "Event not found" |
| Non-owner access | Stranger user token | Forbidden | HTTP 403 Forbidden |
| Event with Planar Background & Poster | Source event has local files in `/uploads/` | Files copied to new distinct filenames on disk for the new event | Safe copy; falls back cleanly if disk file missing |
| Event with zero spots | Source event has 0 spots configured | Duplicates event successfully with 0 spots | 201 Created |

</frozen-after-approval>

## Code Map

- `backend/app/schemas/event.py` -- Added `EventDuplicate` schema with optional title and start/end dates.
- `backend/app/api/v1/endpoints/events.py` -- Added `POST /{id_or_slug}/duplicate` endpoint.
- `backend/tests/test_events_api.py` -- Unit and integration tests for event duplication, spots cloning, clean slate, access control, and edge cases.
- `frontend/src/types/event.ts` -- Added `EventDuplicateInput` type.
- `frontend/src/lib/api.ts` -- Added `duplicateEvent` API client function.
- `frontend/src/components/DuplicateEventModal.tsx` -- New modal for confirming/customizing duplicate event.
- `frontend/src/components/EventCard.tsx` -- Added "Dupliquer" action button.
- `frontend/src/App.tsx` -- Wired up duplicate action, state, modal, and notifications.

## Review Records & Remediation

- **Verification Gap Reviewer**:
  - Identified missing date assertions for +365d and custom dates. Added comprehensive timestamp assertions in test suite.
  - Identified unverified background image copying. Added background image upload & disk verification in tests.
  - Identified unverified spot geometries. Added GeoJSON feature coordinates verification.
  - Identified unverified published-to-draft status reset. Tested with source event in published status.
- **Edge Case Hunter & Blind Hunter**:
  - Guarded against title length > 255 chars with base title truncation.
  - Symmetrically handled single-boundary date updates (start only, end only, or both).
  - Used correct `settings.upload_dir_path / "backgrounds"` directory matching upload convention.
  - Added transaction failure cleanup: unlinking cloned disk files if database commit fails.
  - Handled IntegrityError returning HTTP 409 Conflict.
  - Upgraded frontend modal to `datetime-local` input to preserve hours and minutes.
  - Selected newly duplicated draft event upon creation.


