---
title: "Story 2.2: Multi-Spot Selection & Temporary Hold Lock (15 min)"
type: "feature"
created: "2026-09-13"
status: 'done'
baseline_commit: '588c3f86bf953808f85599ce72be18043eaf5654'
route: "dispatch"
review_loop_iteration: 0
context:
  - "_bmad-output/planning-artifacts/architecture/architecture-gvg-2026-09-04/ARCHITECTURE-SPINE.md"
  - "_bmad-output/implementation-artifacts/epic-2-context.md"
  - "_bmad-output/planning-artifacts/ux-designs/ux-gvg-2026-09-04/DESIGN.md"
  - "_bmad-output/planning-artifacts/ux-designs/ux-gvg-2026-09-04/EXPERIENCE.md"
  - "_bmad-output/implementation-artifacts/spec-2-1-consultation-interactive-plan-public-mobile-first.md"
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** When exhibitors (like Monique) browse the venue map to book flea market spaces, several visitors may attempt to select the same attractive stalls at the same time. Without concurrency protection and a cart system, double bookings occur, or buyers lose their chosen stalls while continuing to browse or preparing their information.

**Approach:** Implement atomic PostgreSQL 15-minute hold locks tied to anonymous client session tokens (`POST /api/v1/public/events/{slug}/spots/{id}/lock` and `unlock`), support multi-stall cart retrieval (`GET /api/v1/public/events/{slug}/cart`), render cart-selected stalls in Cobalt Blue (`#2563EB`) on the interactive map, provide explicit collision toast alerts when attempting to select stalls held by other buyers, and build a reactive Cart Drawer with a dynamic 15-minute countdown timer (*Hold Timer*).

## Boundaries & Constraints

**Always:**
- Use atomic single-transaction SQL updates to acquire locks: `UPDATE spots SET status = 'locked', locked_until = func.now() + INTERVAL '15 minutes', locked_by_token = :token WHERE id = :spot_id AND (status = 'available' OR (status = 'locked' AND (locked_until.is_(None) OR locked_until < func.now() OR locked_by_token = :token)))`.
- Persist an anonymous client UUID `session_token` in browser `localStorage` (`gvg_session_token`) so cart locks survive page reloads and mobile browser tab changes.
- Return HTTP 409 Conflict with clear French error messages when a stall is already held by another session (`"Ce stand est en cours de commande par un autre visiteur"`) or already sold/blocked (`"Cet emplacement n'est plus disponible à la vente"`).
- Render stalls currently held in the user's own cart with Cobalt Blue styling (`#2563EB`, fill `#3B82F6`, border `#1D4ED8` 2.5px) according to `DESIGN.md`.
- Display a collapsible floating Cart Drawer showing: total stalls count, cumulative linear meters, and total price in euros (`2 stands (4,0 m) • 20,00 €`).
- Include a live countdown timer (*Hold Timer*) synced with the earliest `locked_until` in the cart (`14:59`), displaying visual warning (amber/red pulse) when remaining time is under 2 minutes.
- When a user deselects a stall or removes it from the Cart Drawer, release the lock atomically in the database (`status = 'available', locked_until = NULL, locked_by_token = NULL`).
- Automatically clear expired stalls from the cart when the hold timer reaches zero with an explicit notification toast.

**Never:**
- Never require user registration, passwords, or personal details to lock stalls in the cart (guest reservation flow).
- Never allow one visitor's lock request to steal or overwrite an active lock owned by another visitor.
- Never rely on an external Redis or background worker daemon for lock expiration; dynamic SQL queries treat `locked_until < now()` as available.
- Never hide stall numbers or map controls behind the Cart Drawer; drawer must be collapsible and respect mobile viewport bounds.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Lock available stall | Tap green stall A-01 with session token `tok-1` | HTTP 200/201; stall status set to `locked` with `locked_until = now() + 15m`; turns blue; Cart Drawer opens with `1 stand (2,0 m) • 10,00 €` | N/A |
| Multi-stall selection | Tap green stall A-02 while A-01 is in cart | Both stalls turn blue; cart updates to `2 stands (4,0 m) • 20,00 €`; timer reflects earliest expiration | Atomic lock acquired for each stall |
| Concurrent collision | User B taps A-01 while User A holds active lock | HTTP 409 Conflict; toast notification "Ce stand est en cours de commande par un autre visiteur"; map remains green/amber for User B | User A's lock is unaffected |
| Unlock from map | User A taps blue stall A-01 already in cart | HTTP 200 OK; stall released to `available`; turns green; removed from cart | Lock cleared in DB |
| Remove from Cart Drawer | User clicks `X` on stall A-02 in drawer | HTTP 200 OK unlock request; A-02 turns green on map; cart total updates | Recalculates total meters & price |
| Lock expired stall | Stall was locked by User B but `locked_until` has passed | User A successfully acquires lock; `locked_by_token` becomes User A; `locked_until` reset to `now() + 15m` | Overwrites expired lock cleanly |
| Page reload with active cart | Visitor refreshes `/e/:slug` with active tokens in `localStorage` | Rehydrates cart from `GET /api/v1/public/events/{slug}/cart`; stalls highlighted in blue; countdown resumes | Expired items automatically pruned |
| Timer expiration (00:00) | 15 minutes elapse without checkout | Cart empties; toast "Votre réservation temporaire a expiré, les stands ont été libérés"; blue stalls revert to green | Triggers client state reset |

</frozen-after-approval>

## Code Map

- `backend/app/schemas/public.py` -- Define `LockSpotRequest`, `UnlockSpotRequest`, `CartSpotItem`, and `CartResponse` schemas.
- `backend/app/api/v1/endpoints/public.py` -- Implement:
  - `POST /api/v1/public/events/{slug}/spots/{spot_id}/lock` (atomic acquisition)
  - `POST /api/v1/public/events/{slug}/spots/{spot_id}/unlock` (atomic release)
  - `GET /api/v1/public/events/{slug}/cart` (active cart inspection)
- `backend/tests/test_public_api.py` -- Pytest suite covering lock acquisition, concurrency conflicts (HTTP 409), unlocking, expired lock takeover, multi-stall cart totals, and session isolation.
- `frontend/src/types/public.ts` -- TypeScript interfaces for cart responses, lock payloads, and cart spot items.
- `frontend/src/lib/session.ts` -- Helper managing persistent anonymous `session_token` in `localStorage`.
- `frontend/src/lib/api.ts` -- Client functions `lockSpot`, `unlockSpot`, and `fetchCart`.
- `frontend/src/components/public/CartDrawer.tsx` -- Responsive mobile-first bottom cart bar with item count, total meters/price, expandable list, remove actions, and live hold timer.
- `frontend/src/components/public/PublicMap.tsx` -- Update stall styling to render cart-selected spots in Cobalt Blue (`#2563EB`), handle selection/deselection clicks, and pass collision events.
- `frontend/src/pages/PublicEventPage.tsx` -- Orchestrate cart state, lock/unlock mutations, timer countdown, collision toast messages, and rehydration on mount.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/schemas/public.py` -- Define Pydantic request and response schemas for lock, unlock, and cart retrieval `[Source: ARCHITECTURE-SPINE.md#AD-2, epic-2-context.md]`.
- [x] `backend/app/api/v1/endpoints/public.py` -- Implement atomic SQL lock (`15 min`), unlock, and cart endpoints with collision checks `[Source: ARCHITECTURE-SPINE.md#AD-2, epic-2-context.md]`.
- [x] `backend/tests/test_public_api.py` -- Add automated tests for locking, conflict detection (HTTP 409), unlocking, expired lock takeover, and cart aggregation `[Source: ARCHITECTURE-SPINE.md#Testing-Strategy]`.
- [x] `frontend/src/lib/session.ts` & `frontend/src/types/public.ts` -- Implement persistent session token manager and cart TypeScript models `[Source: epic-2-context.md]`.
- [x] `frontend/src/lib/api.ts` -- Add `lockSpot`, `unlockSpot`, and `fetchCart` API methods `[Source: ARCHITECTURE-SPINE.md]`.
- [x] `frontend/src/components/public/CartDrawer.tsx` -- Build responsive collapsible cart drawer with hold countdown timer, meter/price summary, and item removal `[Source: DESIGN.md, EXPERIENCE.md]`.
- [x] `frontend/src/components/public/PublicMap.tsx` -- Support cart-selected stall rendering in Cobalt Blue (`#2563EB`) and tap-to-lock/unlock interactions `[Source: DESIGN.md#colors]`.
- [x] `frontend/src/pages/PublicEventPage.tsx` -- Integrate cart management, collision toasts, hold timer tick, and rehydration on load `[Source: EXPERIENCE.md]`.
- [x] Verification -- Run backend test suite (`pytest`) and frontend production build (`npm run build`) to ensure zero regressions.

**Acceptance Criteria:**
- Given Monique clicks on an available green stall A-12,
- When the lock request succeeds,
- Then stall A-12 turns Cobalt Blue (`#2563EB`) and the Cart Drawer appears at the bottom with total meters, price in euros, and a dynamic 15-minute countdown,
- When Monique clicks on an adjacent available stall A-13,
- Then stall A-13 also turns blue and the Cart Drawer aggregates both stalls (e.g. "2 stands (4,0 m) • 20,00 €"),
- When another visitor attempts to click stall A-12 during this time,
- Then HTTP 409 is returned and a toast notification warns "Ce stand est en cours de commande par un autre visiteur",
- When Monique clicks A-12 again or clicks `X` in the Cart Drawer,
- Then stall A-12 is unlocked in the database and reverts to Emerald Green.

## Implementation Notes

- **Backend Public API:**
  - Implemented `LockSpotRequest`, `UnlockSpotRequest`, `CartSpotItem`, and `CartResponse` in `backend/app/schemas/public.py`.
  - Implemented atomic SQL lock acquisition (`15 min`), atomic release, and cart inspection in `backend/app/api/v1/endpoints/public.py`:
    - `POST /api/v1/public/events/{slug}/spots/{spot_id}/lock`
    - `POST /api/v1/public/events/{slug}/spots/{spot_id}/unlock`
    - `GET /api/v1/public/events/{slug}/cart`
  - Atomic single-transaction SQL queries ensure zero race conditions, with dynamic dialect detection (`INTERVAL '15 minutes'` on PostgreSQL and SQLite date manipulation fallback for tests).
  - Explicit HTTP 409 Conflict messages returned when a stall is already held (`"Ce stand est en cours de commande par un autre visiteur"`) or sold/blocked (`"Cet emplacement n'est plus disponible à la vente"`).
  - Helper `get_cart_for_session` prunes expired locks from the database automatically on cart queries.
- **Backend Automated Tests:**
  - Added 11 new tests to `backend/tests/test_public_api.py` covering:
    - Successful spot locking and database state verification.
    - Multi-spot selection and cart aggregation (meters and price totals).
    - Concurrency collision detection returning HTTP 409 and preserving existing lock.
    - Locking sold/blocked stalls returning HTTP 409.
    - Releasing hold locks via unlock endpoint.
    - Unauthorized unlock prevention (attempting to unlock another user's hold).
    - Expired lock takeover by new visitors.
    - Cart rehydration and automatic pruning of expired locks.
    - Empty cart querying without session token.
    - Session isolation between distinct visitors.
  - All 63 backend tests in the test suite pass with 0 errors.
- **Frontend Multi-Spot & Cart Drawer:**
  - Implemented `session.ts` with `getSessionToken`, `resetSessionToken`, and `clearSessionToken` storing `gvg_session_token` in `localStorage`.
  - Defined TypeScript models in `frontend/src/types/public.ts` and API methods `lockSpot`, `unlockSpot`, and `fetchCart` in `frontend/src/lib/api.ts`.
  - Created `CartDrawer.tsx` with mobile-first collapsible design, dynamic 15-minute countdown Hold Timer, warning alert style under 2 minutes (<120s), total meters and price in French currency format, and individual spot removal (`X` button).
  - Updated `PublicMap.tsx` with `cartSpotIds` prop and Cobalt Blue (`#2563EB`, fill `#3B82F6`, border `#1D4ED8` 2.5px) rendering according to `DESIGN.md`, updated tooltips and accessible aria labels.
  - Updated `PublicHeader.tsx` status legend to include Cobalt Blue "Mon panier".
  - Updated `PublicEventPage.tsx` with full cart state orchestration, map tap-to-lock/unlock, collision toast alerts, hold timer expiration resets, and rehydration on initial mount.
  - Verified full TypeScript compilation and Vite production build (`npm run build`) with zero errors.

## Spec Change Log

## Review Triage Log

- **patch:** `frontend/src/pages/PublicEventPage.tsx` — `<CartDrawer>` rendered without `onProceedToCheckout` prop, hiding checkout action button — Pass checkout progression callback with toast/route transition.
- **patch:** `backend/app/schemas/public.py` — `session_token` lacks `max_length=255` validation, risking HTTP 500 on database insertion — Add `max_length=255` constraint to `LockSpotRequest` and `UnlockSpotRequest`.
- **patch:** `backend/app/api/v1/endpoints/public.py` — `db.bind` accessed directly instead of `db.get_bind()` — Use `bind = db.get_bind()` for robust dialect detection.
- **patch:** `frontend/src/components/public/CartDrawer.tsx` — Naive datetime from SQLite lacks UTC 'Z' suffix, causing timezone offset in countdown — Append 'Z' to ISO string if timezone offset is missing.
- **patch:** `frontend/src/pages/PublicEventPage.tsx` — Error detail array from HTTP 422 rendered directly in toast causes crash — Extract `err?.detail[0]?.msg || err?.detail` safely.
- **patch:** `frontend/src/components/public/PublicMap.tsx` — Inspected unavailable spots masquerade in Cobalt Blue — Ensure only spots in `cartSpotIds` receive Cobalt Blue fill.
- **patch:** `frontend/src/pages/PublicEventPage.tsx` — Unlock error does not refresh cart or spots, leaving desynchronized stalls in drawer — Call `pollSpots()` in unlock catch blocks.
- **patch:** `backend/tests/test_public_api.py` — Missing assertions on 15-minute lock duration and earliest expiration (`min`) in multi-spot carts — Add assertions checking `now + 14m <= locked_until <= now + 16m` and `cart.expires_at == spot1.locked_until`.
- **patch:** `frontend/src/pages/PublicEventPage.tsx` — Rapid double-clicks trigger race conditions on map stalls — Add `pendingSpotIds` guard to prevent duplicate concurrent clicks.
