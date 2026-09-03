# Phase 1 Architecture Design

## Purpose and boundaries

Phase 1 delivers a FastAPI REST backend, PostgreSQL persistence, and a React + TypeScript frontend foundation for warehouse management. It deliberately excludes AI/ML, GIS route optimization, RAG, and chatbot features. Public APIs are versioned under `/api/v1`.

## Architecture overview

The backend is organized as `api routers -> services -> repositories -> SQLAlchemy models -> PostgreSQL`. Routers own HTTP concerns and declare authorization dependencies; services own validation and transaction boundaries; repositories encapsulate queries and persistence. Pydantic schemas form the public request/response contract. Alembic owns schema changes.

The frontend is organized as `pages`, reusable `components`, `services/api`, `auth`, and `types`. A single environment-configured API client sends access tokens and centralizes error handling. It never acts as the authorization boundary.

```text
React/Vite -> /api/v1 -> FastAPI router -> permission dependency
                                  -> service -> repository -> PostgreSQL
```

## Authentication and authorization

Persisted authenticated roles are `admin`, `warehouse`, and `client`. `guest` is anonymous/public access only and is never persisted as a user role.

Login issues a signed JWT containing `sub` (user ID), `role` (issuance snapshot), and `exp`. A protected request validates signature and expiration, then loads the user identified by `sub` from the database. Authorization always evaluates the current database role, never the JWT `role` claim. Disabled or missing users are rejected as unauthenticated.

Routers use centralized reusable dependencies such as `require_permission(Permission.PRODUCT_WRITE)`. The dependency checks a single permission-to-allowed-roles map; routers do not contain ad hoc role checks.

## RBAC contract

| Capability | Anonymous guest | admin | warehouse | client |
|---|---:|---:|---:|---:|
| Register / login | No / No | Yes | Yes | Yes |
| Read products, categories | Yes | Yes | Yes | Yes |
| Create, update, delete products/categories | No | Yes | No | No |
| Read suppliers | No | Yes | Yes | No |
| Modify suppliers | No | Yes | No | No |
| Read warehouses and stock | No | Yes | Yes | Yes |
| Modify warehouses | No | Yes | No | No |
| Create/read inbound and outbound | No | Yes | Yes | No |
| Read transactions (append-only) | No | Yes | Yes | No |
| Admin dashboard | No | Yes | No | No |
| Client portal API subset | No | Yes | No | Yes |
| Manage users/roles | No | admin only (no Phase 1 API) | No | No |

All transaction-log mutation routes are absent. Warehouse-specific row-level authorization is out of scope, but every warehouse-scoped data model retains `warehouse_id` so it can be added later without a route-contract break.

## ERD and database schema

```text
users (id, email UQ, password_hash, role, is_active, created_at, updated_at)
categories (id, name UQ, parent_id -> categories.id nullable, timestamps)
suppliers (id, name UQ, email UQ nullable, phone nullable, address nullable, timestamps)
products (id, sku UQ, name, description nullable, category_id -> categories, supplier_id -> suppliers nullable,
          unit, reorder_level >= 0, is_active, timestamps)
warehouses (id, code UQ, name UQ, address, latitude nullable, longitude nullable, timestamps)
stocks (id, warehouse_id -> warehouses, product_id -> products, quantity >= 0, timestamps,
        UQ(warehouse_id, product_id))
inbounds (id, warehouse_id -> warehouses, product_id -> products, quantity > 0, reference nullable,
          note nullable, created_by -> users, created_at)
outbounds (id, warehouse_id -> warehouses, product_id -> products, quantity > 0, reference nullable,
           note nullable, created_by -> users, created_at)
transactions (id, transaction_type {INBOUND, OUTBOUND}, warehouse_id -> warehouses,
              product_id -> products, quantity > 0, inbound_id -> inbounds nullable,
              outbound_id -> outbounds nullable, created_by -> users, created_at)
regions (id, code UQ, name UQ, timestamps)
purchase_requests (id, request_number UQ, warehouse_id -> warehouses, product_id -> products,
                   quantity > 0, status, requested_by -> users, timestamps)
route_logs (id, warehouse_id -> warehouses, region_id -> regions nullable, route_payload JSON nullable,
            created_by -> users nullable, created_at)
```

Foreign keys use restrictive deletion for audited or referenced business data. Category deletion is rejected when children or products reference it. Product, warehouse, and user deletion are not exposed where historic records would be invalidated. Indexes cover foreign keys and commonly filtered fields: `products.category_id`, `products.supplier_id`, stock compound unique key, inbound/outbound warehouse/product/created_at, and transaction warehouse/product/type/created_at.

## API contract

All errors use `{ "detail": { "code": "...", "message": "..." } }`. Validation errors retain FastAPI's documented 422 shape. Lists use `{ "items": [], "total": 0, "page": 1, "page_size": 20 }` and accept `page` and `page_size`; stock additionally accepts `warehouse_id` and `product_id`.

| Group | Endpoints | Access |
|---|---|---|
| Auth | `POST /auth/register`, `POST /auth/login` | register is public; login authenticates persisted roles |
| Product | `GET /products`, `GET /products/{id}`, `POST`, `PUT`, `DELETE /products/{id}` | reads public; mutations admin |
| Category | corresponding CRUD routes | reads public; mutations admin |
| Supplier | corresponding CRUD routes | reads admin/warehouse; mutations admin |
| Warehouse | corresponding CRUD routes | reads admin/warehouse/client; mutations admin |
| Stock | `GET /stock`, `GET /stock/{id}` | admin/warehouse/client |
| Inbound | `POST /inbounds`, `GET /inbounds`, `GET /inbounds/{id}` | admin/warehouse |
| Outbound | `POST /outbounds`, `GET /outbounds`, `GET /outbounds/{id}` | admin/warehouse |
| Transaction | `GET /transactions`, `GET /transactions/{id}` | admin/warehouse, read-only |
| Dashboard | `GET /dashboard/stats` | admin |
| Client portal | documented read-only product/warehouse/stock views | client/admin |

Successful creates return `201`, reads/updates return `200`, deletes return `204`, missing resources return `404`, duplicate/conflict and insufficient stock return `409`, invalid input returns `422`, missing/invalid authentication returns `401`, and authenticated disallowed roles return `403`.

## Inventory transaction design

Inbound and outbound services each execute in one database transaction. Inbound creates its record, locks or creates the corresponding `(warehouse_id, product_id)` stock row, increments it, writes a transaction record, and commits. Outbound locks the stock row, rejects if absent or quantity is insufficient, then creates outbound, decrements stock, writes transaction, and commits. Any failure rolls back all writes. A check constraint also prohibits negative stored stock.

## Migration and seed plan

1. Create Alembic configuration and an initial migration containing roles, domain tables, constraints, indexes, and timestamp defaults.
2. Verify `alembic upgrade head` against an empty PostgreSQL database.
3. Add an idempotent seed command creating one admin, warehouse operator, client, master categories/suppliers/products, warehouses, and stock. Credentials come from environment variables or are printed only for local development, never committed.
4. Verify an upgrade, seed, application startup, and downgrade/upgrade cycle in a disposable test database.

## Implementation order

1. Environment, project scaffolding, quality tooling, Docker, and progress tracking (1.1–1.2).
2. Domain schema and migration/seed (1.3–1.6).
3. Authentication and centralized RBAC (1.7–1.8).
4. Master-data CRUD and tests (1.9–1.12).
5. Warehouse, verified geocoding, stock, inventory workflow, audit log, dashboard (1.13–1.19).
6. Frontend foundation, authentication, product management, client portal, then dashboard integration after backend dashboard is ready (1.20–1.24).

## Testing strategy

Backend tests use pytest, httpx, a disposable PostgreSQL test database, and transaction-isolated fixtures. Tests first cover authentication and every permission boundary, then each CRUD response/validation/conflict case, then inventory atomicity and low-stock dashboard aggregation. Auth plus CRUD coverage must exceed 70%.

Frontend verification includes typecheck/build, routing, token lifecycle, protected-route behavior, loading/error states, and real API integration. No mock data is accepted for critical integrated flows. End-to-end verification follows login -> protected API -> product -> warehouse -> inbound -> stock increase -> outbound -> stock decrease -> transaction -> dashboard.
