# Phase 1 Implemented Architecture

## System boundary

Phase 1 is a basic warehouse-management modular monolith. A React 19/Vite client calls a versioned FastAPI API, and SQLAlchemy persists state in PostgreSQL 16. Docker Compose is the supported local integration topology. Public business access is limited to registration and login; authenticated roles are `admin`, `warehouse`, and `client`.

The phase deliberately excludes geocoding, route optimization, transfer, stocktake, barcode/QR, alerting, notifications, advanced reports/dashboard behavior, password reset, refresh tokens, MFA, distributed rate limiting, event buses, CQRS, Kubernetes, and cloud-specific deployment. Coordinates are entered directly and must be supplied as a valid latitude/longitude pair.

## Backend dependency flow

The implemented dependency direction is:

```text
HTTP request
  -> FastAPI router and permission dependency
  -> domain service
  -> repository
  -> SQLAlchemy model/session
  -> PostgreSQL
```

Routers own HTTP parsing, response models, and authorization declarations. They do not import SQLAlchemy or execute queries. Services own business validation, transaction commit/rollback, and applicable audit writes. Repositories query, add, delete, flush, refresh, and expose the session required by the owning service; repositories do not commit. Pydantic schemas define strict external input and output. Alembic is the sole schema migration mechanism.

Feature packages under `app/` separate auth, master data, warehouses, inventory, dashboard, users, and administrative audit. Cross-feature dependencies stay explicit rather than using a generic repository or dependency-injection framework.

## Authentication and authorization

Passwords use Argon2 hashes. The JWT contains only `sub`, `iat`, and `exp`; it does not carry authoritative role or active-state claims. Every protected request validates the token, loads the current user from PostgreSQL, rejects missing or inactive users, and evaluates the current database role through the centralized `PERMISSION_ROLES` map.

Frontend route guards and role-sensitive controls improve navigation and user experience, but the backend permission dependency remains the security boundary. Public registration always creates an active `client`; the request schema rejects a role field. Admin user creation and role changes accept only `client` or `warehouse`, so an API caller cannot mint another admin through Phase 1 management endpoints.

## Role capabilities

| Capability | admin | warehouse | client |
|---|---:|---:|---:|
| Read categories and products | Yes | Yes | Yes |
| Modify categories and products | Yes | No | No |
| Read suppliers | Yes | Yes | No |
| Modify suppliers | Yes | No | No |
| Read warehouses and stock | Yes | Yes | Yes |
| Modify warehouses | Yes | No | No |
| Create/read inbound and outbound movements | Yes | Yes | No |
| Read immutable stock transactions | Yes | Yes | No |
| Read dashboard totals | Yes | No | No |
| Manage client/warehouse users | Yes | No | No |
| Read administrative user audit | Yes | No | No |

Warehouse row-level tenancy is not implemented. The `warehouse` role can operate across the Phase 1 warehouse set. Warehouse IDs remain explicit throughout the model so finer assignment can be added later.

## Data model and integrity

```text
users
  ├─< inbounds.created_by_id
  ├─< outbounds.created_by_id
  ├─< transactions.created_by_id
  └─< audit_logs.actor_user_id

categories ──< categories (parent) ──< products >── suppliers
                                        │
warehouses ──< stocks >─────────────────┘
     │          UQ(warehouse_id, product_id), quantity >= 0
     ├─< inbounds  ──1 transactions(type=inbound)
     └─< outbounds ──1 transactions(type=outbound)
```

Users have case-insensitive unique email addresses and roles `admin`, `warehouse`, or `client`. Products have case-insensitive unique normalized SKUs, nonnegative reorder levels, a required category, and an optional supplier. Warehouses have case-insensitive unique uppercase codes; coordinates are either both absent or both present and within valid ranges.

Inbound, outbound, and transaction quantities are positive. A stock row is unique per warehouse/product and cannot be negative. A transaction must reference exactly one matching inbound or outbound movement. Foreign keys use restrictive deletion where history would otherwise be invalidated. All persisted timestamps are timezone-aware UTC; the browser formats them in the user's locale.

The schema also contains `regions`, `purchase_requests`, and `route_logs` as reserved Phase 1 foundation tables. They have no Phase 1 HTTP or UI workflow and must not be presented as completed product capability.

Alembic head is `20260904_0002`. It adds administrative audit persistence, case-insensitive identity indexes, normalized warehouse constraints, coordinate constraints, and the exact-one-movement transaction constraint on top of the initial schema.

## Inventory transaction boundary

Inbound and outbound use database transactions owned by `InventoryService`. Inbound validates warehouse/product references, locks or safely creates the stock row, increments quantity, writes the inbound movement and its immutable stock transaction, then commits. Outbound locks the stock row, rejects absent or insufficient stock with `409`, decrements quantity, writes the outbound movement and its immutable transaction, then commits. Any exception rolls back the complete unit.

Stock transactions are the sole Phase 1 business audit for inventory movement. There is no API to mutate or delete them. `audit_logs` is a separate admin-only trail for `user.created`, `user.role_changed`, and `user.status_changed`; it exposes only allowlisted `email`, `role`, and `is_active` snapshots and never passwords or password hashes.

## Frontend architecture

The client is feature-oriented under `client/src/features`, with application providers, routes, navigation, and the shell under `client/src/app`, and shared API/error/UI utilities under `client/src/shared`. React Router enforces authenticated/role-aware navigation. TanStack Query owns server state, React Hook Form and Zod own form validation, and one API client adds the bearer token and normalizes the stable backend error envelope.

A genuine `401` clears the local session and returns to login. A `403` preserves the valid session and displays the forbidden route. Role-aware UI never substitutes for backend authorization.

## Runtime topology

The production-oriented Compose stack contains PostgreSQL `db`, one-shot `migrate`, FastAPI `api`, Nginx-served `web`, and opt-in one-shot `bootstrap`. API startup depends on a healthy database and successful migration. Web startup depends on a healthy API. API and web runtime images are multi-stage builds and run as non-root users. Source tests, `.env`, credentials, caches, local virtual environments, `node_modules`, and Playwright output are excluded from runtime images.

`GET /api/v1/health/live` is process liveness. `GET /api/v1/health/ready` executes `SELECT 1` and reports database availability. Migration is a single release step; API replicas never migrate on startup. Seed requires all three role credentials, validates them before opening the database, is idempotent, and preserves existing hashes and business data.

The E2E overlay locks itself to `smart-warehouse-phase1-task19-e2e`, uses a disposable volume, publishes only web port `58080`, runs migration then bootstrap before API, and leaves database/API ports internal.

## Verification and extension points

Backend verification combines Ruff, unit tests, PostgreSQL migration/integration/constraint/concurrency tests, and transaction-ownership guards. Frontend verification combines Vitest/React Testing Library, TypeScript, production build, and three Playwright critical paths against the Dockerized stack. CI performs those gates without publishing images or deploying.

Phase 2 should extend existing service/repository boundaries and create new Alembic revisions. Transfer and stocktake should reuse inventory locking and immutable transaction patterns. Alerts, reports, dashboards, notifications, and security enhancements should consume explicit application contracts rather than query across repository boundaries.

The exact HTTP contract is in `docs/api/phase-1-contract.md`; operational commands are in `docs/operations/phase-1-runbook.md`.
