---
title: 'Story 7.1: Public Multi-Event Home Portal & Search'
type: 'feature'
created: '2026-09-17'
status: 'done'
baseline_commit: '6670bf6b833ba0f24eb62268ffe7ab627d20ec95'
route: 'dispatch'
review_loop_iteration: 1
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Visitors and exhibitors currently land on the login screen or an event-specific URL without an open public portal to browse upcoming community garage sales and flea markets across the platform.

**Approach:** Build a dedicated public home page (`/`) featuring platform discovery, live keyword/location search, and dynamic event cards with real-time stall capacity counters (`available_spots`), backed by a public unauthenticated API endpoint (`GET /api/v1/public/events`).

## Boundaries & Constraints

**Always:**
- Expose `GET /api/v1/public/events` without requiring any authentication token or session.
- Only return events with `status == 'published'` and whose `end_date` is in the future or equal to the current day (`end_date >= func.now()`).
- Aggregate stall availability (`total_spots` and `available_spots`) dynamically per event, counting only active stalls not currently reserved or locked by an active session.
- Order events chronologically by `start_date ASC` so that the most imminent events appear first.
- Provide responsive real-time client-side and server-side filtering by city/commune, title, and description.
- Keep the organizer/admin dashboard accessible via dedicated routes (`/admin`, `/login`) and an "Espace Organisateur" navigation button in the public header.

**Never:**
- Never display draft, archived, or cancelled events on the public portal.
- Never expose sensitive organizer or attendee data (such as stripe credentials, private attendee notes, phone numbers, or exhibitor personal records) on the public portal.
- Never break existing direct links to `/e/:slug`, `/events/:slug`, or admin routes (`/admin`, `/login`, `/admin/users`).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Public listing of upcoming events | `GET /api/v1/public/events` (No auth) | `200 OK` with JSON array of published upcoming events, including `total_spots`, `available_spots`, pricing, dates, and location | N/A |
| Search filter by city or keyword | `GET /api/v1/public/events?search=rennes` | `200 OK` with filtered events matching city/address, title, or description | Empty list `[]` if no matches |
| Event with past `end_date` | Event ended yesterday | Excluded from `GET /api/v1/public/events` results | N/A |
| Event with `status='draft'` | Draft event in database | Excluded from `GET /api/v1/public/events` results | N/A |
| Event with 0 spots drawn | Published event without spots | Returned with `total_spots=0` and `available_spots=0` | N/A |
| Visitor navigates to `/` | Anonymous visitor browser | Renders `HomePage.tsx` with hero section, live search bar, and event card grid | Fallback empty state if no published events |
| Organizer navigates to `/login` | Click "Espace Organisateur" | Renders `LoginPage.tsx` or redirects to `/admin` if already authenticated | N/A |

</frozen-after-approval>

## Code Map

- `backend/app/schemas/public.py` -- Define `PublicEventListItem` schema with `price_per_meter`, `total_spots`, `available_spots`, dates, and location details.
- `backend/app/api/v1/endpoints/public.py` -- Implement `GET /events` endpoint filtering published future events with dynamic spot availability outer join aggregation and optional `search` query parameter.
- `backend/tests/test_public_api.py` -- Add automated test cases covering public event listing, status filtering (published vs draft), past event exclusion, spot availability calculation, and search filtering.
- `frontend/src/types/public.ts` -- Define TypeScript interface `PublicEventListItem`.
- `frontend/src/lib/api.ts` -- Add client function `fetchPublicEvents(search?: string)`.
- `frontend/src/pages/HomePage.tsx` -- Implement public portal page component featuring hero banner, instant search filter bar, responsive event cards (date, address, pricing, remaining spots badge, visual banner), and header with navigation to organizer space.
- `frontend/src/App.tsx` -- Update root routing so that `/` renders `HomePage.tsx` for visitors and organizers, with `/admin` and `/login` routes reserved for administration, and seamless navigation between the public catalog and organizer console.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/schemas/public.py` -- Add `PublicEventListItem` response schema with validation and computed `price_per_meter`.
- [x] `backend/app/api/v1/endpoints/public.py` -- Add `GET /events` endpoint with SQL outer join aggregation for `total_spots` and `available_spots`, date filtering, and search.
- [x] `backend/tests/test_public_api.py` -- Write unit tests for `GET /api/v1/public/events` asserting published filtering, date cutoff, spot aggregation, and search term matching.
- [x] `frontend/src/types/public.ts` & `frontend/src/lib/api.ts` -- Add `PublicEventListItem` interface and `fetchPublicEvents` API helper.
- [x] `frontend/src/pages/HomePage.tsx` -- Create the public home page with hero section, live search input, event cards grid, remaining capacity badges, and navigation CTA.
- [x] `frontend/src/App.tsx` -- Route `/` to `HomePage`, preserve `/admin` and `/login` navigation, and integrate direct links to event showcase and reservation.

**Acceptance Criteria:**
- Given published upcoming events in the database, when an unauthenticated user opens `/`, then they see the list of events displayed as rich cards with title, date, commune, price, and remaining stall capacity without being redirected to login.
- Given an event that is in `draft` status or whose `end_date` is in the past, when querying `/api/v1/public/events` or viewing `/`, then it is not displayed in the public portal.
- Given a user typing a search term in the home page search bar, then the list of events filters in real time to show only events matching that city, title, or keyword.
- Given an event card on the home page, when the user clicks "Voir l'événement" or "Réserver mon stand", then they are navigated directly to that event's public page.
- Given an organizer on the public home page, when they click "Espace Organisateur", then they are directed to the login page (or admin dashboard if already logged in).

## Implementation Notes

- Endpoint `GET /api/v1/public/events` dynamically joins `Event` with an aggregation subquery on `Spot` to calculate `total_spots` and `available_spots` with lazy lock expiration (`status == 'available' OR (status == 'locked' AND (locked_until IS NULL OR locked_until < func.now()))`).
- Date cutoff uses `func.date(Event.end_date) >= func.date(func.now())` to ensure events taking place on the current day remain visible until midnight.
- Search term escaping cleans `\`, `%`, and `_` to avoid SQL wildcard injection.
- The home page features client-side and debounced server-side filtering, broken image fallback, multi-day date range formatting, and accessible navigation between public and admin views.

## Spec Change Log

## Review Triage Log

- **Blind Hunter / Edge Case Hunter**:
  - `func.date(Event.end_date) >= func.date(func.now())` adopted to prevent premature disappearance of current-day events. -> *Patched*.
  - Escape SQL wildcards (`%`, `_`, `\`) in search query. -> *Patched*.
  - Direct "Réserver" button on event card to interactive map (`/e/${slug}`) instead of empty cart checkout. -> *Patched*.
  - Replace Tailwind v4 classes (`focus:outline-hidden`, `shadow-xs`, `shadow-2xs`) with Tailwind v3 compatible classes (`focus:outline-none`, `shadow-sm`). -> *Patched*.
  - Prevent async search response race condition with `active` cancellation flag in `useEffect`. -> *Patched*.
  - Add `onError` fallback image handler for broken event visual links. -> *Patched*.
  - Multi-day date range display formatting in `HomePage.tsx`. -> *Patched*.
  - Ensure `/events/:slug` and `/events/:slug/map` match `parsePublicRoute`. -> *Patched*.
  - Fix login screen visual flash by checking `isLoading` before `isLoginRoute`. -> *Patched*.
  - Header logo accessibility with button element and keyboard focus rings. -> *Patched*.
- **Verification Gap Reviewer**:
  - Assert `price_per_meter == 4.0` in public tests. -> *Patched*.
  - Add search match assertion on `Event.description`. -> *Patched*.
  - Add assertion verifying exclusion of `status == "archived"` events. -> *Patched*.

## Verification

**Commands:**
- `/home/sylvain/projets/gvg/gvg/.venv/bin/pytest backend/tests/test_public_api.py -v` -- Result: 26/26 passed (100%)
- `/home/sylvain/projets/gvg/gvg/.venv/bin/pytest backend/tests/ -q` -- Result: 277/277 passed (100%)
- `npm --prefix frontend run build` -- Result: 0 errors, clean production bundle generated

## Design Notes

- **Stall Availability Computation**: Spots are considered available when `Spot.status == 'available'` or (`Spot.status == 'locked'` AND (`Spot.locked_until IS NULL` OR `Spot.locked_until < func.now()`)). Using an aggregation subquery with an outer join keeps the query efficient across both SQLite and PostgreSQL.
- **Header & Navigation**: The public header displays a clean, modern aesthetic with logo, tagline, and an "Espace Organisateur" / "Connexion" button. If the user is already authenticated as an organizer or superadmin, it displays a direct badge/link "Tableau de bord" leading back to `/admin`.


