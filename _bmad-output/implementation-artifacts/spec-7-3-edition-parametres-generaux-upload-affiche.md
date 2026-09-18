---
title: 'Story 7.3: Édition des Paramètres Généraux & Upload d''Affiche (Max 5 Mo)'
type: 'feature'
created: '2026-09-18'
status: 'done'
baseline_commit: 'b4c28c83ebec89938170b74d123ecdcf139730aa'
route: 'dispatch'
review_loop_iteration: 0
context:
  - _bmad-output/planning-artifacts/epics.md
  - _bmad-output/planning-artifacts/architecture/architecture-gvg-2026-09-04/ARCHITECTURE-SPINE.md
  - backend/app/models/event.py
  - backend/app/schemas/event.py
  - backend/app/api/v1/endpoints/events.py
  - frontend/src/types/event.ts
  - frontend/src/lib/api.ts
  - frontend/src/components/EventCard.tsx
  - frontend/src/pages/EventSettingsPage.tsx
  - frontend/src/App.tsx
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Organizers need to be able to edit all general parameters of their event (title, description, start/end dates, exhibitor setup times, public opening hours, physical address, organizer contact email, pricing per meter, manual approval toggle, status, and exhibitor regulations) and upload or replace the official event poster (up to 5 MB, JPEG/PNG/WebP) with immediate live preview and persistence.

**Approach:**
1. Backend:
   - Provide endpoint `POST /api/v1/events/{id_or_slug}/poster` to upload an official poster up to 5 MB, with strict MIME and magic bytes validation (PNG, JPEG, WebP), stored securely in `uploads/posters/`, updating `event.poster_image_url`.
   - Provide endpoint `DELETE /api/v1/events/{id_or_slug}/poster` to remove the poster and reset `poster_image_url` to `None`.
   - Ensure `PATCH /api/v1/events/{id_or_slug}` supports updating all general event parameters (including `poster_image_url=None`, `price_per_meter`, `status`, etc.) with proper authorization check (`check_event_ownership`).
2. Frontend:
   - Create `EventSettingsPage.tsx` with comprehensive form inputs for general settings, responsive layout, status selector, and dedicated poster upload section with drag & drop, file picker, file size validation (<= 5 MB), format validation, image preview, removal button, and direct link to the public showcase (`/e/:slug`).
   - Add API helpers `uploadEventPoster` and `deleteEventPoster` in `frontend/src/lib/api.ts`.
   - Add "Paramètres" button in `EventCard.tsx` and integrate the settings view/tab in `App.tsx`.

## Boundaries & Constraints

**Always:**
- Strictly enforce 5 MB maximum file size both in frontend (immediate user feedback before upload) and backend (`HTTP_413_REQUEST_ENTITY_TOO_LARGE`).
- Strictly validate MIME types and magic bytes for PNG, JPEG, and WebP (`HTTP_415_UNSUPPORTED_MEDIA_TYPE`).
- Enforce event ownership check (`check_event_ownership`): only event owner or super-admin can edit settings or upload/delete posters.
- Support lookup by either UUID or slug on both poster upload, deletion, and patch endpoints.
- Update `poster_image_url` immediately and return `EventResponse`.
- Changes saved must be immediately reflected on public showcase and portal.

**Never:**
- Never accept files over 5 MB.
- Never accept spoofed or non-image files.
- Never allow unauthenticated or unauthorized users to modify event settings or upload/delete posters.
- Never break existing event fields, spots, or pricing validation.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Edit event parameters | Valid title, dates, times, price, status | `PATCH /api/v1/events/{id}` returns 200 with updated `EventResponse`, changes persisted | 422 if end_date < start_date or price <= 0 |
| Upload valid poster (PNG/JPG/WebP <= 5MB) | Valid image file <= 5MB | `POST /api/v1/events/{id}/poster` returns 200, saves to `uploads/posters/`, sets `poster_image_url` | 200 with updated event |
| Upload poster > 5MB | Image file > 5MB (e.g. 5.5MB) | Backend returns 413, frontend blocks with error alert before sending | HTTP 413 "L'affiche dépasse la taille maximale autorisée de 5 Mo" |
| Upload invalid format (PDF, TXT) | Non-image file or invalid MIME | Backend returns 415, frontend warns about format | HTTP 415 "Format non supporté (PNG, JPEG, WebP uniquement)" |
| Upload spoofed file | PNG MIME header with text content | Backend checks magic bytes and returns 415 | HTTP 415 "Le contenu du fichier n'est pas une image valide" |
| Upload empty file | 0-byte file | Backend returns 422 | HTTP 422 "Le fichier téléversé est vide" |
| Delete poster | Click "Supprimer l'affiche" or `DELETE /poster` | Removes poster, sets `poster_image_url=None`, returns updated event | 200 OK |
| Non-owner tries to edit or upload | Non-owner authenticated user | Forbidden | HTTP 403 "You do not have permission to modify this event" |

</frozen-after-approval>

## Code Map

- `backend/app/main.py` -- Ensure `uploads/posters` directory is initialized.
- `backend/app/api/v1/endpoints/events.py` -- Add `POST /{id_or_slug}/poster` and `DELETE /{id_or_slug}/poster`.
- `backend/tests/test_events_api.py` -- Comprehensive unit and integration tests for poster upload, size check (5MB), MIME & magic bytes checks, deletion, and ownership.
- `frontend/src/lib/api.ts` -- Add `uploadEventPoster` and `deleteEventPoster`.
- `frontend/src/pages/EventSettingsPage.tsx` -- New page component for event settings and poster upload/preview.
- `frontend/src/components/EventCard.tsx` -- Add "Paramètres" button with callback `onEditSettings`.
- `frontend/src/App.tsx` -- Integrate `EventSettingsPage`, `activeTab: 'settings'`, routing, and notifications.

