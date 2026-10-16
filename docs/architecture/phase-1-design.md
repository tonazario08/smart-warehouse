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

Routers own HTTP parsing, response models, and authorization declarations. They do not import SQLAlchemy or execute queries. Services own business validation, transaction commit/rollback, and applicable audit writes. Repositories query, add, delete, flush, refresh, and expose the session required by the owning service; repositories do not commit. Pydantic schemas define validated external input and output. Alembic is the sole schema migration mechanism.

Feature packages under `app/` separate auth, master data, warehouses, inventory, dashboard, users, and administrative audit. Cross-feature dependencies stay explicit rather than using a generic repository or dependency-injection framework.

## Authentication and authorization

Passwords use Argon2 hashes. Server-issued JWTs contain `sub`, `iat`, and `exp`; decoding requires all three claims and verifies the configured key/algorithm and expiry. Tokens do not carry authoritative role or active-state claims. Every protected request loads the current user from PostgreSQL, rejects missing or inactive users, and evaluates the current database role through the centralized `PERMISSION_ROLES` map.

Frontend route guards and role-sensitive controls improve navigation and user experience, but the backend permission dependency remains the security boundary. Public registration always creates an active `client`; the request schema rejects a role field. Admin user creation and role changes accept only `client` or `warehouse`, so an API caller cannot mint another admin through Phase 1 management endpoints.

## Role capabilities

This is the backend/API permission matrix, not a list of active frontend screens.

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

Inbound/outbound request quantities are integers in `1..2147483647`; optional movement references are limited to 120 characters. PostgreSQL integer storage bounds stock and transaction quantities. A stock row is unique per warehouse/product and cannot be negative. A transaction must reference exactly one matching inbound or outbound movement. Foreign keys use restrictive deletion where history would otherwise be invalidated. All persisted timestamps are timezone-aware UTC; the active browser formats dates/numbers with `vi-VN`.

The schema also contains `regions`, `purchase_requests`, and `route_logs` as reserved Phase 1 foundation tables. They have no Phase 1 HTTP or UI workflow and must not be presented as completed product capability.

Alembic head is `20260904_0002`. Before normalizing data or applying its DDL, it checks legacy collisions in normalized user emails, product SKUs and warehouse codes and aborts with field names rather than row values. It then adds administrative audit persistence, case-insensitive identity indexes, normalized warehouse constraints, coordinate constraints, and the exact-one-movement transaction constraint on top of the initial schema.

## Inventory transaction boundary

Inbound and outbound use database transactions owned by `InventoryService`. Inbound validates warehouse/product references, locks or safely creates the stock row, checks the resulting balance against `2147483647`, increments quantity, writes the inbound movement and its immutable stock transaction, then commits. Overflow returns `409 STOCK_QUANTITY_LIMIT_EXCEEDED`, including competing first inbounds. Outbound locks the stock row, rejects absent or insufficient stock with `409 INSUFFICIENT_STOCK`, decrements quantity, writes the outbound movement and its immutable transaction, then commits. Any exception rolls back the complete unit, without partial stock/movement/transaction writes.

Stock transactions are the sole Phase 1 business audit for inventory movement. There is no API to mutate or delete them. `audit_logs` is a separate admin-only trail for `user.created`, `user.role_changed`, and `user.status_changed`; it exposes only allowlisted `email`, `role`, and `is_active` snapshots and never passwords or password hashes.

## Frontend architecture

The active runtime is `main.tsx -> App.tsx -> app/AuthProvider.tsx -> app/router.tsx`. Its Figma pages live under `client/src/pages`; shell/navigation and reusable controls use `client/src/shared/layout` and `shared/ui`, local assets and plain CSS. Pages use React state/effects and the `client/src/api.ts` facade, not TanStack Query/RHF/Zod runtime providers. The facade takes explicit catalogue tokens, collects all pages for directory/stock/history joins, honors `VITE_API_BASE_URL`, and preserves structured status/code/field/server-message metadata while presenting safe Vietnamese errors.

The token key remains `smart-warehouse-token`. Auth hydration reads the authoritative `/auth/me`; current-session `401` clears the session, while delayed failures from an older session generation cannot clear a newer login, even if it reuses a token. API `403` preserves the session and displays a localized failure; transport/403 hydration failures do not erase the stored token. Route guards send unauthenticated visitors to login with a return destination and redirect denied roles to `/products` for clients or `/inventory` for warehouse users. There is no active `/forbidden` screen. Role-aware UI never substitutes for backend authorization.

The Figma routes cover dashboard, products, inventory/detail, warehouses/detail and inbound/outbound lists/forms. User/audit administration, public registration, category/supplier management and a separate transactions UI were not added. Their backend endpoints remain supported. Stock detail can display real movement time/reference/note and actor ID for admin/warehouse users; clients do not fetch restricted history. Actor names are not invented from IDs.

Historical `client/src/features` modules, the legacy auth/query/form infrastructure and their meaningful tests are retained. Only tests and their utilities import `client/src/test/LegacyAppRouter.tsx`; that router and the English shell are not application entry points. Legacy capability-test results are distinct from tests of the active Figma API/provider/routes.

## Runtime topology

The production-oriented Compose stack contains PostgreSQL `db`, one-shot `migrate`, FastAPI `api`, Nginx-served `web`, and opt-in one-shot `bootstrap`. API startup depends on a healthy database and successful migration. Web startup depends on a healthy API. API and web runtime images are multi-stage builds and run as non-root users. Source tests, `.env`, credentials, caches, local virtual environments, `node_modules`, and Playwright output are excluded from runtime images.

`GET /api/v1/health/live` is process liveness. `GET /api/v1/health/ready` executes `SELECT 1` and reports database availability. Migration is a single release step; API replicas never migrate on startup. Seed requires all three role credentials and distinct normalized emails, validates supplied credentials before opening the database, and rejects an existing identity with a different role without reassigning it. Repeated valid bootstrap preserves existing hashes and business data.

The E2E overlay defaults to project `smart-warehouse-phase1-task19-e2e`, uses a disposable volume, publishes only the configurable web port (default `58080`), runs migration then bootstrap before API, and leaves database/API ports internal. The runbook guards the rendered project name before destructive cleanup. Playwright accepts only loopback ports `58080` or `58081`; overrides must match the isolated stack rather than the development origin.

## Verification and extension points

Backend verification combines Ruff, unit tests, PostgreSQL migration/integration/constraint/concurrency tests, and transaction-ownership guards. Frontend `npm.cmd run test:all` runs Vitest/React Testing Library capability and active-Figma tests plus the retained Node-host suite; TypeScript, production build and dependency audit are separate gates. CI runs both frontend suites rather than only Vitest, without publishing images or deploying.

Eight Playwright tests run against the isolated production stack. UI evidence covers real Vietnamese login/refresh/logout, role navigation/guards, 401 cleanup, 403 session retention, product CRUD, warehouse create/read/edit, inbound/outbound success and rejection, stock/history and dashboard changes. Explicit real API steps cover registration/client-only enforcement, directory mutations, managed-user role/status and password-safe administrative audit, plus warehouse deletion not offered by the UI. No mock success responses or legacy shell are used. Trace, video and screenshots are disabled to avoid storing authentication payloads; runner results do not imply visual parity for every page.

Phase 2 should extend existing service/repository boundaries and create new Alembic revisions. Transfer and stocktake should reuse inventory locking and immutable transaction patterns. Alerts, reports, dashboards, notifications, and security enhancements should consume explicit application contracts rather than query across repository boundaries.

The exact HTTP contract is in `docs/api/phase-1-contract.md`; operational commands are in `docs/operations/phase-1-runbook.md`.
