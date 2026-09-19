---
title: 'Story 8.1: Découpage en Onglets de la Gestion des Inscriptions'
type: 'feature'
created: '2026-09-19'
status: 'done'
baseline_commit: 'c4dda08'
route: 'dispatch'
review_loop_iteration: 1
context:
  - _bmad-output/planning-artifacts/epics.md
  - _bmad-output/planning-artifacts/architecture/architecture-gvg-2026-09-04/ARCHITECTURE-SPINE.md
  - frontend/src/pages/RegistrationsPage.tsx
  - frontend/src/components/RemindersCard.tsx
  - frontend/src/components/BroadcastModal.tsx
  - frontend/src/components/ManualBookingModal.tsx
  - frontend/src/types/order.ts
  - frontend/src/lib/api.ts
  - frontend/src/App.tsx
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Currently, [`RegistrationsPage.tsx`](file:///home/sylvain/projets/gvg/gvg/frontend/src/pages/RegistrationsPage.tsx) is a single, dense column containing over 1,900 lines of mixed concerns: KPI cards, reminders configuration, manual registration dialogs, pending moderation cards, pending cancellation cards, bulk event cancellation, and the large orders table with sorting and filtering. This creates visual clutter and high cognitive load for organizers who need to focus specifically on check-in, on-site walk-ins, disputes, or attendee emails.

**Approach:**
Refactor and modularize the registrations experience into 4 clear, dedicated horizontal tabs:
1. **Inscriptions (`inscriptions`)**:
   - High-level KPIs and occupancy progress bar.
   - Clean orders table with full search, status filters (All, En ligne, Hors-ligne, En attente, Annulées), sorting, per-row and bulk selection, attestation PDF links, and pagination.
   - Action bar for official check-in sheets (PDF / Excel).
2. **Guichet sur place (`guichet`)**:
   - Dedicated physical walk-in registration workflow.
   - Integrated quick registration form for on-site cash, check, or complimentary tickets with available spot selection.
   - Summary of offline collections (total cash, total checks, number of exhibitors registered at the counter).
3. **Modération & Litiges (`moderation`)**:
   - Dynamic alert badge on the tab showing the count of items requiring action (`pending_approvals + pending_cancellations`).
   - Moderation toggle switch (manual approval mode on/off with explanation).
   - Dedicated Approval queue for pending orders with instant "Approve" (capture funds) and "Reject" (release spots) actions.
   - Dedicated Cancellation & Refund requests queue with exhibitor's stated reason, and arbitration actions ("Approve refund" or "Reject cancellation").
   - Protected Emergency Event Cancellation & Bulk Refund modal trigger.
4. **Communications (`communications`)**:
   - Mass e-mail broadcast trigger ([`BroadcastModal`](file:///home/sylvain/projets/gvg/gvg/frontend/src/components/BroadcastModal.tsx)) with dynamic tags.
   - Scheduled reminder cards ([`RemindersCard`](file:///home/sylvain/projets/gvg/gvg/frontend/src/components/RemindersCard.tsx)) for J-7 and J-2 with active/upcoming window status and manual trigger options.
   - Email audit logs / transmission history link or overview.

**URL Synchronization:**
- Active tab is read from and synchronized to the URL query parameter `?tab=inscriptions|guichet|moderation|communications` using browser history (`pushState`/`replaceState`), supporting bookmarks, direct links, and browser back/forward buttons without losing context.

## Boundaries & Constraints

**Always:**
- Keep all existing actions and functionality intact (approvals, rejections, refunds, bulk cancellation, email broadcast, reminder triggers, manual bookings, checkin exports).
- Synchronize tab state with URL query parameter `?tab=...` (defaulting cleanly to `inscriptions`).
- Maintain dynamic badge counts (pending moderations and cancellations) on the "Modération & Litiges" tab.
- Modularize sub-views into clean components under `frontend/src/pages/registrations/`.
- Ensure 100% test suite and production build pass.

**Never:**
- Never break existing URL paths (e.g. `/admin/events/{id}/inscriptions`).
- Never lose search queries or pagination state unexpectedly when switching between tabs if data can be preserved.
- Never introduce regressions in backend endpoints or existing order workflows.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Direct Navigation without tab | `/admin/events/123/inscriptions` | Opens tab `inscriptions` by default, sets URL to `?tab=inscriptions` | Clean fallback to 'inscriptions' |
| Direct Navigation with query param | `.../inscriptions?tab=moderation` | Opens tab `moderation` directly | Preserves query parameter |
| Invalid tab query param | `.../inscriptions?tab=unknown` | Gracefully falls back to `inscriptions` | No crash, defaults to 'inscriptions' |
| Pending Moderation Badge | 2 pending approvals, 1 cancellation | Tab shows badge with "3" | Live update upon approval/refund |
| Browser Back/Forward | User clicks browser back | Tab updates seamlessly to previous tab | Popstate event listener |
| Walk-in Guichet Submission | User records cash order on Guichet tab | Order created, stats update, stays on Guichet tab with success toast | Form validation error toast if invalid |

</frozen-after-approval>

## Code Map

- `frontend/src/pages/registrations/RegistrationsTab.tsx` -- Table view, filters, search, sorting, pagination, and KPI cards.
- `frontend/src/pages/registrations/GuichetTab.tsx` -- On-site walk-in registration form, spot picker, and cash/check summary.
- `frontend/src/pages/registrations/ModerationTab.tsx` -- Approval queue, cancellation arbitration, moderation toggle, emergency bulk cancellation.
- `frontend/src/pages/registrations/CommunicationsTab.tsx` -- Bulk email broadcast, J-7/J-2 reminders card, and email logs.
- `frontend/src/pages/RegistrationsPage.tsx` -- Main container, state management, tab headers with badges, and URL synchronization.
- `frontend/src/App.tsx` -- Admin route integration and URL state support.
- `backend/tests/` -- Ensure all existing tests pass without regressions.

## Review Records

### Review 1: Blind Hunter, Edge Case Hunter, Verification Gap Reviewer
- **Findings Identified**:
  1. *State leakage across tabs*: Filtered `orders` starved `GuichetTab` and `ModerationTab`. Remediated by fetching `allOrders` concurrently in `loadData` and providing it to Guichet & Moderation tabs.
  2. *Row actions for cancellation requests*: Missing arbitration actions in `RegistrationsTab`. Remediated by adding `onOpenRejectCancellationModal` and rendering Rembourser / Refuser buttons for `cancellation_requested` rows.
  3. *Missing Notes / Réf column*: Remediated by restoring the `Notes / Réf` table column and cell displaying check numbers, internal notes, and cancellation reasons.
  4. *Missing adminNotes in Guichet*: Remediated by adding an internal notes `<textarea>` in `GuichetTab.tsx`.
  5. *Negative custom price validation & 422 error parsing*: Remediated in `GuichetTab.tsx` with positive validation and robust array detail parsing.
  6. *Event cancellation checks*: Remediated in `GuichetTab.tsx` and `CommunicationsTab.tsx` with disabled states on cancelled events.
  7. *Dead code removal*: Removed unreachable `ManualBookingModal` and `isModalOpen` state from `RegistrationsPage.tsx`.
  8. *WAI-ARIA Accessibility*: Added `role="tablist"`, `role="tab"`, `aria-selected`, and `role="tabpanel"`.
  9. *Tailwind CSS cleanup*: Replaced invalid `shadow-2xs`, `rounded-xs`, `backdrop-blur-xs`, and `py-0.2` with valid Tailwind utilities.
  10. *Pagination bounds & Email truncate*: Added bounds safeguard upon order deletion and `inline-block truncate` on emails.
- **Verification**:
  - `npm run build`: 100% clean build (TypeScript compilation & Vite bundle).
  - `pytest`: 295/295 backend tests passed (including all 43 admin orders, moderation, and arbitration tests).

