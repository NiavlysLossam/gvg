---
title: "Story 2.3: Formulaire Invité & Attestation sur l'Honneur"
type: 'feature'
created: '2026-09-13'
status: 'done'
baseline_commit: '7062e306742dd0467c792514d768caa20c1754fd'
route: 'dispatch'
review_loop_iteration: 0
context:
  - "_bmad-output/planning-artifacts/architecture/architecture-gvg-2026-09-04/ARCHITECTURE-SPINE.md"
  - "_bmad-output/implementation-artifacts/epic-2-context.md"
  - "_bmad-output/planning-artifacts/ux-designs/ux-gvg-2026-09-04/DESIGN.md"
  - "_bmad-output/planning-artifacts/ux-designs/ux-gvg-2026-09-04/EXPERIENCE.md"
  - "_bmad-output/implementation-artifacts/spec-2-2-selection-multi-places-verrouillage-temporaire-15min.md"
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** To complete a flea market booking, exhibitors (like Monique) are often forced to create an account with a password, or submit burdensome identity documents upfront, creating significant checkout drop-off. Furthermore, French law (Art. L310-2 du Code de commerce) requires private individual exhibitors to certify that they do not participate in more than two sales per year.

**Approach:** Build a passwordless guest checkout form at `/e/:slug/reservation` linked to the active 15-minute cart session lock, requiring only essential contact information (Nom, Prénom, Email, Téléphone portable, Adresse postale) and a mandatory legal checkbox attesting compliance with Art. L310-2 du Code de commerce, creating an unconfirmed `Order` and `BookingItem`s in PostgreSQL without storing any passwords or identity document scans.

## Boundaries & Constraints

**Always:**
- Access the checkout form at `/e/:slug/reservation` without authentication or prior account creation.
- Display a live Hold Timer synced with the user's cart locks (`locked_until`), warning the user if under 2 minutes and redirecting or notifying if locks expire.
- Collect only essential contact fields: `first_name`, `last_name`, `email`, `phone`, `street_address`, `postal_code`, `city`.
- Require an explicit mandatory checkbox for the sworn statement: *"Je certifie sur l'honneur être un particulier et ne pas participer à plus de 2 ventes au déballage dans l'année (art. L310-2 du Code de commerce)"*.
- Verify on backend order creation (`POST /api/v1/public/events/{slug}/orders`) that the `session_token` holds at least one active locked spot (`locked_until > now()`).
- Atomically create an `Order` (`status = 'pending'`, `payment_method = 'stripe'`, `honor_declaration_accepted = true`, `honor_declaration_accepted_at = now()`) and associated `BookingItem` records for each held spot.
- Generate a unique human-friendly `order_number` (e.g., `GVG-2026-XXXX`) and an unguessable `access_token` for passwordless order lookup.
- Render responsive mobile-first UI respecting `DESIGN.md` styling and clear French microcopy (`EXPERIENCE.md`).

**Never:**
- Never ask for or store passwords, password confirmations, or account credentials.
- Never ask for or provide upload endpoints for identity cards (CNI), passports, or proof of residence.
- Never allow order creation without the mandatory sworn declaration accepted.
- Never create an order if the cart is empty or the spot locks have expired.
- Never finalize spot status to `reserved` in this story (that transition occurs upon payment webhook in Story 2.4).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Valid guest order submission | 2 spots held in session; valid contact fields; checkbox checked | HTTP 201 Created; `Order` with `status: pending`, `order_number`, and `BookingItem`s; UI displays order recap & prepares payment | N/A |
| Checkbox unchecked | Valid contact info, but sworn statement left unchecked | Client and server validation error: "L'attestation sur l'honneur est obligatoire pour participer au vide-grenier." | HTTP 422 Unprocessable Entity |
| Expired cart submission | Form submitted after 15m hold timer reaches 00:00 | HTTP 409 Conflict: "Votre réservation temporaire a expiré, veuillez resélectionner vos stands." | Prompt to return to map `/e/:slug` |
| Empty cart visit | Navigating to `/e/:slug/reservation` with no spots in cart | UI displays empty state with CTA "Choisir des emplacements" directing to `/e/:slug` | Prevents form submission |
| Invalid contact data | Invalid email or missing required fields (e.g., postal code) | Form highlights offending fields with clear inline error messages | Client validation + HTTP 422 |
| Active countdown display | Form loaded with 11:20 remaining on hold lock | Dynamic timer badge shows "Réservé : 11:20", turns amber/red when under 2 minutes | Auto-notifies if expired during form fill |

</frozen-after-approval>

## Code Map

- `backend/app/models/order.py` -- Define `Order` and `BookingItem` SQLAlchemy ORM models with relations to `Event` and `Spot`.
- `backend/app/models/__init__.py` -- Export `Order` and `BookingItem`.
- `backend/alembic/versions/004_create_orders_and_booking_items.py` -- Alembic database migration creating `orders` and `booking_items` tables with indices and foreign keys.
- `backend/app/schemas/order.py` -- Define Pydantic validation schemas (`GuestOrderCreate`, `BookingItemOut`, `OrderOut`).
- `backend/app/api/v1/endpoints/public.py` -- Implement `POST /api/v1/public/events/{slug}/orders` validating `session_token`, checking active locks, calculating totals, and committing order draft.
- `backend/tests/test_orders_api.py` -- Comprehensive Pytest suite testing validation rules, mandatory honor declaration, active lock binding, order number generation, and conflict handling.
- `frontend/src/types/order.ts` -- TypeScript interfaces for order submission and response payloads.
- `frontend/src/lib/api.ts` -- API client function `createGuestOrder`.
- `frontend/src/components/checkout/GuestCheckoutForm.tsx` -- Responsive guest form component with contact fields, phone/postal code formatting, legal checkbox, and validation messages.
- `frontend/src/pages/ReservationPage.tsx` -- Main reservation page at `/e/:slug/reservation` with cart summary, live Hold Timer, empty state fallback, and checkout form integration.
- `frontend/src/App.tsx` -- Update URL route resolver to match `/e/:slug/reservation` and render `ReservationPage`.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/models/order.py` -- Create `Order` and `BookingItem` models with UUID PK, event FK, order_number, contact info, status, access_token, and honor declaration timestamp `[Source: ARCHITECTURE-SPINE.md#AD-2, epics.md#Story-2.3]`.
- [x] `backend/app/models/__init__.py` -- Export `Order` and `BookingItem` `[Source: ARCHITECTURE-SPINE.md]`.
- [x] `backend/alembic/versions/004_create_orders_and_booking_items.py` -- Create and run Alembic migration creating `orders` and `booking_items` tables `[Source: ARCHITECTURE-SPINE.md]`.
- [x] `backend/app/schemas/order.py` -- Define Pydantic request and response schemas with strict validation for email, phone, postal code, and mandatory honor declaration `[Source: epics.md#Story-2.3]`.
- [x] `backend/app/api/v1/endpoints/public.py` -- Implement `POST /api/v1/public/events/{slug}/orders` endpoint binding cart session locks to order `[Source: ARCHITECTURE-SPINE.md, epics.md#Story-2.3]`.
- [x] `backend/tests/test_orders_api.py` -- Write automated tests for guest order creation, required fields validation, honor declaration enforcement, and expired lock rejection `[Source: ARCHITECTURE-SPINE.md#Testing-Strategy]`.
- [x] `frontend/src/types/order.ts` -- Create TypeScript models for guest order request and created order entity `[Source: ARCHITECTURE-SPINE.md]`.
- [x] `frontend/src/lib/api.ts` -- Add `createGuestOrder` API client function `[Source: ARCHITECTURE-SPINE.md]`.
- [x] `frontend/src/components/checkout/GuestCheckoutForm.tsx` -- Build accessible, responsive form with clear validation, live feedback, and prominent sworn declaration checkbox `[Source: DESIGN.md, EXPERIENCE.md]`.
- [x] `frontend/src/pages/ReservationPage.tsx` -- Build reservation page with active cart review, hold timer synchronization, and back-to-map navigation `[Source: EXPERIENCE.md#Key-Flows]`.
- [x] `frontend/src/App.tsx` -- Route `/e/:slug/reservation` to `ReservationPage` with fallback navigation `[Source: EXPERIENCE.md#Surfaces]`.
- [x] Verification -- Run backend test suite (`pytest`) and frontend production build (`npm run build`) to ensure zero regressions.

**Acceptance Criteria:**
- Given Monique clicks on "Continuer la réservation" from her cart containing locked stalls,
- When the reservation page `/e/:slug/reservation` loads,
- Then the live Hold Timer reflects remaining cart lock time, and only essential contact fields are shown (Nom, Prénom, Email, Téléphone, Adresse postale),
- And no password or account creation fields exist,
- And an unchecked mandatory checkbox states: "Je certifie sur l'honneur être un particulier et ne pas participer à plus de 2 ventes au déballage dans l'année (art. L310-2 du Code de commerce)",
- When Monique fills all valid contact details and checks the box,
- Then submitting the form successfully creates a pending `Order` with associated `BookingItem`s in the database and advances to the payment step.

## Implementation Notes

- **Backend Architecture & Models:**
  - Implemented `Order` and `BookingItem` SQLAlchemy ORM models in `backend/app/models/order.py` with UUID PKs, relationship mappings to `Event` and `Spot`, and automated generation of human-friendly `order_number` (format `GVG-YYYY-XXXX`) and unguessable 32-byte URL-safe `access_token`.
  - Added relationships in `Event.orders` and `Spot.booking_items`, exporting `Order` and `BookingItem` in `backend/app/models/__init__.py`.
  - Created Alembic database migration `backend/alembic/versions/004_create_orders_and_booking_items.py` establishing `orders` and `booking_items` tables with foreign keys and indexes on `event_id`, `order_number`, `email`, `access_token`, and `status`. Verified full upgrade and downgrade in `test_migrations.py`.
- **Validation Schemas & Public API:**
  - Defined strict Pydantic schemas in `backend/app/schemas/order.py`: `GuestOrderCreate`, `BookingItemOut`, and `OrderOut`.
  - Enforced mandatory sworn declaration check (`honor_declaration_accepted: bool = True`) with the exact French error message: `"L'attestation sur l'honneur est obligatoire pour participer au vide-grenier."`.
  - Added robust validation for phone numbers (8 to 15 digits), postal codes (2 to 10 alphanumeric chars), and email addresses with zero third-party dependency issues.
  - Implemented `POST /api/v1/public/events/{slug}/orders` in `backend/app/api/v1/endpoints/public.py`: verifies active spot locks (`locked_until > now()`), calculates order total price in cents, creates pending order draft with `BookingItem`s, and returns HTTP 201 Created.
  - Implemented `GET /api/v1/public/events/{slug}/orders/{order_id}` with `access_token` authorization check.
  - Returns HTTP 409 Conflict if cart is empty or hold locks have expired, pruning expired locks from the database.
- **Backend Automated Testing:**
  - Added comprehensive Pytest test suite in `backend/tests/test_orders_api.py` covering:
    - Nominal guest order creation with multi-spot cart, total price calculation, and order number format verification.
    - Sworn declaration rejection returning HTTP 422 with the exact required French error message.
    - Empty cart and expired cart conflict handling returning HTTP 409 and releasing expired locks.
    - Contact field validation (email format, missing names, phone length, empty postal code).
    - Passwordless access token authentication and retrieval (`GET /orders/{id}`).
    - Security assertion confirming zero password, password confirmation, or CNI upload fields exist in models or schemas.
  - Entire backend test suite passes: 70 tests passed with 0 errors.
- **Frontend Guest Checkout & Reservation:**
  - Defined TypeScript interfaces in `frontend/src/types/order.ts` and added `createGuestOrder` and `fetchPublicOrder` API helpers in `frontend/src/lib/api.ts`.
  - Created `frontend/src/components/checkout/GuestCheckoutForm.tsx` conforming to `DESIGN.md` (Forest Green theme, touch-friendly 44px+ inputs, max-w-xl layout) and `EXPERIENCE.md` microcopy. Includes field formatting, inline error messages, and prominent sworn statement checkbox (art. L310-2 du Code de commerce).
  - Built `frontend/src/pages/ReservationPage.tsx` at `/e/:slug/reservation` with live Hold Timer badge (amber pill, red pulse under 2 minutes), cart summary card, empty cart fallback with CTA back to map, expired lock handling, and post-submission recap.
  - Updated `frontend/src/App.tsx` URL routing to support both `/e/:slug` (PublicMap) and `/e/:slug/reservation` (ReservationPage) with browser history pushState and popstate synchronization.
  - Wired `onProceedToCheckout` in `PublicEventPage.tsx` to transition seamlessly to `/e/:slug/reservation`.
  - Verified frontend build (`npm run build`) completes cleanly with zero TypeScript or Vite bundling errors.

## Review Triage Log

| Finding | Verdict | Evidence / Disposition |
|---------|---------|------------------------|
| Partial spot expiration in cart allows silent partial order creation | `medium` | Handled: endpoint checks if any locked spot expired and raises HTTP 409 conflict while clearing expired locks. |
| Concurrent double-submission creates duplicate pending orders | `medium` | Handled: endpoint checks for existing pending order on matching spots for this session/email. |
| Held spots hold timer not refreshed on order creation | `medium` | Handled: `locked_until` on spots is extended to `now() + 15 min` upon order creation to allow time for payment. |
| Non-constant-time access_token comparison | `low` | Handled: replaced `order.access_token != access_token` with `secrets.compare_digest`. |
| French grammar error in schema error message ("Le adresse", "Le ville") | `low` | Handled: corrected to "L'adresse est obligatoire." and "La ville est obligatoire.". |
| Email regex too restrictive in backend vs frontend | `low` | Handled: aligned with standard permissive RFC-compatible regex `r"^[^@\s]+@[^@\s]+\.[^@\s]+$"`. |
| Missing BookingItem unit price and linear meterage test assertions | `medium` | Handled: added explicit test assertions in `test_create_guest_order_nominal`. |
| session_token required in schema preventing X-Session-Token header alone | `medium` | Handled: changed schema to `session_token: Optional[str] = None` and added test. |
| Tailwind v4 classes used in Tailwind v3 (outline-hidden, shadow-xs) | `low` | Handled: replaced with `outline-none` and `shadow-sm`. |
| Missing autocomplete and inputMode on guest inputs | `low` | Handled: added `autoComplete` and `inputMode` to all fields in `GuestCheckoutForm.tsx`. |
| Raw "Value error, " prefix shown to user | `low` | Handled: stripped prefix in submit error handling. |
| Potential NaN in timer calculation on unparseable date | `low` | Handled: added NaN check in timer calculation. |
| Missing passive_deletes on Spot.booking_items | `low` | Handled: added `passive_deletes=True` to `booking_items` relationship on `Spot`. |
| Frontend order route persistence / lookup | `false` | Out of scope for Story 2.3; covered by Story 2.4 confirmation and Epic 3 order management. |
| Form unmounting on hold timer expiration | `false` | Intended UX behavior per specification and EXPERIENCE.md when 15m expires. |
| Frontend test coverage absence | `false` | Frontend unit testing is not part of this project's current test runner configuration (backend pytest suite). |

## Verification

**Commands:**
- `.venv/bin/pytest backend/tests/test_orders_api.py backend/tests/test_public_api.py` -- expected: all tests pass
- `PATH=/home/sylvain/projets/gvg/gvg/.tools/node/bin:$PATH npm --prefix frontend run build` -- expected: TypeScript build completes with zero errors


