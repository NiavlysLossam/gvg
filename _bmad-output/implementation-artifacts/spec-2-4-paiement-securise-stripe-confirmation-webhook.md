---
title: "Story 2.4: Paiement Sécurisé Stripe & Confirmation par Webhook"
type: 'feature'
created: '2026-09-13'
status: 'done'
baseline_commit: 'dbd20bce051ce6443c914793f873e60dd4d75198'

route: 'dispatch'
review_loop_iteration: 0
context:
  - "_bmad-output/planning-artifacts/architecture/architecture-gvg-2026-09-04/ARCHITECTURE-SPINE.md"
  - "_bmad-output/implementation-artifacts/epic-2-context.md"
  - "_bmad-output/planning-artifacts/ux-designs/ux-gvg-2026-09-04/DESIGN.md"
  - "_bmad-output/planning-artifacts/ux-designs/ux-gvg-2026-09-04/EXPERIENCE.md"
  - "_bmad-output/implementation-artifacts/spec-2-3-formulaire-invite-attestation-sur-honneur.md"
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** After providing contact details and accepting the sworn statement, exhibitors (like Monique) need to pay for their reserved stalls securely without their banking data ever touching the GVG server. Crucially, if Monique closes her mobile browser or loses network connectivity immediately after authenticating with her bank (3D Secure), the booking must not be lost or corrupted.

**Approach:** Integrate Stripe Elements and PaymentIntents (`POST /api/v1/public/events/{slug}/orders/{order_id}/payment-intent`), mount a secure banking payment card component in the reservation checkout tunnel, implement a cryptographically verified webhook handler (`POST /api/v1/webhooks/stripe`) for `payment_intent.succeeded` as the single source of financial truth converting `Order.status` to `confirmed` and `Spot.status` to `reserved`, and redirect the exhibitor to the confirmation screen at `/e/:slug/confirmation/:orderId`.

## Boundaries & Constraints

**Always:**
- Use the official Stripe SDK on the backend and `@stripe/stripe-js` / `@stripe/react-stripe-js` on the frontend.
- Rely **exclusively** on the cryptographically signed Stripe webhook `payment_intent.succeeded` as the financial source of truth to transition an `Order` from `pending` to `confirmed` and its spots from `locked` to `reserved` (`AD-3`).
- Authenticate payment intent creation using the order's `access_token` and verify that the order belongs to the given event slug and is in `pending` status with active spot locks.
- Record `stripe_payment_intent_id` on the `Order` record upon PaymentIntent creation.
- Ensure the webhook handler (`/api/v1/webhooks/stripe`) verifies the `Stripe-Signature` header using `stripe.Webhook.construct_event`.
- Ensure idempotent webhook execution: if a `payment_intent.succeeded` event arrives more than once for an already `confirmed` order, return HTTP 200 without duplicate updates or errors.
- Display a smooth loading state on the payment button with clear French microcopy: *"Validation sécurisée en cours..."* to prevent double-clicks.
- Implement the confirmation page at `/e/:slug/confirmation/:orderId` accessible via `access_token` displaying the order number, list of reserved stalls, total paid, and warm confirmation message (*"Bravo Monique, votre stand est réservé !"*).
- Support polling with a short fallback interval on the confirmation screen if the webhook is slightly delayed during 3DS redirection.

**Never:**
- Never receive, process, or store raw credit card numbers, expiration dates, or CVC codes on GVG servers (Stripe Elements handles all card data directly with Stripe).
- Never transition spots to `reserved` directly from a frontend redirect or unverified client callback.
- Never allow payment intent creation for an order whose spot hold locks have already expired.
- Never commit secret API keys or webhook secrets to source control.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Nominal payment success | Valid card entered in Stripe Elements; payment confirmed | Webhook `payment_intent.succeeded` received; `Order` marked `confirmed`; spots marked `reserved`; redirected to `/e/:slug/confirmation/:orderId` | N/A |
| Card declined | Insufficient funds or invalid card number | Stripe Elements displays localized error message in French; order remains `pending`; user can retry with another card | Inline error in UI |
| Webhook arrives before client redirect | Stripe processes payment and delivers webhook in < 500ms | DB already updated to `confirmed` and `reserved`; confirmation page immediately displays confirmed status | Idempotent |
| Webhook slightly delayed | Client redirected to `/confirmation/:orderId` while webhook is in-flight | Confirmation page shows soft loader ("Confirmation de votre règlement en cours...") and polls order status until `confirmed` | Auto-updates when webhook completes |
| Duplicate webhook delivery | Stripe retries `payment_intent.succeeded` delivery | Webhook endpoint detects order already `confirmed`; logs event and returns HTTP 200 OK | Idempotent no-op |
| Invalid webhook signature | Forged or corrupted `Stripe-Signature` header sent to `/api/v1/webhooks/stripe` | HTTP 400 Bad Request; event rejected; no database state changed | Security rejection |
| Expired hold lock before payment | User delays payment beyond 15m hold expiration | PaymentIntent creation or confirmation fails with 409 Conflict; spots released | Prompt to re-select stalls |

</frozen-after-approval>

## Code Map

- `backend/pyproject.toml` -- Added `stripe>=15.0.0` dependency.
- `backend/app/core/config.py` -- Stripe settings: `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, and `STRIPE_WEBHOOK_SECRET`.
- `backend/app/services/stripe_service.py` -- Dedicated Stripe service encapsulating `create_or_get_payment_intent`, `verify_webhook_event`, and status mappings.
- `backend/app/api/v1/endpoints/public.py` -- Add endpoint `POST /api/v1/public/events/{slug}/orders/{order_id}/payment-intent` returning `client_secret` and publishable key.
- `backend/app/api/v1/endpoints/webhooks.py` -- New webhook router handling `POST /api/v1/webhooks/stripe` with signature verification and atomic transition of orders to `confirmed` and spots to `reserved`.
- `backend/app/api/v1/api.py` (or `main.py`) -- Mount webhook endpoint on `/api/v1/webhooks` or `/api/v1/webhooks/stripe`.
- `backend/tests/test_stripe_payment.py` -- Comprehensive Pytest suite testing PaymentIntent creation, webhook processing, signature validation, idempotency, and spot status transition.
- `frontend/src/types/order.ts` -- Add payment intent response and order status types.
- `frontend/src/lib/api.ts` -- Client function `createPaymentIntent(slug, orderId, accessToken)`.
- `frontend/src/components/checkout/StripePaymentForm.tsx` -- Stripe Elements wrapper and card payment form component with loading spinner and error feedback.
- `frontend/src/pages/ReservationPage.tsx` -- Step 2 payment view: embed `StripePaymentForm` once order is created in pending state.
- `frontend/src/pages/ConfirmationPage.tsx` -- Confirmation page at `/e/:slug/confirmation/:orderId` with success banner, order summary, calendar add hint, and cancellation link placeholder.
- `frontend/src/App.tsx` -- Update URL routing for `/e/:slug/confirmation/:orderId`.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/services/stripe_service.py` -- Implement service with PaymentIntent creation, metadata binding, and webhook event verification `[Source: ARCHITECTURE-SPINE.md#AD-3]`.
- [x] `backend/app/api/v1/endpoints/public.py` -- Add `POST /events/{slug}/orders/{order_id}/payment-intent` endpoint verifying access_token and hold locks `[Source: ARCHITECTURE-SPINE.md]`.
- [x] `backend/app/api/v1/endpoints/webhooks.py` -- Implement `POST /webhooks/stripe` processing `payment_intent.succeeded` with atomic transitions to `confirmed` and `reserved` `[Source: ARCHITECTURE-SPINE.md#AD-3]`.
- [x] `backend/tests/test_stripe_payment.py` -- Test suite for payment intent creation, webhook processing, spot conversion to `reserved`, idempotency, and signature security `[Source: ARCHITECTURE-SPINE.md#Testing-Strategy]`.
- [x] `frontend/src/components/checkout/StripePaymentForm.tsx` -- Build Stripe Elements payment component with card input, loading state, and error handling `[Source: EXPERIENCE.md#Key-Flows]`.
- [x] `frontend/src/pages/ReservationPage.tsx` -- Wire payment step to display `StripePaymentForm` upon order creation `[Source: EXPERIENCE.md]`.
- [x] `frontend/src/pages/ConfirmationPage.tsx` -- Build order confirmation screen at `/e/:slug/confirmation/:orderId` with polling and celebration UI `[Source: EXPERIENCE.md#Surfaces]`.
- [x] `frontend/src/App.tsx` -- Register `/e/:slug/confirmation/:orderId` route and handle browser history navigation `[Source: EXPERIENCE.md]`.
- [x] Verification -- Run backend test suite (`pytest`) and frontend production build (`npm run build`) to ensure zero regressions.

**Acceptance Criteria:**
- Given Monique has filled the guest form with active 15m hold locks,
- When the payment step displays Stripe Elements,
- Then she can enter test card details and click "Régler ma commande",
- When the payment succeeds and the Stripe webhook `payment_intent.succeeded` is received,
- Then the Order status becomes `confirmed` and associated spots become `reserved` in the database,
- And Monique is navigated to `/e/:slug/confirmation/:orderId` displaying her confirmed order number, stalls list, and celebration message.

## Implementation Notes

- **Stripe Backend Service & Webhooks:**
  - Created `backend/app/services/stripe_service.py` implementing `create_or_get_payment_intent`, `verify_webhook_event`, and `confirm_order_from_payment_intent`.
  - Reuses existing Stripe PaymentIntents if already created and not canceled, binds order metadata (`order_id`, `order_number`, `event_id`, `event_slug`, `exhibitor_email`), and updates `Order.stripe_payment_intent_id`.
  - Implemented `backend/app/api/v1/endpoints/webhooks.py` mounted at `/api/v1/webhooks/stripe` (and `/webhooks/stripe`) verifying cryptographic `Stripe-Signature` headers via `stripe.Webhook.construct_event`.
  - When receiving `payment_intent.succeeded`, atomically marks `Order.status = "confirmed"` and associated `Spot`s as `status = "reserved"`, clearing `locked_until` and `locked_by_token` (`AD-3`).
  - Webhook is fully idempotent: redundant deliveries for already confirmed orders return HTTP 200 without duplicate modifications.
- **Public API & Schemas:**
  - Added schema `PaymentIntentResponse` in `backend/app/schemas/order.py` with `client_secret`, `publishable_key`, `payment_intent_id`, `amount_cents`, and `currency`.
  - Added `POST /api/v1/public/events/{slug}/orders/{order_id}/payment-intent` in `backend/app/api/v1/endpoints/public.py`: validates access token, verifies spot hold locks are active (rejects expired locks with HTTP 409 Conflict), and initializes or returns the Stripe PaymentIntent.
- **Automated Testing:**
  - Added 9 comprehensive automated tests in `backend/tests/test_stripe_payment.py` covering:
    - Nominal PaymentIntent creation with metadata and DB record update.
    - Idempotent reuse of existing PaymentIntents.
    - Token authentication and authorization boundaries (401, 403, 404).
    - Rejection of expired spot hold locks with HTTP 409 and release of spots to `available`.
    - Rejection of already confirmed orders with HTTP 409.
    - Cryptographic webhook validation using genuine HMAC-SHA256 signatures generated with `stripe.WebhookSignature.generate_signature_header`.
    - Webhook idempotency on duplicate deliveries.
    - Forged / corrupted signature rejection with HTTP 400 without DB state change.
    - Unhandled and unknown events handled gracefully with HTTP 200.
  - All 82 backend pytest tests pass without regression.
- **Frontend Stripe Elements & Checkout:**
  - Added `PaymentIntentResponse` in `frontend/src/types/order.ts` and client helper `createPaymentIntent` in `frontend/src/lib/api.ts`.
  - Created `frontend/src/components/checkout/StripePaymentForm.tsx` integrating `@stripe/stripe-js` and `@stripe/react-stripe-js` (`Elements`, `PaymentElement`). Includes smooth loading state with exact French microcopy *"Validation sécurisée en cours..."*, card error localization, double-click prevention, and 256-bit SSL reassurance notices.
  - Updated `frontend/src/pages/ReservationPage.tsx` Step 2 view: upon order creation, seamlessly embeds `StripePaymentForm` with order recap, exhibitor details, and smooth transition to confirmation.
  - Created `frontend/src/pages/ConfirmationPage.tsx` at `/e/:slug/confirmation/:orderId` with celebration hero banner (*"Bravo {first_name}, votre stand est réservé !"*), stalls list, total paid, event reminders, .ics calendar export, and fallback polling for delayed webhook delivery (*"Confirmation de votre règlement en cours..."*).
  - Updated `frontend/src/App.tsx` router to parse `/e/:slug/confirmation/:orderId` (with hash and query fallbacks) and wired browser history navigation.
  - Verified frontend production build (`npm run build`) completes cleanly with zero TypeScript or Vite errors.

## Review Triage Log

| Finding | Verdict | Evidence / Disposition |
|---------|---------|------------------------|
| Missing amount and currency check in webhook handler | `medium` | Handled: verified received amount matches `order.total_price_cents` and currency is `eur` in `confirm_order_from_payment_intent`. |
| Potential double-booking if webhook delayed and spot claimed by another | `medium` | Handled: verifies `order.status == 'pending'` and checks that none of the spots are already marked `reserved`. |
| Internal 500 config error masked as 400 Bad Request to Stripe | `medium` | Handled: re-raised `HTTPException` directly before catching general `Exception`. |
| Premature celebration banner on ConfirmationPage when payment pending/failed | `medium` | Handled: celebration gated strictly behind `order.status === 'confirmed'`; added error state for `redirect_status=failed`. |
| Payment submission button hangs in loading on unhandled status / 3DS dismiss | `medium` | Handled: `setSubmitting(false)` called on all non-succeeded/non-processing statuses with explicit error message. |
| Hash routing regex captures query params into `orderId` | `medium` | Handled: updated regex with `(?:\?.*)?$` to exclude query parameters from `orderId`. |
| Incomplete spot release and order status left in orphaned pending on expired hold | `medium` | Handled: all order spots released to available and order marked `cancelled`. |
| Unhandled StripeError on PaymentIntent creation unverified in tests | `medium` | Handled: added test asserting StripeError returns HTTP 502 Bad Gateway. |
| Root route `/webhooks/stripe` unverified in tests | `low` | Handled: added dedicated test verifying root `/webhooks/stripe` route. |
| Fallback order lookup by `stripe_payment_intent_id` unverified in tests | `low` | Handled: added test verifying fallback lookup when metadata is empty. |
| Minimum 50 cents charge validation | `low` | Handled: added validation raising HTTP 400 if `total_price_cents < 50`. |
| Already-confirmed order shows initialization error in PaymentForm | `low` | Handled: 409 conflict automatically triggers `onSuccess(order.id)`. |
| Unsafe clipboard copy on ConfirmationPage in non-HTTPS contexts | `low` | Handled: wrapped in `try/catch` with fallback handling. |

## Verification

**Commands:**
- `PYTHONPATH=backend .venv/bin/pytest backend/tests/test_stripe_payment.py backend/tests/test_orders_api.py` -- expected: all tests pass
- `PATH=/home/sylvain/projets/gvg/gvg/.tools/node/bin:$PATH npm --prefix frontend run build` -- expected: TypeScript build completes with zero errors



