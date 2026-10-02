# Phase 1 API Contract

## Conventions

The base path is `/api/v1`. JSON is used for request and response bodies. Protected routes require `Authorization: Bearer <access_token>`. Anonymous business access is limited to `POST /auth/register` and `POST /auth/login`; health probes are also public.

All list responses use:

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20
}
```

`page` defaults to `1`. `page_size` defaults to `20` and accepts `1..100`. IDs are positive integers when supplied as filters. All timestamps are timezone-aware ISO 8601 values representing UTC storage.

## Authentication and system routes

| Method and path | Access | Request | Success |
|---|---|---|---|
| `POST /auth/register` | Anonymous | `RegisterRequest` | `201 UserResponse` |
| `POST /auth/login` | Anonymous | `LoginRequest` | `200 TokenResponse` |
| `GET /auth/me` | Authenticated | None | `200 UserResponse` |
| `GET /health` | Public probe | None | `200 {"status":"ok"}` |
| `GET /health/live` | Public probe | None | `200 {"status":"alive"}` |
| `GET /health/ready` | Public probe | None | `200 {"status":"ready"}` or `503 DATABASE_UNAVAILABLE` |

`RegisterRequest` is `{email, password}` with a normalized valid email and a 12 to 128 character password. Extra fields, including `role`, are rejected. Registration always creates a `client`.

`LoginRequest` is `{email, password}`. `TokenResponse` is `{access_token, token_type: "bearer", user}`. `UserResponse` is `{id, email, role, is_active}`. JWT claims are `sub`, `iat`, and `exp`; the current database user, role, and active state remain authoritative.

## Master data routes

| Method and path | Access | Request or filters | Success |
|---|---|---|---|
| `GET /categories` | admin, warehouse, client | Pagination | `200 Page<CategoryResponse>` |
| `GET /categories/{category_id}` | admin, warehouse, client | Path ID | `200 CategoryResponse` |
| `POST /categories` | admin | `CategoryCreate` | `201 CategoryResponse` |
| `PUT /categories/{category_id}` | admin | `CategoryUpdate` | `200 CategoryResponse` |
| `DELETE /categories/{category_id}` | admin | Path ID | `204` |
| `GET /products` | admin, warehouse, client | Pagination; `search`, `category_id`, `supplier_id`, `is_active` | `200 Page<ProductResponse>` |
| `GET /products/{product_id}` | admin, warehouse, client | Path ID | `200 ProductResponse` |
| `POST /products` | admin | `ProductCreate` | `201 ProductResponse` |
| `PUT /products/{product_id}` | admin | `ProductUpdate` | `200 ProductResponse` |
| `DELETE /products/{product_id}` | admin | Path ID | `204` |
| `GET /suppliers` | admin, warehouse | Pagination; `search` | `200 Page<SupplierResponse>` |
| `GET /suppliers/{supplier_id}` | admin, warehouse | Path ID | `200 SupplierResponse` |
| `POST /suppliers` | admin | `SupplierCreate` | `201 SupplierResponse` |
| `PUT /suppliers/{supplier_id}` | admin | `SupplierUpdate` | `200 SupplierResponse` |
| `DELETE /suppliers/{supplier_id}` | admin | Path ID | `204` |

`CategoryCreate/Update` is `{name, parent_id?}`. A category cannot parent itself or create a hierarchy cycle. Referenced categories cannot be deleted.

`ProductCreate/Update` is `{sku, name, description?, category_id, supplier_id?, unit, reorder_level, is_active}`. SKU is normalized to uppercase. `reorder_level` is nonnegative. Category is required; supplier is optional.

`SupplierCreate/Update` is `{name, email?, phone?, address?}`. Optional strings, when supplied, cannot be blank. Duplicate normalized identity fields return a conflict.

Responses add `id` and otherwise expose the corresponding safe fields. Passwords and internal hashes never appear.

## Warehouse and inventory routes

| Method and path | Access | Request or filters | Success |
|---|---|---|---|
| `GET /warehouses` | admin, warehouse, client | Pagination; `search` | `200 Page<WarehouseResponse>` |
| `GET /warehouses/{warehouse_id}` | admin, warehouse, client | Path ID | `200 WarehouseResponse` |
| `POST /warehouses` | admin | `WarehouseWrite` | `201 WarehouseResponse` |
| `PUT /warehouses/{warehouse_id}` | admin | `WarehouseWrite` | `200 WarehouseResponse` |
| `DELETE /warehouses/{warehouse_id}` | admin | Path ID | `204` |
| `GET /stock` | admin, warehouse, client | Inventory filters and pagination | `200 Page<StockResponse>` |
| `GET /stock/{stock_id}` | admin, warehouse, client | Path ID | `200 StockResponse` |
| `GET /inbounds` | admin, warehouse | Inventory filters and pagination | `200 Page<InventoryMovementReadResponse>` |
| `GET /inbounds/{inbound_id}` | admin, warehouse | Path ID | `200 InventoryMovementReadResponse` |
| `POST /inbounds` | admin, warehouse | `InventoryMovementCreate` | `201 InventoryMovementResponse` |
| `GET /outbounds` | admin, warehouse | Inventory filters and pagination | `200 Page<InventoryMovementReadResponse>` |
| `GET /outbounds/{outbound_id}` | admin, warehouse | Path ID | `200 InventoryMovementReadResponse` |
| `POST /outbounds` | admin, warehouse | `InventoryMovementCreate` | `201 InventoryMovementResponse` |
| `GET /transactions` | admin, warehouse | Transaction filters and pagination | `200 Page<TransactionResponse>` |
| `GET /transactions/{transaction_id}` | admin, warehouse | Path ID | `200 TransactionResponse` |

`WarehouseWrite` is `{code, name, address, latitude?, longitude?}`. Code is normalized to uppercase. Coordinates must be both absent or both present; latitude is `-90..90` and longitude is `-180..180`. `WarehouseResponse` adds `id`, `created_at`, and `updated_at`.

Inventory filters are optional `warehouse_id`, `product_id`, `created_from`, and `created_to`. Datetime filters must include a timezone and `created_from` cannot be later than `created_to`. Transaction lists additionally accept `transaction_type` as `inbound` or `outbound`. Unknown inventory query fields are rejected.

`InventoryMovementCreate` is `{warehouse_id, product_id, quantity, reference?, note?}` with positive quantity. The create response adds `id`; read responses also include `created_by_id` and `created_at`. Inbound atomically increases stock. Outbound atomically decreases stock and returns `409 INSUFFICIENT_STOCK` rather than permitting a negative balance.

`StockResponse` is `{id, warehouse_id, product_id, quantity, created_at}`. `TransactionResponse` is `{id, transaction_type, warehouse_id, product_id, quantity, inbound_id?, outbound_id?, created_by_id, created_at}`. Transactions are immutable and are the sole Phase 1 business audit for inventory movement.

## Dashboard, users, and administrative audit

| Method and path | Access | Request or filters | Success |
|---|---|---|---|
| `GET /dashboard/stats` | admin | None | `200 DashboardStats` |
| `POST /users` | admin | `UserCreate` | `201 ManagedUserResponse` |
| `GET /users` | admin | Pagination | `200 Page<ManagedUserResponse>` |
| `GET /users/{user_id}` | admin | Path ID | `200 ManagedUserResponse` |
| `PATCH /users/{user_id}/role` | admin | `UserRoleUpdate` | `200 ManagedUserResponse` |
| `PATCH /users/{user_id}/status` | admin | `UserStatusUpdate` | `200 ManagedUserResponse` |
| `GET /audit-logs` | admin | Pagination; `action`, `target_type`, `target_id` | `200 AuditLogPage` |
| `GET /audit-logs/{audit_log_id}` | admin | Path ID | `200 AuditLogResponse` |

`DashboardStats` is `{product_count, total_stock, low_stock_count}`.

`UserCreate` is `{email, password, role}` where role is only `client` or `warehouse` and password is 12 to 128 characters. `UserRoleUpdate` accepts the same two managed roles. `UserStatusUpdate` is `{is_active: boolean}`. Admin accounts and self-management are protected from demotion/deactivation through these endpoints. `ManagedUserResponse` is `{id, email, role, is_active}`.

Administrative audit records are created only for `user.created`, `user.role_changed`, and `user.status_changed`. `AuditLogResponse` is `{id, actor_user_id, action, target_type, target_id, before_data, after_data, created_at}`. Before/after data is restricted to `email`, `role`, and `is_active`; credentials and hashes are never returned. This audit is separate from stock transactions.

## RBAC matrix

| Permission | admin | warehouse | client |
|---|---:|---:|---:|
| `catalog:read` | Yes | Yes | Yes |
| `product:write` | Yes | No | No |
| `supplier:read` | Yes | Yes | No |
| `supplier:write` | Yes | No | No |
| `warehouse:read` | Yes | Yes | Yes |
| `warehouse:write` | Yes | No | No |
| `inventory:read` | Yes | Yes | Yes |
| `inventory:history:read` | Yes | Yes | No |
| `inventory:write` | Yes | Yes | No |
| `dashboard:read` | Yes | No | No |
| `user:manage` | Yes | No | No |
| `audit:read` | Yes | No | No |

## Error contract

Application errors use one envelope:

```json
{
  "detail": {
    "code": "INSUFFICIENT_STOCK",
    "message": "Insufficient stock.",
    "fields": null
  }
}
```

Request validation returns `422 REQUEST_VALIDATION_ERROR` and a `fields` map whose values are safe generic messages. Expected domain conflicts and not-found conditions use stable codes. Missing authentication returns `401 AUTHENTICATION_REQUIRED`; malformed token handling returns a safe `401`; an authenticated role without permission receives `403`. Unexpected exceptions and database integrity details are not exposed and become safe `500` or `409` envelopes.

Common status semantics are `200` read/update, `201` create, `204` delete, `401` unauthenticated, `403` forbidden, `404` missing resource, `409` conflict/insufficient stock, `422` invalid input, and `503` failed readiness.
