# Phase 1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the Phase 1 warehouse-management foundation with stable FastAPI APIs and a React client that uses the real backend.

**Architecture:** The backend uses versioned FastAPI routers, services, repositories, SQLAlchemy 2 models, Alembic migrations, and PostgreSQL. The frontend uses Vite React/TypeScript, one API client, and route-based auth UI. RBAC comes from a centralized permission dependency whose current role source is the database.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2, PostgreSQL 16, Alembic, Pydantic 2, Argon2, JWT, pytest/httpx; React, TypeScript, Vite; Docker Compose.

**Spec:** `docs/architecture/phase-1-design.md`

## Global Constraints

- API routes are rooted at `/api/v1`.
- Persist only `admin`, `warehouse`, and `client`; guest is anonymous/public access.
- JWT must include `sub`, `role`, and `exp`; authorization loads the current user and uses its database role.
- No transaction mutation APIs; stock never becomes negative.
- Do not commit `.env`, credentials, or secrets.
- Test each behavior before adding production behavior; update `PROGRESS.md` only after verification.

---

### Task 1: Environment and project foundation (1.1–1.2)

**Files:** Create backend dependency/config files, frontend Vite project files, Docker files, `.env.example`, `README.md`, and `PROGRESS.md`.

- [ ] Create reproducible Python and Node version constraints, linters, test commands, and development environment examples.
- [ ] Create the FastAPI application factory, health endpoint, React app shell, and Docker Compose services for API, web, and PostgreSQL.
- [ ] Add an initial health/startup test and verify it fails before the app exists, then passes after minimal implementation.
- [ ] Verify backend startup, frontend build, and no secrets tracked by Git.

### Task 2: Database schema, migration, and seed (1.3–1.6)

**Files:** Create SQLAlchemy models, Alembic configuration/revision, seed command, schemas, and model/migration tests.

- [ ] Write failing persistence tests for role constraints, category hierarchy, stock compound uniqueness, and non-negative stock.
- [ ] Implement models and an initial Alembic revision exactly as specified in the design.
- [ ] Add an idempotent seed command and verify fresh-database upgrade plus seed.
- [ ] Verify indexes, foreign keys, constraints, and relationships through PostgreSQL integration tests.

### Task 3: Authentication and RBAC (1.7–1.8)

**Files:** Create auth schemas, service, router, JWT helpers, permission map/dependencies, and auth/RBAC tests.

- [ ] Write failing tests for registration, Argon2 hashing, login, invalid credentials, invalid/expired tokens, and database-role authority over stale JWT role claims.
- [ ] Implement JWT issue/validation, current-user loading, and centralized permission dependencies.
- [ ] Encode each approved matrix permission and write unauthorized/forbidden/allowed tests for all roles.
- [ ] Verify no protected router bypasses the permission dependencies.

### Task 4: Master-data APIs and tests (1.9–1.12)

**Files:** Create repositories, services, routers, schemas, and tests for products, categories, and suppliers.

- [ ] Write failing CRUD, validation, duplicate, not-found, public-read, and admin-write authorization tests.
- [ ] Implement routers backed by services and repositories with paginated list responses.
- [ ] Verify OpenAPI paths/schemas, test coverage above 70% for auth plus CRUD, and all tests passing.

### Task 5: Warehouse and geocoding (1.13–1.14)

**Files:** Create warehouse repository/service/router/schemas, provider interface, timeout/error handling, and tests.

- [ ] Write failing warehouse CRUD and role-boundary tests plus provider success/failure tests.
- [ ] Implement warehouse CRUD including address, latitude, and longitude; integrate a configured geocoding provider only when credentials are available.
- [ ] Mark geocoding blocked in `PROGRESS.md` if credentials or verified provider access are unavailable; do not simulate completion.

### Task 6: Inventory and audit workflow (1.15–1.18)

**Files:** Create stock, inbound, outbound, and transaction repositories/services/routers/schemas plus transactional integration tests.

- [ ] Write failing tests for inbound increment, outbound decrement, insufficient-stock conflict, rollback, and append-only transactions.
- [ ] Implement atomic service methods using row locking and one session transaction per operation.
- [ ] Implement filtered stock and transaction reads, without transaction mutation routes.
- [ ] Verify database state after success and intentional failure cases.

### Task 7: Dashboard API (1.19)

**Files:** Create dashboard service/router/schema/tests and API documentation.

- [ ] Write failing admin-only tests for product count, total stock, and low-stock alerts.
- [ ] Implement aggregate queries and stable response schemas.
- [ ] Verify response documentation and readiness for frontend integration.

### Task 8: Frontend foundation and auth (1.20–1.21)

**Files:** Create Vite configuration, route tree, API client, auth store/context, layouts, pages, and build checks.

- [ ] Write failing component/routing tests for token persistence, logout, and protected-route redirects where test tooling is configured.
- [ ] Implement typed API client, centralized error handling, login/register, and route protection.
- [ ] Verify production build and API-backed authentication flow.

### Task 9: Frontend product and client views (1.23–1.24)

**Files:** Create product-management and client-portal pages/components/services/types.

- [ ] Write failing UI behavior tests for product CRUD form validation and client read-only access.
- [ ] Implement pages using real product, warehouse, and stock APIs with loading/error states.
- [ ] Verify client cannot be offered or execute inventory mutations.

### Task 10: Dashboard integration and final verification (1.22)

**Files:** Create dashboard page/components and final API/architecture/progress documentation updates.

- [ ] Write failing dashboard rendering tests for statistics, loading, and API error behavior.
- [ ] Implement admin dashboard against `GET /api/v1/dashboard/stats` with no mock data.
- [ ] Run the documented end-to-end flow, `pytest`, coverage, `npm run build`, fresh migration/seed, and update the completion report.
