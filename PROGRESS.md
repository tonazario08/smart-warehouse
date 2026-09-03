# Phase 1 Progress

Current Task:
- Task 10 - Dashboard integration and final verification.

Completed:
- 1.1 - Environment setup: Python virtual environment, backend dependency metadata, lint/test tooling, environment template, Docker/Compose configuration, Git ignore rules, and baseline documentation.
- 1.2 - Project initialization: FastAPI application factory with a versioned health endpoint, health test, React + TypeScript/Vite client foundation, client Docker configuration, and API/web Compose services.
- 1.3 - Domain model foundation: SQLAlchemy declarative base and Phase 1 entities with role, hierarchy, uniqueness, and quantity constraints, verified by persistence tests.
- 1.4 - Alembic configuration and initial schema migration: all Phase 1 tables, foreign keys, indexes, unique/check constraints, and timestamp defaults are defined in revision `20260829_0001`.
- 1.7-1.8 - Authentication and RBAC: registration, Argon2 password hashing, JWT login/validation, current-user loading, and centralized permission mapping are implemented and tested.
- 1.9-1.12 - Master-data APIs: paginated category/product/supplier reads, admin writes, validation, conflict handling, and RBAC tests are implemented.
- 1.13 - Warehouse CRUD: role-protected list/detail/create/update endpoints with uniqueness validation are implemented.
- 1.15-1.18 (foundation) - Role-protected inbound/outbound creation updates stock atomically and appends immutable transaction records; insufficient stock returns `409`.
- 1.19 (foundation) - Admin-only dashboard stats reports product count, total stock, and low-stock count.
- Docker runtime - Docker Desktop 4.89.0 / Docker Engine 29.7.2 with WSL 2 backend is installed and running.
- Docker migration/seed - PostgreSQL 16 initialized; Alembic revision `20260829_0001` applied and seed data created.
- Docker runtime smoke - `api`, `web`, and `db` rebuilt and started successfully; web returned `200` and admin API login returned `200` with an access token.
- 1.20-1.21 - Frontend sign-in form calls `POST /api/v1/auth/login`, stores the access token, reports errors, and displays the signed-in user.
- 1.23-1.24 - Frontend product register and client portal are implemented with real product, warehouse, and stock APIs. Admins can create, update, and delete products; client views expose no inventory mutation controls.
- Stock read API - `GET /api/v1/stock` supports optional warehouse/product filters and is available to inventory-read roles.
- API/frontend integration - CORS allows the local frontend origin `http://localhost:5173`.

In Progress:
- None.

Blocked:
- None.
- Geocoding provider verification: no configured external provider credentials are available; warehouse coordinates remain explicitly supplied fields.

Failed Tests:
- None. `.venv\Scripts\python.exe -m pytest -q` passed (27 tests) and `npm.cmd run build` passed on 2026-09-03.

Known Issues:
- The repository has no initial Git commit, so an isolated linked worktree cannot be created.
- In-app browser smoke verification remains unavailable because no browser session is connected; HTTP-level web/API smoke verification passed.

Technical Decisions:
- Backend dependencies are managed by `pyproject.toml`; `.[dev]` installs pytest, httpx, coverage, and Ruff.
- PostgreSQL 16 is the Docker Compose database target.
- API and frontend implementation follow `docs/architecture/phase-1-design.md`.
- Docker Desktop uses the WSL 2 backend and per-user installation.

API Contract Changes:
- Frontend now consumes the existing `POST /api/v1/auth/login` contract; no backend auth contract changes were required.
- CORS was added for the local frontend origin.
- `GET /api/v1/stock` returns stock balances and accepts optional `warehouse_id` and `product_id` filters for admin, warehouse, and client roles.

Database Migration Status:
- Initial Alembic revision `20260829_0001` was applied successfully to the Docker PostgreSQL 16 database on 2026-09-03. Development seed data was created successfully.

Next Task:
- Implement the admin dashboard page against `GET /api/v1/dashboard/stats`, then run final Phase 1 verification.

Last Updated:
- 2026-09-03
