---
title: 'Story 1.1: Project Initialization & Event Creation'
type: 'feature'
created: '2026-09-04'
status: 'done'
baseline_commit: 'fd0d90ca60d177f09b7d6811e776ee774220de9a'
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
- [x] `backend/` -- Scaffold Python FastAPI environment, dependencies (`pyproject.toml` / `requirements.txt`), and app architecture -- Foundation for GVG API.
- [x] `backend/app/models/event.py` -- Define `Event` model and database schema -- Persists event metadata with UUID and cents pricing.
- [x] `backend/alembic/` -- Generate initial migration for table `events` -- Enables reproducible schema migrations.
- [x] `backend/app/api/v1/endpoints/events.py` -- Implement event creation (`POST`) and retrieval (`GET`) endpoints -- Provides backend API for admin and public views.
- [x] `backend/tests/test_events_api.py` -- Write automated tests for event endpoints and validations -- Ensures zero regression and robust validation.
- [x] `frontend/` -- Initialize React Vite application with Tailwind CSS and build Event Creation form -- Allows Marc to configure an event in the browser.
- [x] `docker-compose.yml` -- Configure Docker Compose file with PostGIS 16-3.4 and GVG services -- Provides portable local development environment.
- [x] `scripts/install-ubuntu.sh` -- Scaffold native Ubuntu deployment script -- Implements AD-8 deployment requirement.

**Acceptance Criteria:**
- Given Marc opens the GVG web application,
- When he inputs event details (title "Vide-Grenier de Printemps", dates, setup hours 06:00-08:00, public hours 08:00-18:00, location address, and rate 4.00 €/m),
- Then the backend persists the event into PostgreSQL with a unique UUID and slug, returning HTTP 201,
- And the event is visible on the dashboard with status "Brouillon / Configuration du plan", ready for map calibration (Story 1.2).

## Implementation Notes

- Fully implemented backend scaffold with FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, and pytest test suite.
- Implemented `Event` model with integer cents (`price_per_meter_cents`), UUID primary key, timestamps, collision-protected slug generation using `python-slugify`, and default status `draft`.
- Exposed REST endpoints `POST /api/v1/events`, `GET /api/v1/events`, `GET /api/v1/events/{id_or_slug}`, and `PATCH /api/v1/events/{id_or_slug}` with RFC 7807 problem details error responses.
- Configured Alembic initial migration `001_initial_events_table.py` for reproducible schema management.
- Implemented frontend React 18 SPA with Vite, Tailwind CSS, Lucide icons, event creation form with real-time validations, and event overview cards displaying status "Brouillon / Configuration du plan".
- Added multi-container `docker-compose.yml` (PostGIS 16-3.4, FastAPI backend, React frontend) and automated native Ubuntu deployment script `scripts/install-ubuntu.sh` implementing AD-8.
- Ran automated test suite `pytest backend/tests/test_events_api.py`: 7/7 tests passed.
- Built production frontend bundle `npm --prefix frontend run build`: 0 errors.

## Spec Change Log

## Review Triage Log

| ID | Location | Verdict | Evidence | Route |
|---|---|---|---|---|
| BH-1 | backend/app/api/v1/endpoints/events.py | medium | Unhandled IntegrityError during concurrent slug generation if multiple requests insert the same slug simultaneously. | patch |
| BH-2 | backend/app/api/v1/endpoints/events.py:142 | medium | Self-collision on title update when slugify(title) matches current event slug, unnecessarily incrementing counter suffix. | patch |
| BH-3 | backend/app/schemas/event.py:80 | medium | Partial PATCH with only start_date or end_date can invert the schedule if not validated against existing database values. | patch |
| BH-4 | backend/tests/test_events_api.py | low | Missing test coverage for PATCH endpoint and list pagination query parameters. | patch |
| BH-5 | backend/app/schemas/event.py:10,26 | low | map_type and status fields are unconstrained strings rather than Literal or Enums. | patch |
| BH-6 | backend/app/schemas/event.py:9,25 | low | description and rules_text lack max_length boundaries. | patch |
| BH-7 | backend/app/main.py:16 | medium | Base.metadata.create_all in lifespan swallows exceptions and bypasses Alembic table tracking in production. | patch |
| BH-8 | alembic.ini | low | Duplicate alembic.ini in root and backend/ risks configuration divergence. | patch |
| BH-9 | backend/app/main.py:44 | low | RFC 7807 problem details only implemented for RequestValidationError; HTTPException lacks code attribute. | patch |
| BH-10 | docker-compose.yml / vite.config.ts | medium | Frontend container proxy to localhost:8000 fails inside Docker where backend is on service host 'backend'. | patch |
| BH-11 | frontend/src/lib/api.ts:3 | medium | Hardcoded API_BASE ignores VITE_API_URL environment variable. | patch |
| BH-12 | frontend/tsconfig.tsbuildinfo | low | Local build cache tsconfig.tsbuildinfo is committed and missing in .gitignore. | patch |
| BH-13 | scripts/install-ubuntu.sh:60 | low | Glob postgresql-*-postgis-* is unquoted and may trigger shell expansion. | patch |
| BH-14 | frontend/src/App.tsx:21 | medium | loadEvents catches network errors silently without showing an error message to the user. | patch |
| BH-15 | frontend/src/App.tsx | false | Spec and intent for Story 1.1 define a single organizer dashboard; deep-linked routes belong to subsequent stories. | rejected |
| BH-16 | frontend/src/components/EventForm.tsx | low | Time fields use type="text" instead of type="time" and lack format regex. | patch |
| BH-17 | backend/app/schemas/event.py:30 | low | price_per_meter uses float representation before integer cents conversion. | patch |
| BH-18 | backend/app/schemas/event.py:105 | low | Pydantic response serializer manually inspects table columns rather than reading model properties. | patch |
| BH-19 | sprint-status.yaml | false | sprint-status tracks coarse states (in-progress, done); in-review is an internal workflow step state. | rejected |
| EH-1 | backend/app/api/v1/endpoints/events.py:137 | medium | Duplicate of BH-3: Partial PATCH date inversion without checking existing record. | patch |
| EH-2 | backend/app/api/v1/endpoints/events.py:47 | medium | Duplicate of BH-1: Concurrent POST slug collision causes IntegrityError. | patch |
| EH-3 | backend/app/api/v1/endpoints/events.py:142 | medium | Duplicate of BH-2: Minor title edit causes self-collision suffix bump. | patch |
| EH-4 | backend/app/api/v1/endpoints/events.py:25 | low | Event title near 255 chars with suffix counter can exceed VARCHAR(255). | patch |
| EH-5 | backend/app/main.py:33 | high | If CORS_ORIGINS is empty, allow_origins=["*"] with allow_credentials=True crashes Starlette CORSMiddleware. | patch |
| EH-6 | frontend/vite.config.ts:11 | medium | Duplicate of BH-10: Proxy target in docker-compose. | patch |
| VG-1 | backend/tests/test_events_api.py:169 | low | Verification gap: event list descending sort order is unasserted against frontend consumer. | patch |
| VG-2 | backend/tests/conftest.py | low | Verification gap: database migrations are bypassed by SQLite metadata creation in test suite. | patch |
| VG-3 | backend/app/schemas/event.py:80 | medium | Duplicate of BH-3: Partial PATCH date range check bypass. | patch |
| VG-4 | backend/app/api/v1/endpoints/events.py:719 | medium | Duplicate of BH-2: Self-collision in slug update. | patch |
| VG-5 | deploy/nginx/gvg.conf:15 | medium | Nginx reverse proxy location regex does not match /health endpoint. | patch |
| VG-6 | scripts/install-ubuntu.sh:120 | low | Unquoted PROJECT_NAME in .env file risks parsing errors with systemd EnvironmentFile. | patch |
| VG-7 | backend/tests/test_events_api.py | medium | Unverified status query filter on GET /api/v1/events. Added test_list_events_status_filter. | patch |
| VG-8 | backend/tests/test_events_api.py:270 | medium | Unverified slug identifier resolution in PATCH /api/v1/events/{slug}. Added test case. | patch |
| VG-9 | backend/tests/test_events_api.py | low | Unverified fallback slug for non-alphanumeric event titles. Added test_fallback_slug_for_non_alphanumeric_title. | patch |
| VG-10 | backend/tests/test_migrations.py:15 | low | Working directory sensitivity in Alembic test config resolution. Converted to Path(__file__). | patch |
| VG-11 | frontend/src/components/EventCard.tsx:31 | low | Guard against potential TypeError in toFixed if price_per_meter is undefined. | patch |
| EC-7 | backend/app/core/config.py:25 | low | CORS_ORIGINS environment variable supplied as JSON array string starting with bracket. Added json.loads parsing. | patch |
| EC-8 | scripts/install-ubuntu.sh:89 | medium | Idempotency on script rerun: user password desynchronization. Added ALTER USER. | patch |
| EC-9 | scripts/install-ubuntu.sh:154 | low | Service restart vs reload for inactive Nginx. Updated to systemctl restart. | patch |
| BH-20 | frontend/src/components/EventForm.tsx:211 | low | Step size 0.10 in number input blocked cent precision. Updated to 0.01. | patch |
| BH-21 | frontend/src/components/EventForm.tsx:11 | low | Pre-filled sample organizer values in form defaults replaced with clean placeholders. | patch |
| BH-22 | .gitignore | low | Added *.tsbuildinfo and tsconfig.tsbuildinfo to ignore local TypeScript build artifacts. | patch |

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
