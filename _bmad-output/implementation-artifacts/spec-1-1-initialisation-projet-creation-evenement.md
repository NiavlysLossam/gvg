---
title: 'Story 1.1: Project Initialization & Event Creation'
type: 'feature'
created: '2026-09-04'
status: 'ready-for-dev'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '_bmad-output/planning-artifacts/architecture/architecture-gvg-2026-09-04/ARCHITECTURE-SPINE.md'
  - '_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** GVG needs a robust initial repository scaffold and database foundation allowing an event organizer (Marc) to register a new flea market event with dates, hours, location, and pricing so it can subsequently be mapped.

**Approach:** Initialize the fullstack project structure (`backend/`, `frontend/`, `docker-compose.yml`, `scripts/install-ubuntu.sh`), configure FastAPI with SQLAlchemy 2.0 and PostgreSQL/PostGIS, implement the `Event` data model and migration, expose REST CRUD endpoints (`POST /api/v1/events`, `GET /api/v1/events/{id_or_slug}`), and build an admin event creation form in Vite/React.

## Boundaries & Constraints

**Always:**
- Store monetary values in integer cents (`price_per_meter_cents`) to avoid floating-point rounding issues.
- Generate standard UUIDs for primary keys and slugify public URLs with collision protection.
- Ensure CORS, Pydantic v2 schemas, and standard error formats RFC 7807 (`{"detail": "..."}`) are used.
- Include PostgreSQL 16 + PostGIS 3.4 in `docker-compose.yml` for unified outdoor & indoor spot coordinates.

**Never:**
- Never require user authentication or passwords in this initial story; keep it direct for organizer testing.
- Never store uploaded ID card scans or personal sensitive identity documents.
- Never hardcode database connection strings; load all configurations via Pydantic settings from environment variables.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Create valid event | Valid title, dates, setup/public hours, address, price per meter (4.00 €) | HTTP 201 Created with UUID, generated slug, status `draft`, `price_per_meter_cents: 400` | N/A |
| Duplicate title collision | Existing event with slug `vide-grenier-saint-michel` | Appends unique counter/hash suffix (e.g. `vide-grenier-saint-michel-2`) | Automatically handled |
| Invalid date range | `end_date` < `start_date` | HTTP 422 Unprocessable Entity with clear validation message | Pydantic model validator |
| Negative price | `price_per_meter` < 0 | HTTP 422 Unprocessable Entity | Pydantic `gt=0` constraint |
| Get event by ID or Slug | Existing event UUID or slug | HTTP 200 OK with full event payload | HTTP 404 Not Found if non-existent |

</frozen-after-approval>

## Code Map

- `backend/app/main.py` -- FastAPI application factory, CORS middleware, API router mounting, health check endpoint.
- `backend/app/core/config.py` -- Application settings (database URL, CORS origins, environment) via `pydantic-settings`.
- `backend/app/core/database.py` -- SQLAlchemy engine, declarative Base, and DB session dependency (`get_db`).
- `backend/app/models/event.py` -- SQLAlchemy `Event` model with timestamps, UUID, status enum, and pricing in cents.
- `backend/app/schemas/event.py` -- Pydantic v2 schemas (`EventCreate`, `EventUpdate`, `EventResponse`, `EventListResponse`).
- `backend/app/api/v1/endpoints/events.py` -- REST route handlers for creating, listing, and retrieving events.
- `backend/app/api/v1/router.py` -- Main v1 APIRouter aggregating all feature endpoints.
- `backend/alembic/` -- Database migration configuration and initial migration script for `events`.
- `backend/tests/test_events_api.py` -- Pytest suite validating event creation, edge-case validations, and retrieval.
- `frontend/src/` -- Vite + React SPA with Tailwind CSS, event creation form, and event overview card with "Brouillon / Configuration du plan" status.
- `docker-compose.yml` -- Orchestrates PostGIS 16-3.4, backend FastAPI service, and frontend dev server.
- `scripts/install-ubuntu.sh` -- Shell script scaffold for native Ubuntu 22.04/24.04 LTS deployment (AD-8).

## Tasks & Acceptance

**Execution:**
- [ ] `backend/` -- Scaffold Python FastAPI environment, dependencies (`pyproject.toml` / `requirements.txt`), and app architecture -- Foundation for GVG API.
- [ ] `backend/app/models/event.py` -- Define `Event` model and database schema -- Persists event metadata with UUID and cents pricing.
- [ ] `backend/alembic/` -- Generate initial migration for table `events` -- Enables reproducible schema migrations.
- [ ] `backend/app/api/v1/endpoints/events.py` -- Implement event creation (`POST`) and retrieval (`GET`) endpoints -- Provides backend API for admin and public views.
- [ ] `backend/tests/test_events_api.py` -- Write automated tests for event endpoints and validations -- Ensures zero regression and robust validation.
- [ ] `frontend/` -- Initialize React Vite application with Tailwind CSS and build Event Creation form -- Allows Marc to configure an event in the browser.
- [ ] `docker-compose.yml` -- Configure Docker Compose file with PostGIS 16-3.4 and GVG services -- Provides portable local development environment.
- [ ] `scripts/install-ubuntu.sh` -- Scaffold native Ubuntu deployment script -- Implements AD-8 deployment requirement.

**Acceptance Criteria:**
- Given Marc opens the GVG web application,
- When he inputs event details (title "Vide-Grenier de Printemps", dates, setup hours 06:00-08:00, public hours 08:00-18:00, location address, and rate 4.00 €/m),
- Then the backend persists the event into PostgreSQL with a unique UUID and slug, returning HTTP 201,
- And the event is visible on the dashboard with status "Brouillon / Configuration du plan", ready for map calibration (Story 1.2).

## Implementation Notes

## Spec Change Log

## Review Triage Log

## Design Notes

- **Slug Generation:** Derived using `python-slugify` with fallback counter check against existing slugs in the database.
- **Price Precision:** Frontend accepts decimal euros (`4.00`), converted to integer cents (`400`) before sending or in schema serializer.
- **Database Engine:** Async/sync SQLAlchemy 2.0 session pattern compatible with FastAPI dependencies. SQLite fallback support for local unit tests when PostgreSQL daemon is not active.

## Verification

**Commands:**
- `pytest backend/tests/test_events_api.py` -- expected: All event creation and validation tests pass.
- `python -m uvicorn app.main:app --app-dir backend` -- expected: Server starts and `/docs` serves OpenAPI documentation.
- `npm --prefix frontend run build` -- expected: Frontend builds successfully without errors.

**Manual checks (if no CLI):**
- Open `http://localhost:8000/docs` in browser to verify interactive Swagger UI for `POST /api/v1/events` and `GET /api/v1/events/{id_or_slug}`.
- Submit the event creation form from `http://localhost:5173` and confirm the new event appears in draft status.
