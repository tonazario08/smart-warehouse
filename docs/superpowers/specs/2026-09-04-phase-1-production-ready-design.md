# Phase 1 Production-Ready Baseline Design

**Status:** Approved design baseline

**Date:** 2026-09-04

**Scope:** Complete Smart Warehouse Phase 1 as a production-ready basic modular monolith.

## 1. Purpose

Phase 1 delivers a deployable warehouse-management foundation whose main workflows operate
end-to-end from React through FastAPI to PostgreSQL. The system must have clear domain
boundaries, backend-enforced authorization, safe inventory transactions, consistent validation
and errors, auditable user administration, and automated verification of critical behavior.

Production-ready basic means the system is structured and tested well enough to extend and
deploy in a real environment without introducing infrastructure intended for a much larger
system. Event buses, CQRS, a dependency-injection framework, generic repositories, distributed
rate limiting, and cloud-specific orchestration are intentionally excluded.

## 2. Existing Baseline

The repository already contains:

- A FastAPI application with SQLAlchemy models and an initial Alembic migration.
- JWT authentication, Argon2 password hashing, and role-based dependencies.
- CRUD foundations for categories, products, suppliers, and warehouses.
- Stock reads, inbound and outbound creation, immutable stock transactions, and dashboard
  statistics.
- An idempotent development seed command.
- A React and TypeScript client with login, product management, and read-only stock display.
- Backend tests that currently use SQLite for most application behavior.
- Docker Compose services for PostgreSQL, the API, and the web client.

Phase 1 completion restructures and extends this baseline. It does not preserve router-level
database access or the current single-component frontend architecture.

## 3. Architecture

### 3.1 Backend request flow

Each backend domain follows this dependency direction:

```text
HTTP request
  -> router (HTTP semantics, request/response schemas, authorization dependency)
  -> service (business rules, transaction boundary, audit coordination)
  -> repository (queries and persistence without commit)
  -> SQLAlchemy model
  -> PostgreSQL
```

Routers do not contain SQLAlchemy queries or business decisions. Repositories do not call
`commit()` or control multi-step transactions. A service owns one transaction for the complete
business operation, including audit writes. Repository methods may use `flush()` when an
identifier or database constraint result is needed before the operation completes.

The backend remains a synchronous FastAPI and SQLAlchemy modular monolith. Each domain exposes
only the interfaces needed by its router or a specific collaborating service. Direct cross-domain
imports are limited to explicit service interfaces and shared core primitives.

### 3.2 Backend domains

- `auth`: public registration, login, current-user loading, password hashing, and JWT identity.
- `users`: admin user listing, detail, creation, role changes, and activation changes.
- `master_data`: categories, products, and suppliers.
- `warehouses`: warehouse CRUD and coordinate validation.
- `inventory`: stock, inbound, outbound, and stock-transaction history.
- `dashboard`: read-only aggregate metrics.
- `audit`: append-only administrative audit records and admin reads.
- `core`: typed configuration, shared error types, exception handlers, pagination primitives,
  security primitives, and database session infrastructure.

The current `master_data` domain may keep categories, products, and suppliers together because
they share lifecycle rules and are still small. A domain is split further only when its behavior
or file size justifies a separate boundary.

### 3.3 Frontend request flow

```text
route
  -> feature page
  -> feature query/mutation hook
  -> shared API client
  -> FastAPI
```

The frontend is organized into `app`, `auth`, `dashboard`, `users`, `products`, `categories`,
`suppliers`, `warehouses`, `inventory`, `transactions`, and `shared` feature areas. Shared code
contains the API client, reusable UI primitives, common types, and cross-feature validation
helpers. Domain-specific types, schemas, components, and hooks remain in their feature.

React Router supplies navigation and route-level UX guards. TanStack Query owns server state,
cache invalidation, loading, and mutation state. React Hook Form and Zod provide typed forms and
client-side validation. Backend authorization remains authoritative even when a route or action
is hidden in the UI.

## 4. Configuration and Runtime Safety

Application settings are loaded through a typed settings object. The API base prefix, database
URL, JWT secret, JWT algorithm, token lifetime, allowed CORS origins, environment name, and seed
inputs use one canonical name each. The existing `JWT_SECRET` versus `JWT_SECRET_KEY` mismatch is
removed.

Production startup fails before serving traffic when required configuration is absent or unsafe.
In particular, it must reject a missing, placeholder, or insufficiently strong JWT secret. Local
development values may be documented in `.env.example`, but credentials and secrets are never
committed in `.env`.

The API provides two probes:

- Liveness confirms that the process and application event loop can respond; it does not query
  PostgreSQL.
- Readiness executes a lightweight PostgreSQL check and reports healthy only when required
  dependencies are reachable.

Alembic migration is an explicit deployment step that fails the deployment on error. API replicas
do not independently run migrations on startup, preventing multiple instances from racing schema
changes.

## 5. Authentication and Authorization

### 5.1 Public authentication

`POST /api/v1/auth/register` accepts only `email` and `password`. Its Pydantic request model uses
`extra="forbid"`, so a supplied `role` or any unknown field returns a validation error. Successful
registration always creates an active `client`.

Email addresses are trimmed and normalized consistently before uniqueness checks and storage.
Passwords are checked against the documented minimum policy and stored only as an Argon2 password
hash. Passwords and password hashes never appear in API responses, application logs, exception
messages, or audit payloads.

JWT access tokens contain only identity and token lifecycle claims required by the application,
with `sub` set to the user identifier. A token role, if present in a legacy token during migration,
is never used for authorization. Every protected request verifies the token and reloads the user,
current role, and active state from PostgreSQL. Missing, invalid, expired, disabled, or deleted
identities return `401` through the common error contract.

Password reset, refresh tokens, MFA, and distributed login rate limiting are outside Phase 1.

### 5.2 Roles and permissions

Persisted roles are `admin`, `warehouse`, and `client`; anonymous access is not a persisted role.
Permissions remain centrally mapped to roles and are enforced through backend dependencies on
every sensitive endpoint.

| Capability | Anonymous | admin | warehouse | client |
|---|---:|---:|---:|---:|
| Register and login | Yes | Yes | Yes | Yes |
| Read products and categories | No | Yes | Yes | Yes |
| Mutate products and categories | No | Yes | No | No |
| Read suppliers | No | Yes | Yes | No |
| Mutate suppliers | No | Yes | No | No |
| Read warehouses and stock | No | Yes | Yes | Yes |
| Mutate warehouses | No | Yes | No | No |
| Create and read inbound/outbound | No | Yes | Yes | No |
| Read stock transactions | No | Yes | Yes | No |
| Read dashboard | No | Yes | No | No |
| Administer non-admin users | No | Yes | No | No |
| Read administrative audit | No | Yes | No | No |

Backend tests verify both route access and important actions within a route. Frontend role checks
only improve navigation and prevent presenting unusable controls.

Product and category reads require an authenticated `admin`, `warehouse`, or `client`. Anonymous
users can only register and log in; Phase 1 does not expose a public catalogue.

## 6. User Administration and Audit

### 6.1 User administration API

The minimum admin API provides:

- Paginated user listing and user detail.
- Creation of `client` or `warehouse` accounts by an admin.
- Activation and deactivation of non-admin accounts.
- Role transition between `client` and `warehouse` for non-admin accounts.

The ordinary API never creates an `admin`, assigns the `admin` role, changes the role of an admin,
or deactivates an admin. The first administrator is bootstrapped by the seed command using
credentials supplied through environment variables. The current admin therefore cannot lock or
demote itself, and one admin cannot remove another seeded administrator's administrative access
through this API.

Email conflicts and invalid role or state transitions return stable domain errors. User list
responses never include password hashes.

### 6.2 Administrative audit model

An append-only audit table records:

- `id`
- `actor_user_id`
- `action`
- `target_type`
- `target_id`
- `before_data` as JSON when applicable
- `after_data` as JSON when applicable
- `created_at` as timezone-aware UTC

Internal user creation, role changes, and activation changes write an audit record in the same
service transaction as the target mutation. If the audit insert fails, the complete operation is
rolled back. Audit payload construction uses an allowlist and cannot include a password or hash.

Only admins can list and inspect audit records. The application exposes no update or delete route
for audit history. Database access outside the application is governed operationally rather than
by application endpoints.

Administrative audit is reserved for security-sensitive user administration in Phase 1. Inventory
movements use stock-transaction history as their authoritative business audit and do not create a
second administrative audit record for the same operation.

## 7. API and Error Contract

Public APIs remain versioned under `/api/v1`. Collection responses use a consistent bounded
pagination shape:

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20
}
```

`page` starts at one and `page_size` has a documented default and a maximum of 100. Filter values
are validated before querying.

Expected errors use one response shape:

```json
{
  "detail": {
    "code": "USER_EMAIL_CONFLICT",
    "message": "Email is already registered.",
    "fields": null
  }
}
```

`fields` contains field-specific validation details when relevant and is otherwise `null`. Domain
errors, request validation errors, authentication failures, authorization failures, not-found
results, and expected integrity conflicts all use this contract. Stable machine-readable codes
allow the frontend to react without parsing prose.

Unexpected errors return status `500` with a generic code and safe message. Responses do not
expose SQL, stack traces, secrets, or internal exception text. Full diagnostic context remains in
server logs under the deployment's access controls.

The shared frontend client parses this structure and applies consistent behavior:

- `401`: clear invalid local authentication and redirect to sign-in when appropriate.
- `403`: retain the session and show an explicit permission error.
- Domain and validation errors: preserve the server code/message/fields for feature-level display;
  they are not replaced with a generic message.

## 8. Domain Behavior and Validation

### 8.1 Master data

Categories, products, and suppliers have list/detail/create/update/delete operations appropriate to
their RBAC permissions. Lists support bounded pagination and useful domain filters. Category
updates prevent both direct and indirect parent cycles. Referenced records cannot be deleted when
doing so would invalidate inventory or historical records.

SKU values are trimmed and normalized consistently. Email, category, supplier, unit, reorder
level, and active-state fields receive request validation and database-backed integrity checks.

### 8.2 Warehouses

Warehouses have paginated list, detail, create, update, and protected delete behavior. Warehouse
code and name uniqueness are enforced in PostgreSQL. Address is required.

Coordinates are entered directly; no external geocoding provider is called. Latitude and
longitude must be supplied together or both omitted. Latitude is within `[-90, 90]`, longitude is
within `[-180, 180]`, and supported constraints are enforced at both schema and PostgreSQL levels.

Deletion returns a conflict when inventory or historical data references the warehouse.

### 8.3 Inventory

The inventory API provides:

- Paginated and filterable stock reads.
- Inbound creation plus paginated/filterable list and detail.
- Outbound creation plus paginated/filterable list and detail.
- Paginated/filterable, read-only stock-transaction history and detail.

Positive movement quantity, valid warehouse, valid product, and other movement inputs are checked
before persistence. Stored stock has a PostgreSQL `quantity >= 0` constraint. Product reorder level
has a PostgreSQL `reorder_level >= 0` constraint. The stock pair `(warehouse_id, product_id)` has a
PostgreSQL unique constraint.

For an inbound whose stock row already exists, the service selects the row `FOR UPDATE`, increments
it, creates the inbound, and appends the stock transaction in one transaction. For first inbound,
the service uses PostgreSQL atomic insert/upsert behavior based on the unique stock pair, then
locks or atomically updates the canonical row. It safely handles a concurrent creator without
returning an unhandled uniqueness error or losing quantity.

For outbound, the service selects the stock row `FOR UPDATE` before checking available quantity.
It rejects missing or insufficient stock with a conflict and performs no partial writes. A
successful decrement, outbound record, and stock transaction commit together. Concurrent
outbounds cannot produce negative stock or more than one successful allocation of the same units.

Inbound, outbound, and stock-transaction history are append-only through application APIs.
Each successful inbound or outbound appends exactly one stock transaction in the same database
transaction. This stock transaction is the inventory operation's audit record; duplicating it in
the administrative audit table is neither required nor permitted.

### 8.4 Dashboard

The admin dashboard reports at least product count, summed stock quantity, and low-stock count.
Low stock means a stock balance whose quantity is less than or equal to its product reorder level.
All aggregates are read from PostgreSQL and use a consistent snapshot for the request.

## 9. Database Integrity and Time

PostgreSQL is authoritative for development integration, deployment, and production. Critical
integrity is not dependent solely on application validation. Constraints include unique user
email, category name, supplier identity fields where applicable, product SKU, warehouse code and
name, and stock warehouse/product pair; foreign keys; positive movement quantities; non-negative
stock and reorder levels; valid enum values; and coordinate ranges where PostgreSQL supports the
rule directly.

Database and application timestamps are timezone-aware UTC. API responses carry an unambiguous
offset. The frontend formats timestamps in the user's browser timezone.

Schema changes are represented by ordered Alembic revisions. Migration tests build an empty
PostgreSQL database to head. Upgrade compatibility with the current initial revision is preserved;
destructive schema recreation is not an accepted migration strategy.

## 10. Frontend Experience

The authenticated application uses a shared layout and navigation appropriate to the current
role:

- Admin: dashboard, users, audit, categories, products, suppliers, warehouses, stock, inbound,
  outbound, and transaction history.
- Warehouse: allowed catalogue and supplier reads, warehouses, stock, inbound, outbound, and
  transaction history.
- Client: product catalogue, warehouses, and read-only stock.
- Anonymous: client registration and login.

Every data page supplies loading, failure, empty, pagination, and refresh states. Forms show local
validation before submission and map backend field errors to the relevant controls. Mutations
disable duplicate submission, show a clear success/failure result, and invalidate only affected
queries. Destructive actions require explicit confirmation.

The critical workflows run without mock data:

1. Anonymous user registers and becomes a client.
2. Seeded admin signs in, manages non-admin users, master data, and warehouses, and sees audit.
3. Warehouse operator records inbound and outbound movements.
4. Stock and immutable history reflect the movements.
5. Client can read permitted catalogue and inventory data but cannot mutate it.
6. Admin dashboard reflects the resulting database state.

Advanced administration screens outside these workflows may remain API-verified when they do not
affect an approved Phase 1 capability.

## 11. Verification Strategy

### 11.1 Backend

- Unit tests cover pure validation and business-rule helpers without requiring PostgreSQL; SQLite
  is allowed only where the tested behavior is database-independent.
- Integration tests apply Alembic migrations and exercise repositories, services, HTTP contracts,
  constraints, and transactions against PostgreSQL.
- RBAC matrix tests cover each sensitive endpoint and important action, including forbidden role
  assignment, self-protection, mutation attempts, and audit reads.
- Security tests cover forbidden registration fields, password response/audit exclusion, token
  validation, disabled users, current database roles, safe configuration, and sanitized failures.
- Concurrency tests use independent PostgreSQL sessions to exercise simultaneous first inbound,
  inbound/outbound interaction, and competing outbounds. Assertions cover final stock, movement
  records, stock-transaction history, audit where the operation requires it, and rollback behavior,
  not only HTTP status.
- Migration tests upgrade an empty PostgreSQL database and verify key constraints.

### 11.2 Frontend

Vitest and React Testing Library cover route guards, role-sensitive actions, API error handling,
forms, validation, loading, empty, success, and failure states. Tests verify that a `403` does not
destroy a valid session and a genuine `401` follows the common sign-out path.

### 11.3 End-to-end

Playwright runs critical paths against the Dockerized frontend, API, and PostgreSQL database. It
does not duplicate every unit or integration edge case. Critical coverage includes public client
registration; admin user/master-data/warehouse operations and audit; warehouse inbound/outbound;
client read-only behavior; history and stock updates; and dashboard results.

### 11.4 Quality gates

The minimum repeatable gates are:

- Backend Ruff lint.
- Backend unit and PostgreSQL integration/concurrency tests.
- Alembic migration test.
- Frontend type-check.
- Frontend Vitest test suite.
- Frontend production build.
- Playwright critical-path suite.

## 12. Containers and Deployment

Docker uses reproducible, production-oriented builds. The production API and frontend images use
multi-stage builds where helpful, run as a non-root user where compatible, and exclude `.env`,
secrets, tests, test data, caches, local virtual environments, source-only build artifacts, and
development dependencies not required at runtime.

Docker Compose remains the supported local integration environment. Production deployment uses
the same environment contract but runs migration as a single explicit release step before API
replicas are replaced or scaled. Container healthchecks distinguish liveness from readiness.

The seed command is idempotent. It requires bootstrap credentials from environment variables or an
equivalent secure bootstrap mechanism and has no usable production credential defaults. Re-running
seed does not overwrite existing credentials or business records.

## 13. Documentation Deliverables

The final repository documents:

- Local prerequisites, environment setup, run, stop, test, lint, and build commands.
- Modular-monolith architecture and dependency rules.
- ERD and important PostgreSQL constraints.
- API endpoints, pagination, filters, error contract, and RBAC matrix.
- Migration and secure seed procedures.
- Docker development and production build workflow.
- Liveness/readiness behavior.
- Basic PostgreSQL backup and restore procedure.
- UTC storage and frontend timezone display policy.
- Phase 1 scope exclusions and safe extension points.

README, architecture documents, and progress tracking describe the implemented final system and do
not retain stale statements about the original router-only architecture or repository state.

## 14. Completion Criteria

Phase 1 is complete only when all of the following are true:

- Approved API and UI capabilities operate end-to-end on PostgreSQL.
- Public registration cannot accept or assign a privileged role.
- All sensitive operations are authorized by the backend and verified by the RBAC matrix.
- Admin user mutations are protected and atomically audited.
- Inventory concurrency cannot lose quantity, oversell stock, or create inconsistent history.
- Error and validation responses follow the common contract without leaking internal details.
- A new PostgreSQL database migrates to head, secure seed runs repeatedly, and the application
  becomes ready.
- All quality gates in section 11.4 pass from documented commands.
- Docker production images satisfy the runtime-content and secret constraints.
- Documentation matches the delivered architecture and behavior.

## 15. Explicitly Excluded from Phase 1

- External geocoding and GIS route optimization.
- AI, machine learning, RAG, or chatbot features.
- Password reset, refresh tokens, and MFA.
- Distributed rate limiting.
- Event-driven integration, event bus, or CQRS.
- Generic repository or dependency-injection frameworks.
- Kubernetes, cloud-specific infrastructure, and large-scale observability platforms.
- Warehouse-specific row-level staff assignments unless introduced by a later approved phase.
