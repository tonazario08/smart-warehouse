# Phase 1 Production-Ready Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Smart Warehouse Phase 1 as a production-ready basic modular monolith whose approved workflows run end-to-end from React through FastAPI to PostgreSQL.

**Architecture:** Backend domains use `router -> service -> repository -> model -> PostgreSQL`; services own commit/rollback and applicable audit writes, while repositories only query, add, delete, and flush. The React client is feature-oriented and uses React Router, TanStack Query, React Hook Form, and Zod; PostgreSQL-backed integration, concurrency, and critical-path E2E tests verify the system.

**Tech Stack:** Python 3.12+, FastAPI 0.115+, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL 16, Argon2, PyJWT, pytest, Ruff; Node.js 20.19+, React 19, TypeScript, Vite, React Router, TanStack Query, React Hook Form, Zod, Vitest, React Testing Library, Playwright; Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-04-phase-1-production-ready-design.md`

## Global Constraints

- Public API routes are rooted at `/api/v1`.
- Persisted roles are exactly `admin`, `warehouse`, and `client`.
- Anonymous users may register and log in only; catalogue and all other application reads require authentication.
- Public registration accepts only `email` and `password`, forbids extra fields, and always creates a `client`.
- JWT authorization uses the current database user, role, and active state; the token contains identity and lifecycle claims, not authoritative permissions.
- Passwords and password hashes never appear in responses, logs, exception text, or audit payloads.
- Routers contain HTTP/schema/authorization concerns, services contain business rules and transaction ownership, and repositories never call `commit()`.
- Administrative audit covers internal user creation, role change, and activation change in the same transaction as the mutation.
- Each successful inbound/outbound creates exactly one stock transaction as its business audit; it does not create an administrative audit record.
- PostgreSQL 16 is authoritative for integration, concurrency, development integration, and deployment behavior. SQLite is limited to database-independent unit tests.
- Collection responses use `page >= 1`, `1 <= page_size <= 100`, and `{items,total,page,page_size}`.
- Timestamps are timezone-aware UTC at rest and in API responses; the browser formats them for the user.
- Warehouse coordinates are both absent or both present; latitude is `[-90, 90]` and longitude is `[-180, 180]`.
- Migration is an explicit single deployment step; API replicas do not migrate on startup.
- No geocoding, password reset, refresh token, MFA, distributed rate limiting, event bus, CQRS, generic repository, DI framework, Kubernetes, or cloud-specific platform is added.
- Do not stage or commit `.env`, secrets, credentials, `node_modules`, `dist`, caches, virtual environments, test databases, or generated Playwright output.
- Use TDD for each behavior: demonstrate the focused test failing, add the minimum implementation, then run the focused and relevant regression suites.
- Before every commit follow `AGENTS.md`: inspect status, staged diff, unstaged diff, staged file list, and relevant verification output.

## Execution Environment

Use these PowerShell commands from the repository root:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://smart_warehouse_test:test-only@localhost:55432/smart_warehouse_test"
docker compose -f docker-compose.test.yml up -d db_test
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
Set-Location client
npm.cmd test -- --run
npm.cmd run build
```

The checked-in test Compose file owns only disposable test data. A developer must never point
`TEST_DATABASE_URL` at a non-test database.

## Target File Map

| Area | Responsibility |
|---|---|
| `app/core/config.py` | Typed environment configuration and production safety validation |
| `app/core/errors.py` | Domain errors, response schemas, and global exception handlers |
| `app/core/pagination.py` | Bounded page inputs and generic page response/result types |
| `app/db/session.py` | Engine construction and request-scoped SQLAlchemy sessions |
| `app/<domain>/repository.py` | Domain-specific SQLAlchemy queries/persistence; no commit |
| `app/<domain>/service.py` | Business rules, transaction commit/rollback, and audit coordination |
| `app/<domain>/router.py` | HTTP contract, dependency wiring, and response status |
| `app/<domain>/schemas.py` | Strict request and response schemas |
| `app/audit/models.py` | Append-only administrative audit persistence model |
| `tests/unit/` | Database-independent rules and schema tests |
| `tests/postgres/` | PostgreSQL migration, integration, constraint, and concurrency tests |
| `client/src/app/` | Providers, routes, layout, and navigation |
| `client/src/features/` | Auth, dashboard, users, audit, master data, warehouses, and inventory |
| `client/src/shared/` | API client, common types, forms, errors, and UI primitives |
| `client/e2e/` | Playwright critical-path specifications |

---

## Milestone 1 — Core and PostgreSQL Test Foundation

### Task 1: Typed Configuration, Error Contract, Pagination, and Health Probes

**Files:**
- Create: `app/core/__init__.py`
- Create: `app/core/config.py`
- Create: `app/core/errors.py`
- Create: `app/core/pagination.py`
- Modify: `app/db/session.py`
- Modify: `app/main.py`
- Modify: `.env.example`
- Create: `tests/unit/test_config.py`
- Create: `tests/unit/test_pagination.py`
- Modify: `tests/test_health.py`
- Create: `tests/test_error_contract.py`

**Interfaces:**
- Produces: `Settings`, `get_settings() -> Settings`, `DomainError`, `ErrorDetail`, `ErrorResponse`, `PageParams`, `Page[T]`, `register_exception_handlers(app) -> None`.
- Produces: `GET /api/v1/health/live` and database-dependent `GET /api/v1/health/ready`.
- Consumes: existing FastAPI application factory and SQLAlchemy session dependency.

- [ ] **Step 1: Write failing configuration and pagination tests**

```python
# tests/unit/test_config.py
import pytest
from pydantic import ValidationError
from app.core.config import Settings

def test_production_rejects_unsafe_jwt_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://u:p@db/app",
            jwt_secret_key="change-me",
            cors_origins=["https://warehouse.example.com"],
            _env_file=None,
        )

# tests/unit/test_pagination.py
from pydantic import ValidationError
import pytest
from app.core.pagination import PageParams

def test_page_size_is_bounded() -> None:
    with pytest.raises(ValidationError):
        PageParams(page=1, page_size=101)
```

- [ ] **Step 2: Run the focused tests and verify the missing modules fail**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_config.py tests/unit/test_pagination.py -q`

Expected: collection fails because `app.core.config` and `app.core.pagination` do not exist.

- [ ] **Step 3: Implement typed settings and pagination primitives**

```python
# app/core/config.py
from functools import lru_cache
from typing import Literal
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "Smart Warehouse API"
    api_v1_prefix: str = "/api/v1"
    database_url: str
    jwt_secret_key: SecretStr
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_expire_minutes: int = Field(default=30, ge=5, le=1440)
    cors_origins: list[str] = []

    @model_validator(mode="after")
    def reject_unsafe_production_values(self) -> "Settings":
        secret = self.jwt_secret_key.get_secret_value()
        if self.app_env == "production" and (len(secret) < 32 or secret == "change-me"):
            raise ValueError("production JWT secret must contain at least 32 characters")
        return self

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

```python
# app/core/pagination.py
from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")

class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
```

- [ ] **Step 4: Write failing error-contract and probe tests**

```python
# tests/test_error_contract.py
def test_validation_error_uses_stable_contract(test_client) -> None:
    response = test_client.post("/api/v1/auth/login", json={"email": "bad"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"
    assert "fields" in response.json()["detail"]

# tests/test_health.py
def test_liveness_does_not_touch_database(test_client) -> None:
    response = test_client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
```

- [ ] **Step 5: Implement the common error model and exception handlers**

```python
# app/core/errors.py
from typing import Any
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

class ErrorDetail(BaseModel):
    code: str
    message: str
    fields: dict[str, list[str]] | None = None

class ErrorResponse(BaseModel):
    detail: ErrorDetail

class DomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str,
                 fields: dict[str, list[str]] | None = None) -> None:
        self.status_code, self.code, self.message, self.fields = status_code, code, message, fields

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(exc.status_code, {"detail": {
            "code": exc.code, "message": exc.message, "fields": exc.fields,
        }})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields: dict[str, list[str]] = {}
        for item in exc.errors():
            key = ".".join(str(part) for part in item["loc"] if part != "body") or "request"
            fields.setdefault(key, []).append(item["msg"])
        return JSONResponse(422, {"detail": {
            "code": "REQUEST_VALIDATION_ERROR",
            "message": "Request validation failed.",
            "fields": fields,
        }})
```

Register safe handlers for `HTTPException`, expected `IntegrityError`, and uncaught exceptions in
the same file. Log uncaught exceptions server-side and return `INTERNAL_SERVER_ERROR` without
including exception text.

- [ ] **Step 6: Move engine/CORS configuration to Settings and add probes**

```python
# app/main.py (route bodies)
@application.get(f"{settings.api_v1_prefix}/health/live", tags=["system"])
def liveness() -> dict[str, str]:
    return {"status": "alive"}

@application.get(f"{settings.api_v1_prefix}/health/ready", tags=["system"])
def readiness(session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise DomainError(503, "DATABASE_UNAVAILABLE", "Database is unavailable.") from error
    return {"status": "ready"}
```

Update `.env.example` to use `JWT_SECRET_KEY`, `JWT_EXPIRE_MINUTES`, and JSON-formatted
`CORS_ORIGINS`. Remove the SQLite runtime fallback from `app/db/session.py`; missing
`DATABASE_URL` must fail configuration loading.

- [ ] **Step 7: Run focused and baseline regression tests**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_config.py tests/unit/test_pagination.py tests/test_error_contract.py tests/test_health.py -q`

Expected: all listed tests pass and no error body contains SQL or an exception string.

- [ ] **Step 8: Commit the core contract**

```powershell
git add .env.example app/core app/db/session.py app/main.py tests/unit tests/test_error_contract.py tests/test_health.py
git commit -m "feat(core): add safe configuration and API contracts"
```

### Task 2: Disposable PostgreSQL Integration Test Harness

**Files:**
- Create: `docker-compose.test.yml`
- Create: `tests/postgres/__init__.py`
- Create: `tests/postgres/conftest.py`
- Create: `tests/postgres/test_migrations.py`
- Modify: `pyproject.toml`
- Replace: `tests/test_migration.py` (move its maintained coverage into `tests/postgres/test_migrations.py`)

**Interfaces:**
- Produces: `postgres_url`, `postgres_engine`, `postgres_session`, and `postgres_client` pytest fixtures.
- Produces: pytest marker `postgres` and a disposable PostgreSQL service on host port `55432`.
- Consumes: `TEST_DATABASE_URL`, Alembic configuration, `create_app()`, and `get_session`.

- [ ] **Step 1: Add a failing PostgreSQL migration test**

```python
# tests/postgres/test_migrations.py
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

pytestmark = pytest.mark.postgres

def test_migrations_build_expected_schema(postgres_url: str) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", postgres_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    tables = set(inspect(create_engine(postgres_url)).get_table_names())
    assert {"users", "products", "warehouses", "stocks", "transactions"} <= tables
```

- [ ] **Step 2: Run the test and verify it fails without the fixture/service**

Run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_migrations.py -q`

Expected: collection fails because fixture `postgres_url` is unavailable.

- [ ] **Step 3: Add the disposable PostgreSQL service**

```yaml
# docker-compose.test.yml
services:
  db_test:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: smart_warehouse_test
      POSTGRES_USER: smart_warehouse_test
      POSTGRES_PASSWORD: test-only
    ports:
      - "55432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U smart_warehouse_test -d smart_warehouse_test"]
      interval: 2s
      timeout: 3s
      retries: 20
```

- [ ] **Step 4: Implement PostgreSQL fixtures with database-name protection**

```python
# tests/postgres/conftest.py
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

@pytest.fixture(scope="session")
def postgres_url() -> str:
    value = os.environ.get("TEST_DATABASE_URL", "")
    if not value or not make_url(value).database.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must name a database ending in _test")
    return value

@pytest.fixture(scope="session")
def postgres_engine(postgres_url: str):
    engine = create_engine(postgres_url, pool_pre_ping=True)
    yield engine
    engine.dispose()

@pytest.fixture
def postgres_session(postgres_engine):
    with Session(postgres_engine) as session:
        yield session
        session.rollback()
    with postgres_engine.begin() as connection:
        connection.execute(text(
            "TRUNCATE transactions, inbounds, outbounds, stocks, products, categories, "
            "suppliers, warehouses, route_logs, purchase_requests, regions, users "
            "RESTART IDENTITY CASCADE"
        ))
```

Add `postgres_client` by overriding `get_session` with the fixture session. Configure the
`postgres` marker in `pyproject.toml` so unknown markers fail under the existing strict setting.

- [ ] **Step 5: Start PostgreSQL and run the migration test**

Run: `docker compose -f docker-compose.test.yml up -d db_test`

Run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_migrations.py -q`

Expected: the migration reaches `head` against PostgreSQL 16 and the table assertion passes.

- [ ] **Step 6: Commit the PostgreSQL harness**

```powershell
git add docker-compose.test.yml pyproject.toml tests/postgres tests/test_migration.py
git commit -m "test(db): add PostgreSQL integration harness"
```

### Task 3: Production Integrity Constraints and Administrative Audit Migration

**Files:**
- Create: `app/audit/__init__.py`
- Create: `app/audit/models.py`
- Modify: `app/models/__init__.py`
- Modify: `app/models/domain.py`
- Create: `alembic/versions/20260904_0002_production_baseline.py`
- Create: `tests/postgres/test_constraints.py`
- Modify: `tests/postgres/conftest.py`
- Modify: `tests/postgres/test_migrations.py`

**Interfaces:**
- Produces: `AuditLog` model with actor/action/target/before/after/time fields.
- Produces: PostgreSQL checks for normalized identity fields, coordinates, and stock-transaction linkage.
- Consumes: existing `User`, `Product`, `Warehouse`, `Stock`, `Inbound`, `Outbound`, and `StockTransaction` models.

- [ ] **Step 1: Write failing PostgreSQL constraint tests**

```python
# tests/postgres/test_constraints.py
import pytest
from sqlalchemy.exc import IntegrityError
from app.models import Warehouse

pytestmark = pytest.mark.postgres

def test_warehouse_rejects_unpaired_or_out_of_range_coordinates(postgres_session) -> None:
    postgres_session.add(Warehouse(
        code="HCM-01", name="Central", address="1 Nguyen Hue", latitude=91, longitude=None,
    ))
    with pytest.raises(IntegrityError):
        postgres_session.commit()

def test_normalized_email_is_unique_case_insensitively(postgres_session, make_user) -> None:
    postgres_session.add_all([
        make_user(email="client@example.com"), make_user(email="CLIENT@example.com"),
    ])
    with pytest.raises(IntegrityError):
        postgres_session.commit()
```

- [ ] **Step 2: Run the constraint tests and verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_constraints.py -q`

Expected: at least the coordinate and case-insensitive email tests fail because the new checks/indexes are absent.

- [ ] **Step 3: Add the audit model and model-level checks**

```python
# app/audit/models.py
from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.models.domain import IdentifierMixin, utc_now

class AuditLog(IdentifierMixin, Base):
    __tablename__ = "audit_logs"
    actor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[int] = mapped_column(nullable=False, index=True)
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
```

Add SQLAlchemy `CheckConstraint` definitions for paired/ranged coordinates and exactly one
movement link per stock transaction. Re-export `AuditLog` through `app.models`.

- [ ] **Step 4: Write the additive Alembic revision**

The revision must normalize existing email/SKU/warehouse codes before adding checks, create the
`audit_logs` table and indexes, and add named constraints/indexes:

```python
op.create_check_constraint(
    "ck_warehouses_coordinates_paired_and_ranged",
    "warehouses",
    "(latitude IS NULL AND longitude IS NULL) OR "
    "(latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)",
)
op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)
op.create_index("uq_products_sku_upper", "products", [sa.text("upper(sku)")], unique=True)
op.create_check_constraint(
    "ck_transactions_exactly_one_movement",
    "transactions",
    "(transaction_type = 'inbound' AND inbound_id IS NOT NULL AND outbound_id IS NULL) OR "
    "(transaction_type = 'outbound' AND outbound_id IS NOT NULL AND inbound_id IS NULL)",
)
```

The downgrade removes only objects introduced by revision `20260904_0002`; it does not recreate
the initial schema.

- [ ] **Step 5: Extend migration assertions and run PostgreSQL tests**

Assert `audit_logs` exists and inspect named checks/indexes. Then run:

`.venv\Scripts\python.exe -m pytest tests/postgres/test_migrations.py tests/postgres/test_constraints.py -q`

Expected: upgrade from base and upgrade from revision `20260829_0001` both reach head; all constraints pass.

- [ ] **Step 6: Commit the additive schema hardening**

```powershell
git add app/audit app/models alembic/versions/20260904_0002_production_baseline.py tests/postgres
git commit -m "feat(db): harden constraints and add audit log"
```

---

## Milestone 2 — Authentication, Users, and Administrative Audit

### Task 4: Refactor Authentication into Router, Service, and Repository

**Files:**
- Create: `app/auth/repository.py`
- Create: `app/auth/service.py`
- Modify: `app/auth/schemas.py`
- Modify: `app/auth/security.py`
- Modify: `app/auth/dependencies.py`
- Modify: `app/auth/router.py`
- Replace: `tests/test_auth.py`
- Create: `tests/unit/test_auth_schemas.py`
- Create: `tests/postgres/test_auth_integration.py`

**Interfaces:**
- Produces: `UserRepository.get_by_id()`, `get_by_email()`, `add()`.
- Produces: `AuthService.register(email, password) -> User` and `authenticate(email, password) -> User`.
- Produces: `create_access_token(user_id: int, settings: Settings, expires_delta=None) -> str` containing `sub`, `iat`, and `exp` only.
- Produces: strict `RegisterRequest`, `LoginRequest`, `TokenResponse`, and `UserResponse`.

- [ ] **Step 1: Write failing strict-registration and JWT tests**

```python
# tests/postgres/test_auth_integration.py
def test_registration_forbids_role_and_always_creates_client(postgres_client) -> None:
    rejected = postgres_client.post("/api/v1/auth/register", json={
        "email": "person@example.com", "password": "strong-password", "role": "admin",
    })
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"

    created = postgres_client.post("/api/v1/auth/register", json={
        "email": " Person@Example.com ", "password": "strong-password",
    })
    assert created.status_code == 201
    assert created.json()["role"] == "client"

def test_access_token_does_not_carry_authoritative_role(settings, client_user) -> None:
    token = create_access_token(client_user.id, settings)
    claims = jwt.decode(token, settings.jwt_secret_key.get_secret_value(), algorithms=["HS256"])
    assert set(claims) == {"sub", "iat", "exp"}
```

- [ ] **Step 2: Run the auth tests and confirm current behavior fails**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_auth_schemas.py tests/postgres/test_auth_integration.py -q`

Expected: public registration accepts role or the JWT still includes role.

- [ ] **Step 3: Make request schemas strict and normalize email**

```python
class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower()
```

Add `email-validator>=2.2,<3.0` to `pyproject.toml`. Apply the same normalization and strict-extra
policy to login without exposing whether an email exists.

- [ ] **Step 4: Implement repository and service ownership**

```python
class AuthService:
    def __init__(self, session: Session, users: UserRepository) -> None:
        self.session, self.users = session, users

    def register(self, email: str, password: str) -> User:
        user = User(email=email, password_hash=hash_password(password), role=UserRole.CLIENT)
        try:
            self.users.add(user)
            self.session.commit()
            self.session.refresh(user)
            return user
        except IntegrityError as error:
            self.session.rollback()
            raise DomainError(409, "USER_EMAIL_CONFLICT", "Email is already registered.") from error
```

Implement `authenticate()` as a read-only service method that returns the same
`INVALID_CREDENTIALS` response for missing, disabled, or mismatched users. The router builds the
response and contains no SQLAlchemy query or commit.

- [ ] **Step 5: Reload current user state from PostgreSQL on every protected request**

Update `get_current_user` to decode only `sub`, query `UserRepository.get_by_id`, and reject a
missing/disabled user. Preserve the centralized `Permission -> frozenset[UserRole]` mapping; add
`CATALOG_READ`, `SUPPLIER_WRITE`, `USER_MANAGE`, and `AUDIT_READ` instead of reusing unrelated
permissions.

- [ ] **Step 6: Run auth, error-contract, and security regressions**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_auth_schemas.py tests/postgres/test_auth_integration.py tests/test_error_contract.py -q`

Expected: all pass; responses and audit-capable serializers contain no `password_hash` field.

- [ ] **Step 7: Commit the authentication boundary**

```powershell
git add pyproject.toml app/auth tests/unit/test_auth_schemas.py tests/postgres/test_auth_integration.py tests/test_auth.py
git commit -m "fix(auth): secure registration and database-backed authorization"
```

### Task 5: Admin User Management with Atomic Administrative Audit

**Files:**
- Create: `app/users/__init__.py`
- Create: `app/users/schemas.py`
- Create: `app/users/repository.py`
- Create: `app/users/service.py`
- Create: `app/users/router.py`
- Create: `app/audit/schemas.py`
- Create: `app/audit/repository.py`
- Create: `app/audit/service.py`
- Create: `app/audit/router.py`
- Modify: `app/main.py`
- Create: `tests/unit/test_audit_payload.py`
- Create: `tests/postgres/test_users_audit.py`

**Interfaces:**
- Produces: `POST /api/v1/users`, `GET /users`, `GET /users/{id}`, `PATCH /users/{id}/role`, and `PATCH /users/{id}/status`.
- Produces: `GET /api/v1/audit-logs` and `GET /audit-logs/{id}`; no audit mutation route.
- Produces: `AuditService.record_user_event(actor, action, before, after) -> AuditLog` with allowlisted fields.
- Consumes: `PageParams`, `Page`, `DomainError`, `Permission.USER_MANAGE`, and `Permission.AUDIT_READ`.

- [ ] **Step 1: Write failing admin-action and self-protection tests**

```python
# tests/postgres/test_users_audit.py
def test_admin_creates_warehouse_user_and_audit_atomically(postgres_client, admin_headers) -> None:
    response = postgres_client.post("/api/v1/users", headers=admin_headers, json={
        "email": "operator@example.com", "password": "strong-password", "role": "warehouse",
    })
    assert response.status_code == 201
    assert response.json()["role"] == "warehouse"
    logs = postgres_client.get("/api/v1/audit-logs", headers=admin_headers).json()["items"]
    assert [(row["action"], row["after_data"]["role"]) for row in logs] == [
        ("user.created", "warehouse")
    ]
    assert "password" not in str(logs).lower()

def test_admin_cannot_modify_an_admin(postgres_client, admin, admin_headers) -> None:
    for path, payload in [
        (f"/api/v1/users/{admin.id}/status", {"is_active": False}),
        (f"/api/v1/users/{admin.id}/role", {"role": "client"}),
    ]:
        response = postgres_client.patch(path, headers=admin_headers, json=payload)
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "ADMIN_ACCOUNT_PROTECTED"
```

- [ ] **Step 2: Run the user-management test and confirm routes are missing**

Run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_users_audit.py -q`

Expected: requests return `404` because the users and audit routers do not exist.

- [ ] **Step 3: Implement strict user and audit schemas**

```python
class ManagedRole(StrEnum):
    CLIENT = "client"
    WAREHOUSE = "warehouse"

class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: ManagedRole

class UserRoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: ManagedRole

class UserStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool
```

Audit response schemas expose `before_data`/`after_data` and UTC timestamps, never user hashes.

- [ ] **Step 4: Implement domain-specific repositories without commit**

`UserRepository` supplies paginated list/count/get/add and mutation of loaded entities.
`AuditRepository` supplies add/list/count/get. Verify with this architectural test:

```python
def test_repositories_do_not_commit(monkeypatch, postgres_session) -> None:
    def forbidden() -> None:
        raise AssertionError("repository called commit")
    monkeypatch.setattr(postgres_session, "commit", forbidden)
    UserRepository(postgres_session).list(PageParams())
    AuditRepository(postgres_session).list(PageParams())
```

- [ ] **Step 5: Implement service transaction and audit behavior**

```python
def change_status(self, actor: User, target_id: int, is_active: bool) -> User:
    target = self.users.require(target_id)
    if target.role is UserRole.ADMIN or target.id == actor.id:
        raise DomainError(409, "ADMIN_ACCOUNT_PROTECTED", "Admin account cannot be modified.")
    before = {"email": target.email, "role": target.role.value, "is_active": target.is_active}
    target.is_active = is_active
    try:
        self.audit.record(actor.id, "user.status_changed", "user", target.id, before,
                          {**before, "is_active": is_active})
        self.session.commit()
        self.session.refresh(target)
        return target
    except Exception:
        self.session.rollback()
        raise
```

Use the same transaction pattern for internal creation and role changes. Convert known unique
conflicts to `USER_EMAIL_CONFLICT`; allow the safe global handler to sanitize unexpected audit
failures.

- [ ] **Step 6: Test rollback when audit persistence fails**

Patch `AuditRepository.add` to raise during internal user creation, call the service, then assert a
new independent PostgreSQL session finds neither the user nor audit row. This test must verify
database state after rollback, not only the raised error.

- [ ] **Step 7: Run focused user/audit and auth tests**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_audit_payload.py tests/postgres/test_users_audit.py tests/postgres/test_auth_integration.py -q`

Expected: all pass; only admins can call either router, no ordinary API can assign `admin`, and audit is atomic.

- [ ] **Step 8: Commit user administration and audit**

```powershell
git add app/users app/audit app/main.py tests/unit/test_audit_payload.py tests/postgres/test_users_audit.py
git commit -m "feat(users): add audited admin account management"
```

---

## Milestone 3 — Master Data and Warehouses

### Task 6: Category Repository, Service, Authenticated Reads, and Cycle Validation

**Files:**
- Create: `app/master_data/repository.py`
- Create: `app/master_data/service.py`
- Modify: `app/master_data/schemas.py`
- Modify: `app/master_data/router.py`
- Create: `tests/unit/test_architecture.py`
- Create: `tests/postgres/test_categories.py`
- Modify: `tests/test_master_data.py` (remove superseded category cases)

**Interfaces:**
- Produces: `CategoryRepository.list/count/get/add/delete` and `CategoryService.list/get/create/update/delete`.
- Produces: authenticated CRUD routes at `/api/v1/categories` with `CATALOG_READ` for reads and `PRODUCT_WRITE` for mutations.
- Consumes: `PageParams`, `Page[CategoryResponse]`, `DomainError`, and a request-scoped `Session`.

- [ ] **Step 1: Write failing authentication and indirect-cycle tests**

```python
# tests/postgres/test_categories.py
def test_category_reads_require_authentication(postgres_client) -> None:
    response = postgres_client.get("/api/v1/categories")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"

def test_category_rejects_indirect_parent_cycle(postgres_client, admin_headers) -> None:
    root = create_category(postgres_client, admin_headers, "Root")
    child = create_category(postgres_client, admin_headers, "Child", root["id"])
    response = postgres_client.put(
        f"/api/v1/categories/{root['id']}", headers=admin_headers,
        json={"name": "Root", "parent_id": child["id"]},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "CATEGORY_PARENT_CYCLE"
```

- [ ] **Step 2: Run category tests and observe public-read/cycle failures**

Run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_categories.py -q`

Expected: anonymous read succeeds unexpectedly or indirect cycle is accepted.

- [ ] **Step 3: Implement category repository and service**

```python
class CategoryService:
    def update(self, category_id: int, request: CategoryUpdate) -> Category:
        category = self.categories.require(category_id)
        parent = self.categories.get(request.parent_id) if request.parent_id else None
        cursor = parent
        while cursor is not None:
            if cursor.id == category.id:
                raise DomainError(422, "CATEGORY_PARENT_CYCLE", "Category hierarchy contains a cycle.")
            cursor = self.categories.get(cursor.parent_id) if cursor.parent_id else None
        category.name, category.parent_id = request.name.strip(), request.parent_id
        return self._commit_or_conflict(category, "CATEGORY_NAME_CONFLICT")
```

The router constructs the service from the injected session, declares permission dependencies,
and delegates without importing `select`, `func`, or `IntegrityError`.

- [ ] **Step 4: Add an architecture test that forbids repository commit calls**

```python
# tests/unit/test_architecture.py
import ast
from pathlib import Path

def test_repository_modules_never_call_commit() -> None:
    offenders: list[str] = []
    for path in Path("app").glob("**/repository.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "commit":
                    offenders.append(f"{path}:{node.lineno}")
    assert offenders == []
```

- [ ] **Step 5: Run category and architecture tests**

Run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_categories.py tests/unit/test_architecture.py -q`

Expected: anonymous receives `401`, authenticated roles can read, only admin mutates, cycles and references return stable errors.

- [ ] **Step 6: Commit the category domain slice**

```powershell
git add app/master_data tests/unit/test_architecture.py tests/postgres/test_categories.py tests/test_master_data.py
git commit -m "refactor(categories): add service and repository boundary"
```

### Task 7: Supplier Repository and Service Slice

**Files:**
- Modify: `app/master_data/repository.py`
- Modify: `app/master_data/service.py`
- Modify: `app/master_data/schemas.py`
- Modify: `app/master_data/router.py`
- Create: `tests/postgres/test_suppliers.py`
- Modify: `tests/test_master_data.py` (remove superseded supplier cases)

**Interfaces:**
- Produces: `SupplierRepository.list/count/get/add/delete` and `SupplierService.list/get/create/update/delete`.
- Produces: bounded, filterable `/api/v1/suppliers` responses.
- Consumes: `SUPPLIER_READ` for admin/warehouse and `SUPPLIER_WRITE` for admin.

- [ ] **Step 1: Write failing supplier RBAC, normalization, and conflict tests**

```python
def test_supplier_permissions_and_normalized_email(postgres_client, role_headers) -> None:
    payload = {"name": "Main Supply", "email": " SALES@Example.COM "}
    assert postgres_client.post(
        "/api/v1/suppliers", headers=role_headers["warehouse"], json=payload
    ).status_code == 403
    created = postgres_client.post(
        "/api/v1/suppliers", headers=role_headers["admin"], json=payload
    )
    assert created.status_code == 201
    assert created.json()["email"] == "sales@example.com"
    assert postgres_client.get(
        "/api/v1/suppliers", headers=role_headers["client"]
    ).status_code == 403
```

- [ ] **Step 2: Run supplier tests and confirm router-owned persistence fails the architecture target**

Run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_suppliers.py tests/unit/test_architecture.py -q`

Expected: normalization or stable errors fail before the new service/repository behavior.

- [ ] **Step 3: Add strict schemas and supplier query filters**

`SupplierCreate` and `SupplierUpdate` use `extra="forbid"`, normalize optional email, trim name,
phone, and address, and reject empty strings after trimming. `SupplierRepository.list()` accepts
`search: str | None`, `PageParams`, and orders by `id` for stable pagination.

- [ ] **Step 4: Implement service transaction/error mapping**

```python
def create(self, request: SupplierCreate) -> Supplier:
    supplier = Supplier(**request.model_dump())
    try:
        self.suppliers.add(supplier)
        self.session.commit()
        self.session.refresh(supplier)
        return supplier
    except IntegrityError as error:
        self.session.rollback()
        raise DomainError(409, "SUPPLIER_CONFLICT", "Supplier already exists.") from error
```

Delete maps referenced products to `SUPPLIER_IN_USE`; get/update missing records map to
`SUPPLIER_NOT_FOUND`.

- [ ] **Step 5: Run supplier, category, and architecture tests**

Run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_suppliers.py tests/postgres/test_categories.py tests/unit/test_architecture.py -q`

Expected: all pass and repository files remain free of commits.

- [ ] **Step 6: Commit the supplier slice**

```powershell
git add app/master_data tests/postgres/test_suppliers.py tests/test_master_data.py
git commit -m "refactor(suppliers): add validated domain service"
```

### Task 8: Product Repository and Service Slice

**Files:**
- Modify: `app/master_data/repository.py`
- Modify: `app/master_data/service.py`
- Modify: `app/master_data/schemas.py`
- Modify: `app/master_data/router.py`
- Create: `tests/postgres/test_products.py`
- Modify: `tests/test_master_data.py` (remove superseded product cases)

**Interfaces:**
- Produces: `ProductRepository.list/count/get/add/delete` and `ProductService.list/get/create/update/delete`.
- Produces: authenticated, bounded product reads and admin-only writes with `search`, `category_id`, `supplier_id`, and `is_active` filters.
- Consumes: category/supplier repository lookups and PostgreSQL normalized SKU uniqueness.

- [ ] **Step 1: Write failing product authentication, normalization, and reference tests**

```python
def test_product_is_authenticated_and_sku_is_normalized(
    postgres_client, admin_headers, client_headers, category,
) -> None:
    assert postgres_client.get("/api/v1/products").status_code == 401
    created = postgres_client.post("/api/v1/products", headers=admin_headers, json={
        "sku": " sku-001 ", "name": "Bolt", "category_id": category.id,
        "supplier_id": None, "unit": "each", "reorder_level": 0, "is_active": True,
    })
    assert created.status_code == 201
    assert created.json()["sku"] == "SKU-001"
    assert postgres_client.get("/api/v1/products", headers=client_headers).status_code == 200
```

- [ ] **Step 2: Run product tests and verify current public-read/raw-SKU behavior fails**

Run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_products.py -q`

Expected: anonymous access or SKU normalization assertion fails.

- [ ] **Step 3: Implement strict schemas and product repository filters**

Use separate create/update schemas, both `extra="forbid"`. Normalize SKU with
`value.strip().upper()`, trim textual fields, enforce `reorder_level >= 0`, and reject an empty
unit. Repository results order by product `id`; list/count apply identical filters.

- [ ] **Step 4: Implement product business rules and stable domain errors**

```python
def _validate_references(self, category_id: int, supplier_id: int | None) -> None:
    if self.categories.get(category_id) is None:
        raise DomainError(422, "CATEGORY_NOT_FOUND", "Category does not exist.")
    if supplier_id is not None and self.suppliers.get(supplier_id) is None:
        raise DomainError(422, "SUPPLIER_NOT_FOUND", "Supplier does not exist.")
```

Map unique SKU conflicts to `PRODUCT_SKU_CONFLICT`, missing records to `PRODUCT_NOT_FOUND`, and
referenced deletion to `PRODUCT_IN_USE`. Router methods only adapt HTTP inputs/outputs.

- [ ] **Step 5: Run all master-data PostgreSQL tests and architecture test**

Run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_categories.py tests/postgres/test_suppliers.py tests/postgres/test_products.py tests/unit/test_architecture.py -q`

Expected: all pass with no anonymous catalogue access.

- [ ] **Step 6: Commit the product slice**

```powershell
git add app/master_data tests/postgres/test_products.py tests/test_master_data.py
git commit -m "refactor(products): add secure product service slice"
```

### Task 9: Warehouse Repository, Service, Coordinates, and Protected Delete

**Files:**
- Create: `app/warehouse/repository.py`
- Create: `app/warehouse/service.py`
- Modify: `app/warehouse/schemas.py`
- Modify: `app/warehouse/router.py`
- Create: `tests/postgres/test_warehouses.py`
- Modify: `tests/test_warehouses.py` (retain only database-independent unit coverage)

**Interfaces:**
- Produces: `WarehouseRepository.list/count/get/add/delete` and `WarehouseService.list/get/create/update/delete`.
- Produces: paginated `/api/v1/warehouses` with `search` filter, authenticated reads, and admin-only mutations.
- Consumes: coordinate database constraint from Task 3 and common pagination/errors.

- [ ] **Step 1: Write failing coordinate and delete-contract API tests**

```python
def test_coordinates_must_be_paired_and_ranged(postgres_client, admin_headers) -> None:
    response = postgres_client.post("/api/v1/warehouses", headers=admin_headers, json={
        "code": "HCM-01", "name": "Central", "address": "1 Nguyen Hue",
        "latitude": 10.77, "longitude": None,
    })
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"

def test_referenced_warehouse_cannot_be_deleted(
    postgres_client, admin_headers, stocked_warehouse,
) -> None:
    response = postgres_client.delete(
        f"/api/v1/warehouses/{stocked_warehouse.id}", headers=admin_headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "WAREHOUSE_IN_USE"
```

- [ ] **Step 2: Run warehouse tests and verify missing delete/validation behavior**

Run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_warehouses.py -q`

Expected: coordinate response or delete route fails.

- [ ] **Step 3: Implement strict paired-coordinate schema validation**

```python
@model_validator(mode="after")
def coordinates_are_paired(self) -> "WarehouseWrite":
    if (self.latitude is None) != (self.longitude is None):
        raise ValueError("latitude and longitude must be provided together")
    return self
```

Declare latitude/longitude bounds with `Field(ge=..., le=...)`, normalize warehouse code to
uppercase, trim name/address, and use separate response schema with UTC timestamps.

- [ ] **Step 4: Implement warehouse service/repository and delete route**

Service maps code/name conflicts to `WAREHOUSE_CONFLICT`, missing records to
`WAREHOUSE_NOT_FOUND`, and foreign-key delete failures to `WAREHOUSE_IN_USE`. Repository applies
stable pagination/filtering and contains no transaction boundary.

- [ ] **Step 5: Run warehouse, constraint, and architecture tests**

Run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_warehouses.py tests/postgres/test_constraints.py tests/unit/test_architecture.py -q`

Expected: all pass for admin, warehouse, and client read rules; only admin can mutate.

- [ ] **Step 6: Commit the warehouse slice**

```powershell
git add app/warehouse tests/postgres/test_warehouses.py tests/test_warehouses.py
git commit -m "refactor(warehouses): add validated service slice"
```

---

## Milestone 4 — Inventory, Concurrency, Dashboard, and Complete RBAC

### Task 10: Paginated Inventory and Movement-History Reads

**Files:**
- Create: `app/inventory/repository.py`
- Create: `app/inventory/service.py`
- Modify: `app/inventory/schemas.py`
- Modify: `app/inventory/router.py`
- Create: `tests/postgres/test_inventory_reads.py`
- Modify: `tests/test_inventory.py` (remove superseded integration cases)

**Interfaces:**
- Produces: `InventoryRepository` read/query methods and `InventoryService` read methods.
- Produces: paginated/filterable `GET /stock`, `/inbounds`, `/outbounds`, and `/transactions`, plus detail routes for each resource.
- Consumes: `INVENTORY_READ` for admin/warehouse/client stock and `INVENTORY_HISTORY_READ` for admin/warehouse movement/history access.

- [ ] **Step 1: Write failing pagination, filter, detail, and client-boundary tests**

```python
def test_inventory_collections_are_bounded_and_filtered(
    postgres_client, warehouse_headers, seeded_movements,
) -> None:
    response = postgres_client.get(
        f"/api/v1/transactions?page=1&page_size=1&warehouse_id={seeded_movements.warehouse_id}",
        headers=warehouse_headers,
    )
    body = response.json()
    assert response.status_code == 200
    assert body["page_size"] == 1
    assert len(body["items"]) == 1
    assert body["total"] == 2

def test_client_reads_stock_but_not_movements(postgres_client, client_headers) -> None:
    assert postgres_client.get("/api/v1/stock", headers=client_headers).status_code == 200
    assert postgres_client.get("/api/v1/inbounds", headers=client_headers).status_code == 403
    assert postgres_client.get("/api/v1/transactions", headers=client_headers).status_code == 403
```

- [ ] **Step 2: Run inventory-read tests and verify collection shape/routes fail**

Run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_inventory_reads.py -q`

Expected: list responses are raw arrays or movement detail/list routes return `404`.

- [ ] **Step 3: Define strict read/filter/response schemas**

`InventoryFilters` accepts `warehouse_id`, `product_id`, `created_from`, and `created_to` with
positive IDs and validates `created_from <= created_to`. `TransactionFilters` additionally accepts
`transaction_type`. Response schemas expose IDs, quantities, references/notes where applicable,
creator ID, and timezone-aware `created_at`.

- [ ] **Step 4: Implement domain-specific read queries**

```python
def list_transactions(self, filters: TransactionFilters, page: PageParams):
    statement = select(StockTransaction).order_by(StockTransaction.id.desc())
    statement = self._apply_transaction_filters(statement, filters)
    items = list(self.session.scalars(statement.offset(page.offset).limit(page.page_size)))
    total = self.session.scalar(
        select(func.count()).select_from(self._apply_transaction_filters(
            select(StockTransaction.id), filters
        ).subquery())
    ) or 0
    return items, total
```

Implement each domain query explicitly rather than introducing a generic repository. Service
maps missing detail records to resource-specific `404` codes.

- [ ] **Step 5: Run inventory-read, RBAC-adjacent, and architecture tests**

Run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_inventory_reads.py tests/unit/test_architecture.py -q`

Expected: all collection/detail/filter and role assertions pass.

- [ ] **Step 6: Commit inventory read contracts**

```powershell
git add app/inventory tests/postgres/test_inventory_reads.py tests/test_inventory.py
git commit -m "feat(inventory): add paginated movement history"
```

### Task 11: PostgreSQL-Safe Inventory Writes and Concurrency Verification

**Files:**
- Modify: `app/inventory/repository.py`
- Modify: `app/inventory/service.py`
- Modify: `app/inventory/router.py`
- Modify: `app/inventory/schemas.py`
- Create: `tests/postgres/test_inventory_transactions.py`
- Create: `tests/postgres/test_inventory_concurrency.py`
- Modify: `tests/test_inventory.py` (retain database-independent schema tests only)

**Interfaces:**
- Produces: `InventoryService.create_inbound(actor_id, request) -> Inbound` and `create_outbound(actor_id, request) -> Outbound`.
- Produces: `InventoryRepository.get_stock_for_update()`, `insert_stock_if_absent()`, and append-only movement/stock-transaction methods.
- Consumes: PostgreSQL unique stock pair, `INVENTORY_WRITE`, and the movement response schemas from Task 10.

- [ ] **Step 1: Write failing atomicity tests for successful and rejected movements**

```python
# tests/postgres/test_inventory_transactions.py
def test_outbound_is_atomic_and_has_exactly_one_business_audit(
    postgres_session, inventory_service, operator, stocked_product,
) -> None:
    movement = InventoryMovementCreate(
        warehouse_id=stocked_product.warehouse_id,
        product_id=stocked_product.product_id,
        quantity=3,
    )
    outbound = inventory_service.create_outbound(operator.id, movement)
    assert current_quantity(postgres_session, stocked_product) == 2
    assert count_outbounds(postgres_session) == 1
    assert count_stock_transactions(postgres_session, outbound_id=outbound.id) == 1
    assert count_admin_audits(postgres_session) == 0

    with pytest.raises(DomainError) as error:
        inventory_service.create_outbound(operator.id, movement.model_copy(update={"quantity": 9}))
    assert error.value.code == "INSUFFICIENT_STOCK"
    assert current_quantity(postgres_session, stocked_product) == 2
    assert count_outbounds(postgres_session) == 1
    assert count_stock_transactions(postgres_session) == 1
```

- [ ] **Step 2: Write failing concurrent-first-inbound and competing-outbound tests**

```python
# tests/postgres/test_inventory_concurrency.py
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session

def test_concurrent_first_inbounds_do_not_lose_quantity(
    postgres_engine, warehouse_id, product_id, operator_id,
) -> None:
    def receive(quantity: int) -> None:
        with Session(postgres_engine) as session:
            InventoryService(session).create_inbound(
                operator_id,
                InventoryMovementCreate(
                    warehouse_id=warehouse_id, product_id=product_id, quantity=quantity,
                ),
            )
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(receive, [7, 11]))
    with Session(postgres_engine) as check:
        assert stock_quantity(check, warehouse_id, product_id) == 18
        assert movement_counts(check) == {"inbounds": 2, "transactions": 2, "audits": 0}

def test_competing_outbounds_cannot_oversell(postgres_engine, stock_of_ten, operator_id) -> None:
    results = run_two_outbounds(postgres_engine, stock_of_ten, operator_id, quantity=7)
    assert sorted(result.code if isinstance(result, DomainError) else "ok" for result in results) == [
        "INSUFFICIENT_STOCK", "ok"
    ]
    with Session(postgres_engine) as check:
        assert stock_quantity(check, stock_of_ten.warehouse_id, stock_of_ten.product_id) == 3
        assert movement_counts(check) == {"outbounds": 1, "transactions": 1, "audits": 0}
```

Use a `threading.Barrier` inside the test helper so both worker sessions begin together. Add a
controlled inbound/outbound interaction test that holds a row lock in one session, starts the
second operation, releases the first transaction, and asserts the waiting operation evaluates the
committed quantity rather than a stale value.

- [ ] **Step 3: Run the transaction/concurrency tests and verify the current first-row race**

Run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_inventory_transactions.py tests/postgres/test_inventory_concurrency.py -q`

Expected: the existing router-level implementation fails service imports, and concurrent initial stock creation is not safely handled.

- [ ] **Step 4: Implement existing-row lock and first-row conflict handling**

```python
# app/inventory/repository.py
def get_stock_for_update(self, warehouse_id: int, product_id: int) -> Stock | None:
    return self.session.scalar(
        select(Stock).where(
            Stock.warehouse_id == warehouse_id,
            Stock.product_id == product_id,
        ).with_for_update()
    )

def insert_stock_if_absent(
    self, warehouse_id: int, product_id: int, quantity: int,
) -> Stock | None:
    statement = insert(Stock).values(
        warehouse_id=warehouse_id, product_id=product_id, quantity=quantity,
    ).on_conflict_do_nothing(
        index_elements=[Stock.warehouse_id, Stock.product_id]
    ).returning(Stock.id)
    stock_id = self.session.scalar(statement)
    return self.session.get(Stock, stock_id) if stock_id is not None else None
```

Inbound algorithm:

1. Validate warehouse and product.
2. Select existing stock `FOR UPDATE`.
3. If found, increment it.
4. If absent, `INSERT ... ON CONFLICT DO NOTHING` with the full inbound quantity.
5. If another transaction won the insert, select the canonical row `FOR UPDATE` and increment it.
6. Add inbound and exactly one linked stock transaction.
7. Commit once in the service; rollback any exception.

- [ ] **Step 5: Implement outbound lock/check/decrement in the service**

```python
def create_outbound(self, actor_id: int, request: InventoryMovementCreate) -> Outbound:
    try:
        self._require_references(request)
        stock = self.inventory.get_stock_for_update(request.warehouse_id, request.product_id)
        if stock is None or stock.quantity < request.quantity:
            raise DomainError(409, "INSUFFICIENT_STOCK", "Insufficient stock.")
        stock.quantity -= request.quantity
        outbound = self.inventory.add_outbound(request, actor_id)
        self.session.flush()
        self.inventory.add_stock_transaction_for_outbound(outbound, actor_id)
        self.session.commit()
        self.session.refresh(outbound)
        return outbound
    except Exception:
        self.session.rollback()
        raise
```

Do not catch and transform `DomainError` into a `500`. Repository methods do not commit, and no
inventory service calls `AuditRepository`.

- [ ] **Step 6: Run each concurrency case repeatedly**

Run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_inventory_concurrency.py -q --count=10`

If `pytest-repeat` is not added, use PowerShell:

```powershell
1..10 | ForEach-Object { .venv\Scripts\python.exe -m pytest tests/postgres/test_inventory_concurrency.py -q; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
```

Expected: all ten runs pass with final stock, movement history, and zero administrative audit rows exactly as asserted.

- [ ] **Step 7: Run inventory regressions and commit**

Run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_inventory_reads.py tests/postgres/test_inventory_transactions.py tests/postgres/test_inventory_concurrency.py tests/unit/test_architecture.py -q`

```powershell
git add app/inventory tests/postgres/test_inventory_transactions.py tests/postgres/test_inventory_concurrency.py tests/test_inventory.py
git commit -m "fix(inventory): make stock movements concurrency-safe"
```

### Task 12: Dashboard Service and Complete RBAC/Architecture Matrix

**Files:**
- Create: `app/dashboard/repository.py`
- Create: `app/dashboard/service.py`
- Modify: `app/dashboard/router.py`
- Modify: `app/auth/dependencies.py`
- Create: `tests/postgres/test_dashboard.py`
- Create: `tests/postgres/test_rbac_matrix.py`
- Modify: `tests/unit/test_architecture.py`
- Modify: `tests/test_dashboard.py` (retain database-independent schema tests only)

**Interfaces:**
- Produces: `DashboardRepository.get_stats() -> DashboardStats` and `DashboardService.get_stats()`.
- Produces: complete permission mapping for catalogue, supplier, warehouse, inventory, dashboard, users, and audit actions.
- Consumes: all routers completed in Tasks 4–11.

- [ ] **Step 1: Write a failing single-snapshot dashboard test**

```python
def test_dashboard_is_admin_only_and_uses_database_aggregates(
    postgres_client, admin_headers, client_headers, dashboard_dataset,
) -> None:
    assert postgres_client.get(
        "/api/v1/dashboard/stats", headers=client_headers
    ).status_code == 403
    response = postgres_client.get("/api/v1/dashboard/stats", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == {
        "product_count": 3, "total_stock": 29, "low_stock_count": 2,
    }
```

- [ ] **Step 2: Implement a repository query with one PostgreSQL statement**

```python
def get_stats(self) -> DashboardStats:
    product_count = select(func.count(Product.id)).scalar_subquery()
    total_stock = select(func.coalesce(func.sum(Stock.quantity), 0)).scalar_subquery()
    low_stock_count = select(func.count(Stock.id)).join(
        Product, Product.id == Stock.product_id
    ).where(Stock.quantity <= Product.reorder_level).scalar_subquery()
    row = self.session.execute(select(product_count, total_stock, low_stock_count)).one()
    return DashboardStats(
        product_count=row[0], total_stock=row[1], low_stock_count=row[2],
    )
```

The service delegates the read and the router contains no SQLAlchemy aggregate code.

- [ ] **Step 3: Write the full route-and-action RBAC matrix**

```python
@pytest.mark.parametrize(("method", "path", "allowed"), [
    ("get", "/api/v1/products", {"admin", "warehouse", "client"}),
    ("post", "/api/v1/products", {"admin"}),
    ("get", "/api/v1/suppliers", {"admin", "warehouse"}),
    ("post", "/api/v1/suppliers", {"admin"}),
    ("get", "/api/v1/warehouses", {"admin", "warehouse", "client"}),
    ("post", "/api/v1/inbounds", {"admin", "warehouse"}),
    ("get", "/api/v1/transactions", {"admin", "warehouse"}),
    ("get", "/api/v1/dashboard/stats", {"admin"}),
    ("get", "/api/v1/users", {"admin"}),
    ("get", "/api/v1/audit-logs", {"admin"}),
])
def test_rbac_matrix(postgres_client, role_headers, request_case, method, path, allowed):
    for role, headers in role_headers.items():
        response = request_case(postgres_client, method, path, headers)
        assert (response.status_code < 400) is (role in allowed)
```

Provide valid request payloads and prerequisite records per action so an allowed request cannot
pass the test merely by returning a validation/not-found error. Add explicit action tests for
assigning `admin`, modifying an admin, client inventory mutation, warehouse master-data mutation,
and client history access.

- [ ] **Step 4: Add router boundary checks**

Extend `tests/unit/test_architecture.py` to parse every `router.py` and fail on imports from
`sqlalchemy`, calls to `.commit()`/`.rollback()`, or direct model persistence. Allow imports from
schemas, services, auth dependencies, FastAPI, and core types.

- [ ] **Step 5: Run dashboard, RBAC, and architecture tests**

Run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_dashboard.py tests/postgres/test_rbac_matrix.py tests/unit/test_architecture.py -q`

Expected: all route and action combinations match the approved matrix; routers/repositories satisfy their boundaries.

- [ ] **Step 6: Run the full backend gate**

Run: `.venv\Scripts\python.exe -m ruff check app tests alembic`

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: Ruff and all unit/PostgreSQL tests pass with `TEST_DATABASE_URL` configured.

- [ ] **Step 7: Commit dashboard and RBAC completion**

```powershell
git add app/dashboard app/auth/dependencies.py tests/postgres/test_dashboard.py tests/postgres/test_rbac_matrix.py tests/unit/test_architecture.py tests/test_dashboard.py
git commit -m "test(rbac): enforce the complete Phase 1 permission matrix"
```

---

## Milestone 5 — Frontend Feature Architecture and Critical UX

### Task 13: Frontend Tooling, Shared API Client, Providers, and Application Shell

**Files:**
- Modify: `client/package.json`
- Modify: `client/package-lock.json` (generated only by `npm install`)
- Modify: `client/vite.config.ts`
- Modify: `client/tsconfig.app.json`
- Create: `client/src/test/setup.ts`
- Create: `client/src/shared/api/ApiError.ts`
- Create: `client/src/shared/api/ApiClient.ts`
- Create: `client/src/shared/api/types.ts`
- Create: `client/src/shared/ui/AsyncState.tsx`
- Create: `client/src/shared/ui/Pagination.tsx`
- Create: `client/src/app/Providers.tsx`
- Create: `client/src/app/AppShell.tsx`
- Create: `client/src/app/navigation.ts`
- Modify: `client/src/main.tsx`
- Replace: `client/src/styles.css`
- Create: `client/src/shared/api/ApiClient.test.ts`
- Create: `client/src/shared/ui/AsyncState.test.tsx`

**Interfaces:**
- Produces: `ApiError {status, code, message, fields}`, `ApiClient.request<T>()`, `Page<T>`, `Providers`, `AppShell`, `AsyncState`, and `Pagination`.
- Produces: npm scripts `test`, `test:coverage`, `typecheck`, and `build`.
- Consumes: `VITE_API_BASE_URL`, the approved backend error/page contract, and browser timezone formatting.

- [ ] **Step 1: Install approved runtime and test dependencies**

Run from `client`:

```powershell
npm.cmd install react-router-dom @tanstack/react-query react-hook-form zod @hookform/resolvers
npm.cmd install --save-dev vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event @vitest/coverage-v8
```

Review `package.json` and ensure test libraries are in `devDependencies`, then retain the generated
lockfile.

- [ ] **Step 2: Add failing API-client behavior tests**

```typescript
// client/src/shared/api/ApiClient.test.ts
it('clears auth on 401 but preserves a 403 session and domain details', async () => {
  const onUnauthorized = vi.fn()
  const client = new ApiClient('/api/v1', () => 'token', onUnauthorized)
  server.use(http.get('/api/v1/users', () => HttpResponse.json({
    detail: { code: 'PERMISSION_DENIED', message: 'Permission denied.', fields: null },
  }, { status: 403 })))

  await expect(client.request('/users')).rejects.toMatchObject({
    status: 403, code: 'PERMISSION_DENIED', message: 'Permission denied.',
  })
  expect(onUnauthorized).not.toHaveBeenCalled()
})
```

Use `vi.stubGlobal('fetch', vi.fn())` instead of adding MSW unless more than three suites need
network interception. Add a second assertion that a `401` invokes `onUnauthorized` exactly once.

- [ ] **Step 3: Configure Vitest and run the missing-client failure**

```typescript
// client/vite.config.ts
export default defineConfig({
  plugins: [react()],
  test: { environment: 'jsdom', setupFiles: './src/test/setup.ts' },
  server: { host: '0.0.0.0', port: 5173 },
})
```

Run: `npm.cmd test -- --run src/shared/api/ApiClient.test.ts`

Expected: test fails because `ApiClient` is not implemented.

- [ ] **Step 4: Implement the typed API error/client contract**

```typescript
// client/src/shared/api/ApiClient.ts
export class ApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly getToken: () => string | null,
    private readonly onUnauthorized: () => void,
  ) {}

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const token = this.getToken()
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: {
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    })
    const body = response.status === 204 ? null : await response.json().catch(() => null)
    if (!response.ok) {
      const error = ApiError.fromResponse(response.status, body)
      if (response.status === 401) this.onUnauthorized()
      throw error
    }
    return body as T
  }
}
```

`ApiError.fromResponse()` preserves backend `code`, `message`, and `fields`; only malformed error
bodies fall back to `UNEXPECTED_RESPONSE`. It does not turn `403` or domain conflicts into generic
network errors.

- [ ] **Step 5: Implement providers and reusable async/page controls**

Create one `QueryClient` with bounded retry behavior: no retry for `400`–`499`; at most one retry
for transient server/network errors. `AsyncState` must render accessible loading, error, and empty
states. `Pagination` disables invalid previous/next navigation and exposes the current page.

- [ ] **Step 6: Build the responsive application shell**

Move global tokens/layout styles to the replacement stylesheet. Preserve the existing dark
warehouse visual identity, keyboard focus visibility, responsive tables, and readable contrast.
`AppShell` receives navigation items rather than hard-coding authorization decisions.

- [ ] **Step 7: Run frontend unit/type/build checks**

Run: `npm.cmd test -- --run`

Run: `npm.cmd run typecheck`

Run: `npm.cmd run build`

Expected: API client/UI tests pass; TypeScript and Vite production build succeed.

- [ ] **Step 8: Commit frontend foundation**

```powershell
git add client/package.json client/package-lock.json client/vite.config.ts client/tsconfig.app.json client/src
git commit -m "feat(web): add feature-ready application foundation"
```

### Task 14: Authentication State, Registration, Login, and Role-Aware Routes

**Files:**
- Create: `client/src/features/auth/types.ts`
- Create: `client/src/features/auth/schemas.ts`
- Create: `client/src/features/auth/api.ts`
- Create: `client/src/features/auth/AuthProvider.tsx`
- Create: `client/src/features/auth/useAuth.ts`
- Create: `client/src/features/auth/RequireAuth.tsx`
- Create: `client/src/features/auth/RequireRole.tsx`
- Create: `client/src/features/auth/LoginPage.tsx`
- Create: `client/src/features/auth/RegisterPage.tsx`
- Create: `client/src/app/router.tsx`
- Modify: `client/src/app/AppShell.tsx`
- Modify: `client/src/app/navigation.ts`
- Modify: `client/src/main.tsx`
- Delete: `client/src/App.tsx`
- Delete: `client/src/api.ts`
- Delete: `client/src/types.ts`
- Create: `client/src/features/auth/AuthProvider.test.tsx`
- Create: `client/src/features/auth/routes.test.tsx`
- Create: `client/src/features/auth/RegisterPage.test.tsx`

**Interfaces:**
- Produces: `AuthProvider`, `useAuth()`, `RequireAuth`, `RequireRole`, `/login`, `/register`, and protected application routes.
- Produces: `User` and `Role` types used by navigation and subsequent features.
- Consumes: `ApiClient`, `/auth/register`, `/auth/login`, `/auth/me`, and local storage key `smart-warehouse-token`.

- [ ] **Step 1: Write failing registration and route-guard tests**

```tsx
it('submits public registration without a role field', async () => {
  const register = vi.fn().mockResolvedValue({ id: 4, email: 'new@example.com', role: 'client' })
  render(<RegisterPage register={register} />)
  await userEvent.type(screen.getByLabelText(/email/i), 'new@example.com')
  await userEvent.type(screen.getByLabelText(/^password/i), 'strong-password')
  await userEvent.click(screen.getByRole('button', { name: /create account/i }))
  expect(register).toHaveBeenCalledWith({
    email: 'new@example.com', password: 'strong-password',
  })
})

it('redirects anonymous users from protected catalogue routes', () => {
  renderRouter(['/products'], { user: null })
  expect(screen.getByRole('heading', { name: /sign in/i })).toBeInTheDocument()
})
```

- [ ] **Step 2: Run auth component tests and confirm missing feature modules**

Run: `npm.cmd test -- --run src/features/auth`

Expected: tests fail because auth feature components do not exist.

- [ ] **Step 3: Implement Zod schemas and auth API functions**

```typescript
export const registerSchema = z.object({
  email: z.string().trim().email().transform((value) => value.toLowerCase()),
  password: z.string().min(12).max(128),
}).strict()

export const authApi = {
  register: (input: RegisterInput) => api.request<User>('/auth/register', {
    method: 'POST', body: JSON.stringify(input),
  }),
  login: (input: LoginInput) => api.request<TokenResponse>('/auth/login', {
    method: 'POST', body: JSON.stringify(input),
  }),
  me: () => api.request<User>('/auth/me'),
}
```

The registration type has no `role` member. Map backend `fields` to React Hook Form errors.

- [ ] **Step 4: Implement token lifecycle and current-user loading**

`AuthProvider` initializes from local storage, calls `/auth/me` before rendering protected
children, writes a token only after successful login, and clears token/query cache on logout or
the API client's `401` callback. A `403` leaves both token and user intact.

- [ ] **Step 5: Implement route and action guards**

```tsx
export function RequireRole({ allow, children }: PropsWithChildren<{ allow: Role[] }>) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (!allow.includes(user.role)) return <Navigate to="/forbidden" replace />
  return children
}
```

Declare all protected routes under `AppShell`. Navigation derives from `navigation.ts` role lists.
Do not interpret a frontend guard as proof of permission; feature API calls still handle `403`.

- [ ] **Step 6: Run auth, API-client, type, and build checks**

Run: `npm.cmd test -- --run src/features/auth src/shared/api`

Run: `npm.cmd run typecheck`

Run: `npm.cmd run build`

Expected: all pass; anonymous users see only login/register and every authenticated role reaches its allowed shell.

- [ ] **Step 7: Commit frontend authentication**

```powershell
git add client/src
git commit -m "feat(web): add secure authentication and role-aware routes"
```

### Task 15: Admin Dashboard, User Management, and Audit Pages

**Files:**
- Create: `client/src/features/dashboard/api.ts`
- Create: `client/src/features/dashboard/DashboardPage.tsx`
- Create: `client/src/features/dashboard/DashboardPage.test.tsx`
- Create: `client/src/features/users/types.ts`
- Create: `client/src/features/users/schemas.ts`
- Create: `client/src/features/users/api.ts`
- Create: `client/src/features/users/UsersPage.tsx`
- Create: `client/src/features/users/UserCreateForm.tsx`
- Create: `client/src/features/users/UserActions.tsx`
- Create: `client/src/features/users/UsersPage.test.tsx`
- Create: `client/src/features/audit/types.ts`
- Create: `client/src/features/audit/api.ts`
- Create: `client/src/features/audit/AuditPage.tsx`
- Create: `client/src/features/audit/AuditPage.test.tsx`
- Modify: `client/src/app/router.tsx`
- Modify: `client/src/app/navigation.ts`

**Interfaces:**
- Produces: admin-only `/dashboard`, `/users`, and `/audit` pages.
- Consumes: dashboard stats, paginated users/audit APIs, managed role/status endpoints, TanStack Query, and auth role guards.

- [ ] **Step 1: Write failing dashboard and user-action tests**

```tsx
it('renders real dashboard metrics and loading state', async () => {
  mockApi.get('/dashboard/stats', {
    product_count: 12, total_stock: 420, low_stock_count: 3,
  })
  renderAdminRoute('/dashboard')
  expect(screen.getByText(/loading/i)).toBeInTheDocument()
  expect(await screen.findByText('420')).toBeInTheDocument()
})

it('offers only client and warehouse roles when creating a user', async () => {
  renderAdminRoute('/users')
  const role = await screen.findByLabelText(/role/i)
  expect(within(role).queryByRole('option', { name: /admin/i })).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Run admin-page tests and verify routes/features are missing**

Run: `npm.cmd test -- --run src/features/dashboard src/features/users src/features/audit`

Expected: tests fail because the pages are absent.

- [ ] **Step 3: Implement dashboard query and accessible metric cards**

Use query key `['dashboard', 'stats']`. Display product count, total stock, and low-stock count with
labels that remain understandable without color. Render explicit loading/error states and a retry
action.

- [ ] **Step 4: Implement user list/create/role/status mutations**

Use query key `['users', filters]`. Create form accepts only `client`/`warehouse`. Role and status
actions require confirmation and show server domain messages. Disable admin-target actions based
on response data for UX, while preserving backend handling if a request is still attempted.
Invalidate `['users']` and `['audit']` after a successful mutation.

- [ ] **Step 5: Implement append-only audit browsing**

Display actor, action, target, safe before/after changes, and timestamp formatted with
`Intl.DateTimeFormat`. Provide pagination and action/target filters supported by the API. Do not
render edit/delete controls.

- [ ] **Step 6: Verify admin routes and role denial**

Add route tests showing warehouse/client users are redirected from all three admin routes. Also
mock a backend `403` and assert its message renders while the current session remains active.

- [ ] **Step 7: Run focused tests, typecheck, and build**

Run: `npm.cmd test -- --run src/features/dashboard src/features/users src/features/audit`

Run: `npm.cmd run typecheck`

Run: `npm.cmd run build`

Expected: all pass with no admin option exposed by normal user-management UI.

- [ ] **Step 8: Commit admin frontend features**

```powershell
git add client/src/features/dashboard client/src/features/users client/src/features/audit client/src/app
git commit -m "feat(web): add dashboard and audited user administration"
```

### Task 16: Master-Data and Warehouse Management Pages

**Files:**
- Create: `client/src/features/categories/types.ts`
- Create: `client/src/features/categories/schemas.ts`
- Create: `client/src/features/categories/api.ts`
- Create: `client/src/features/categories/CategoriesPage.tsx`
- Create: `client/src/features/categories/CategoriesPage.test.tsx`
- Create: `client/src/features/suppliers/types.ts`
- Create: `client/src/features/suppliers/schemas.ts`
- Create: `client/src/features/suppliers/api.ts`
- Create: `client/src/features/suppliers/SuppliersPage.tsx`
- Create: `client/src/features/suppliers/SuppliersPage.test.tsx`
- Create: `client/src/features/products/types.ts`
- Create: `client/src/features/products/schemas.ts`
- Create: `client/src/features/products/api.ts`
- Create: `client/src/features/products/ProductsPage.tsx`
- Create: `client/src/features/products/ProductsPage.test.tsx`
- Create: `client/src/features/warehouses/types.ts`
- Create: `client/src/features/warehouses/schemas.ts`
- Create: `client/src/features/warehouses/api.ts`
- Create: `client/src/features/warehouses/WarehousesPage.tsx`
- Create: `client/src/features/warehouses/WarehousesPage.test.tsx`
- Modify: `client/src/app/router.tsx`
- Modify: `client/src/app/navigation.ts`

**Interfaces:**
- Produces: paginated/filterable catalogue and warehouse pages with admin CRUD controls.
- Consumes: approved master-data/warehouse APIs, role-based UX, shared forms/errors/pagination, and TanStack Query invalidation.

- [ ] **Step 1: Write failing role-sensitive CRUD tests**

```tsx
it.each(['warehouse', 'client'] as const)(
  'shows products without mutation controls to %s', async (role) => {
    renderRoleRoute('/products', role)
    expect(await screen.findByText('SKU-001')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /create product/i })).not.toBeInTheDocument()
  },
)

it('validates paired coordinates before warehouse submit', async () => {
  renderRoleRoute('/warehouses', 'admin')
  await openCreateForm()
  await userEvent.type(screen.getByLabelText(/latitude/i), '10.77')
  await userEvent.click(screen.getByRole('button', { name: /save/i }))
  expect(await screen.findByText(/latitude and longitude.*together/i)).toBeInTheDocument()
  expect(mockApi.calls('POST', '/warehouses')).toHaveLength(0)
})
```

- [ ] **Step 2: Run feature tests and verify missing pages**

Run: `npm.cmd test -- --run src/features/categories src/features/suppliers src/features/products src/features/warehouses`

Expected: tests fail because feature pages are absent.

- [ ] **Step 3: Implement per-feature types, Zod schemas, API functions, and query keys**

Keep each feature self-contained. Normalize SKU/warehouse code in UI for immediate feedback but
accept backend normalization as authoritative. Warehouse schema uses a `.superRefine()` check for
paired coordinates and numeric bounds identical to the backend.

- [ ] **Step 4: Implement authenticated read experiences by role**

Admin, warehouse, and client can read products/categories. Admin and warehouse can read suppliers.
All authenticated roles can read warehouses. Every list includes bounded pagination, supported
filters, loading/error/empty states, and local-time timestamp formatting where timestamps appear.

- [ ] **Step 5: Implement admin mutation dialogs/forms**

Admin can create/update/delete all four resources. Map backend field errors to controls and
conflicts to form-level messages. Confirm delete, disable duplicate submission, and invalidate the
resource query plus dependent product lookups after success. Non-admin components never render
mutation controls.

- [ ] **Step 6: Run master-data/warehouse tests, auth-route tests, typecheck, and build**

Run: `npm.cmd test -- --run src/features/categories src/features/suppliers src/features/products src/features/warehouses src/features/auth/routes.test.tsx`

Run: `npm.cmd run typecheck`

Run: `npm.cmd run build`

Expected: all pass for admin CRUD and role-correct read-only experiences.

- [ ] **Step 7: Commit master-data and warehouse frontend**

```powershell
git add client/src/features/categories client/src/features/suppliers client/src/features/products client/src/features/warehouses client/src/app
git commit -m "feat(web): add master-data and warehouse workflows"
```

### Task 17: Stock, Inbound, Outbound, and Transaction-History Pages

**Files:**
- Create: `client/src/features/inventory/types.ts`
- Create: `client/src/features/inventory/schemas.ts`
- Create: `client/src/features/inventory/api.ts`
- Create: `client/src/features/inventory/StockPage.tsx`
- Create: `client/src/features/inventory/InboundPage.tsx`
- Create: `client/src/features/inventory/OutboundPage.tsx`
- Create: `client/src/features/inventory/MovementForm.tsx`
- Create: `client/src/features/inventory/StockPage.test.tsx`
- Create: `client/src/features/inventory/MovementForm.test.tsx`
- Create: `client/src/features/transactions/types.ts`
- Create: `client/src/features/transactions/api.ts`
- Create: `client/src/features/transactions/TransactionsPage.tsx`
- Create: `client/src/features/transactions/TransactionsPage.test.tsx`
- Modify: `client/src/app/router.tsx`
- Modify: `client/src/app/navigation.ts`

**Interfaces:**
- Produces: `/stock` for all authenticated roles and `/inbounds`, `/outbounds`, `/transactions` for admin/warehouse.
- Consumes: product/warehouse queries, inventory movement/history APIs, shared API errors, pagination, and role guards.

- [ ] **Step 1: Write failing movement and read-only client tests**

```tsx
it('submits a positive inbound then refreshes stock and history', async () => {
  renderRoleRoute('/inbounds', 'warehouse')
  await selectWarehouse('HCM-01')
  await selectProduct('SKU-001')
  await userEvent.type(screen.getByLabelText(/quantity/i), '5')
  await userEvent.click(screen.getByRole('button', { name: /record inbound/i }))
  expect(await screen.findByText(/inbound recorded/i)).toBeInTheDocument()
  expect(queryClient.invalidateQueries).toHaveBeenCalledWith({ queryKey: ['stock'] })
  expect(queryClient.invalidateQueries).toHaveBeenCalledWith({ queryKey: ['transactions'] })
})

it('client can see stock but cannot route to movement/history pages', () => {
  renderRoleRoute('/outbounds', 'client')
  expect(screen.getByRole('heading', { name: /forbidden/i })).toBeInTheDocument()
})
```

- [ ] **Step 2: Run inventory frontend tests and verify missing feature failures**

Run: `npm.cmd test -- --run src/features/inventory src/features/transactions`

Expected: tests fail because pages and mutations do not exist.

- [ ] **Step 3: Implement stock and history queries**

Use query keys `['stock', filters]`, `['inbounds', filters]`, `['outbounds', filters]`, and
`['transactions', filters]`. Tables expose product/warehouse labels, quantities, actor, reference,
type, and local timestamp. Each page has bounded pagination and supported filters.

- [ ] **Step 4: Implement validated movement forms**

```typescript
export const movementSchema = z.object({
  warehouse_id: z.coerce.number().int().positive(),
  product_id: z.coerce.number().int().positive(),
  quantity: z.coerce.number().int().positive(),
  reference: z.string().trim().max(120).optional(),
  note: z.string().trim().max(2000).optional(),
}).strict()
```

Show `INSUFFICIENT_STOCK` without replacing it with generic copy. Disable repeated submission.
After success invalidate stock, the relevant movement list, transactions, and dashboard stats.

- [ ] **Step 5: Verify navigation and backend-denial behavior for every role**

Admin and warehouse see movement/history navigation and can submit. Client sees stock only. Mock a
backend `403` for a visible action and assert the explicit error is rendered while auth state stays
active.

- [ ] **Step 6: Run the complete frontend gate**

Run: `npm.cmd test -- --run`

Run: `npm.cmd run typecheck`

Run: `npm.cmd run build`

Expected: all frontend tests, TypeScript, and production build pass.

- [ ] **Step 7: Commit inventory frontend workflows**

```powershell
git add client/src/features/inventory client/src/features/transactions client/src/app
git commit -m "feat(web): add inventory movement and history workflows"
```

---

## Milestone 6 — Runtime Images, E2E, Quality Gates, and Documentation

### Task 18: Secure Seed, Explicit Migration, Production Images, and Runtime Health

**Files:**
- Modify: `app/seed.py`
- Modify: `tests/test_seed.py`
- Create: `tests/postgres/test_seed.py`
- Modify: `Dockerfile`
- Create: `.dockerignore`
- Modify: `client/Dockerfile`
- Create: `client/.dockerignore`
- Create: `client/nginx.conf`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Create: `tests/postgres/test_readiness.py`

**Interfaces:**
- Produces: idempotent environment-driven bootstrap, explicit `migrate` Compose service, non-root runtime images, liveness/readiness healthchecks, and static frontend serving.
- Consumes: typed settings, Alembic head, PostgreSQL 16, frontend production build, and API probes.

- [ ] **Step 1: Write failing secure-seed and readiness integration tests**

```python
# tests/postgres/test_seed.py
def test_seed_is_idempotent_and_never_overwrites_admin_password(postgres_engine, seed_settings):
    run_seed(postgres_engine, seed_settings)
    first_hash = read_admin_hash(postgres_engine, seed_settings.admin_email)
    run_seed(postgres_engine, seed_settings)
    assert read_admin_hash(postgres_engine, seed_settings.admin_email) == first_hash
    assert count_users(postgres_engine, seed_settings.admin_email) == 1

def test_seed_requires_all_privileged_credentials() -> None:
    with pytest.raises(ValueError, match="SEED_ADMIN_PASSWORD"):
        load_seed_settings({"SEED_ADMIN_EMAIL": "admin@example.com"})

# tests/postgres/test_readiness.py
def test_readiness_is_healthy_only_with_database(postgres_client) -> None:
    assert postgres_client.get("/api/v1/health/live").status_code == 200
    assert postgres_client.get("/api/v1/health/ready").status_code == 200
```

- [ ] **Step 2: Run seed/readiness tests against PostgreSQL**

Run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_seed.py tests/postgres/test_readiness.py -q`

Expected: current SQLite-oriented seed test setup or old health contract fails.

- [ ] **Step 3: Refactor seed onto canonical settings and password policy**

Keep seed idempotent and preserve existing hashes. Require every seeded privileged credential from
environment input; normalize email and hash only when creating a missing user. Validate production
passwords through the same minimum policy as internal user creation. Never print credentials or
hashes. Existing demo business rows remain idempotent and use no production secret defaults.

- [ ] **Step 4: Replace the API image with a minimal non-root multi-stage build**

```dockerfile
# Dockerfile
FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml README.md ./
COPY app ./app
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`.dockerignore` excludes `.git`, `.env`, `.venv`, tests, caches, coverage, frontend sources,
worktrees, and local data. The runtime contains the installed wheel and Alembic release assets,
not repository/test/build context.

- [ ] **Step 5: Replace the web image with build-only Node plus non-root static runtime**

```dockerfile
# client/Dockerfile
FROM node:22-alpine AS builder
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginxinc/nginx-unprivileged:alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist /usr/share/nginx/html
EXPOSE 8080
```

The Nginx configuration supports SPA fallback and proxies `/api/` to the API service for Compose.
`client/.dockerignore` excludes `.env`, source test output, `node_modules`, `dist`, coverage, and
Playwright artifacts.

- [ ] **Step 6: Make migration and health ordering explicit in Compose**

Add a one-shot `migrate` service that runs `alembic upgrade head`. `api` depends on PostgreSQL
healthy and migration completed successfully. API healthcheck calls readiness; web waits for the
API healthcheck. Add a manually invoked `seed` profile rather than seeding on every API startup.
No API container runs migrations in its command.

- [ ] **Step 7: Verify images and Compose behavior**

Run: `docker compose build --no-cache api web`

Run: `docker compose up -d db migrate api web`

Run: `docker compose ps`

Expected: migration exits `0`; db/api/web become healthy; API liveness/readiness and web root return `200`.

Inspect both final images and confirm no `.env`, test directory, coverage, `node_modules`, or local
build cache is present. Confirm `docker inspect` reports non-root configured users for API and web.

- [ ] **Step 8: Run seed twice and backend/frontend gates**

Run: `docker compose --profile bootstrap run --rm seed`

Run the same seed command again. Expected: both exit `0`, record counts do not increase, and existing password hashes remain unchanged.

Run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_seed.py tests/postgres/test_readiness.py -q`

Run from `client`: `npm.cmd run build`

- [ ] **Step 9: Commit runtime hardening**

```powershell
git add app/seed.py tests/test_seed.py tests/postgres/test_seed.py tests/postgres/test_readiness.py Dockerfile .dockerignore client/Dockerfile client/.dockerignore client/nginx.conf docker-compose.yml .env.example
git commit -m "build: harden migration and runtime containers"
```

### Task 19: Playwright Critical Paths and Automated Quality Workflow

**Files:**
- Modify: `client/package.json`
- Modify: `client/package-lock.json`
- Create: `client/playwright.config.ts`
- Create: `client/e2e/helpers.ts`
- Create: `client/e2e/auth-client.spec.ts`
- Create: `client/e2e/admin-management.spec.ts`
- Create: `client/e2e/inventory-flow.spec.ts`
- Create: `docker-compose.e2e.yml`
- Create: `.github/workflows/quality.yml`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `npm run e2e` critical-path suite and CI gates for Ruff, pytest/PostgreSQL, migration, Vitest, typecheck, build, and Playwright.
- Consumes: Dockerized full stack, secure test-only bootstrap credentials, and completed UI/API routes.

- [ ] **Step 1: Install Playwright and configure generated-artifact ignores**

Run from `client`:

```powershell
npm.cmd install --save-dev @playwright/test
npx.cmd playwright install chromium
```

Add `playwright-report/`, `test-results/`, trace/video/screenshot output, and coverage to `.gitignore`
and `client/.dockerignore`. Add script `"e2e": "playwright test"`.

- [ ] **Step 2: Add a failing anonymous-registration/client-access E2E**

```typescript
// client/e2e/auth-client.spec.ts
test('anonymous registers as client and receives read-only catalogue access', async ({ page }) => {
  const email = `client-${Date.now()}@example.com`
  await page.goto('/register')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill('strong-password')
  await page.getByRole('button', { name: 'Create account' }).click()
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill('strong-password')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/products/)
  await expect(page.getByRole('link', { name: /inbound/i })).toHaveCount(0)
})
```

- [ ] **Step 3: Configure Playwright against the Docker stack**

```typescript
// client/playwright.config.ts
export default defineConfig({
  testDir: './e2e',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
})
```

`docker-compose.e2e.yml` overrides only disposable credentials/data and ensures migration plus seed
complete before the tests. It does not alter production image contents.

- [ ] **Step 4: Run the first E2E and verify it fails before stack/data setup is complete**

Run: `docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --build`

Run from `client`: `npm.cmd run e2e -- auth-client.spec.ts`

Expected before final E2E wiring: failure identifies the missing bootstrap/order or UI contract rather than silently passing on mocked data.

- [ ] **Step 5: Add admin management and audit critical path**

The spec logs in with the environment-provided seeded admin, creates a uniquely named category,
supplier, product, and warehouse, creates a warehouse operator, changes its status/role within the
allowed range, and confirms corresponding administrative audit rows. It also confirms no admin
role option is available and no password text appears on the audit page.

- [ ] **Step 6: Add warehouse inventory and dashboard critical path**

The spec logs in as the operator created by the admin flow, records inbound quantity `20`, records
outbound quantity `7`, and verifies stock `13` plus one inbound, one outbound, and two stock
transactions. It then logs in as admin and verifies dashboard aggregates reflect the resulting
database state. A client session verifies stock is readable but inbound/outbound/history routes
are inaccessible.

- [ ] **Step 7: Run Playwright critical paths repeatedly against a fresh stack**

Run: `docker compose -f docker-compose.yml -f docker-compose.e2e.yml down -v`

Run: `docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --build`

Run from `client`: `npm.cmd run e2e`

Expected: all three critical-path specs pass. Repeat from a second fresh `down -v` cycle to prove seed/migration/order determinism.

- [ ] **Step 8: Add the CI quality workflow**

`.github/workflows/quality.yml` defines:

1. Backend job with PostgreSQL 16 service, Ruff, Alembic migration test, and all pytest suites.
2. Frontend job with `npm ci`, Vitest, typecheck, and production build.
3. E2E job, dependent on the first two, that builds the Docker stack and runs Chromium critical paths.

Use fixed test-only CI credentials in job environment, never production credentials. Upload
Playwright traces/screenshots only on failure. Do not publish images or deploy from this workflow.

- [ ] **Step 9: Run the complete local quality gate**

Run: `.venv\Scripts\python.exe -m ruff check app tests alembic`

Run: `.venv\Scripts\python.exe -m pytest -q`

Run from `client`: `npm.cmd test -- --run`

Run from `client`: `npm.cmd run typecheck`

Run from `client`: `npm.cmd run build`

Run from `client`: `npm.cmd run e2e`

Expected: every command exits `0`.

- [ ] **Step 10: Commit E2E and quality automation**

```powershell
git add client/package.json client/package-lock.json client/playwright.config.ts client/e2e docker-compose.e2e.yml .github/workflows/quality.yml .gitignore client/.dockerignore
git commit -m "test(e2e): cover Phase 1 critical workflows"
```

### Task 20: Final Documentation, Fresh-Environment Verification, and Phase Closure

**Files:**
- Replace: `README.md`
- Replace: `docs/architecture/phase-1-design.md`
- Create: `docs/api/phase-1-contract.md`
- Create: `docs/operations/phase-1-runbook.md`
- Modify: `PROGRESS.md`
- Modify: `docs/superpowers/plans/2026-09-04-phase-1-production-ready.md` (check completed boxes during execution)

**Interfaces:**
- Produces: one accurate setup entry point, implemented architecture, API/RBAC/error contract, operations runbook, and verified completion record.
- Consumes: final commands, endpoints, environment names, migration revision, image behavior, and quality-gate output from Tasks 1–19.

- [ ] **Step 1: Audit documentation against the delivered application**

Run these searches and resolve every stale statement:

```powershell
rg -n "publicly readable|JWT.*role|router.*SQLAlchemy|geocod|no initial Git commit|In Progress|Next Task" README.md PROGRESS.md docs
rg -n "@(router|application)\.(get|post|put|patch|delete)" app
```

Compare documented endpoints with generated `/openapi.json`, the RBAC matrix test cases, and actual
Compose service names. Do not document an endpoint or command that was not verified.

- [ ] **Step 2: Replace README with the verified quick-start path**

README must include prerequisites; safe `.env` creation; explicit migration; secure bootstrap;
local API/web URLs; liveness/readiness; unit/PostgreSQL/frontend/E2E commands; and links to the
architecture, API contract, and runbook. It must state that anonymous access is register/login only.

- [ ] **Step 3: Update architecture and API documentation**

`docs/architecture/phase-1-design.md` describes the implemented modular monolith and dependency
rules without the old router-owned persistence design. `docs/api/phase-1-contract.md` lists every
route, request/response schema, pagination/filter contract, stable error shape, and final RBAC
matrix. Document stock transactions as the sole inventory business audit and administrative audit
as user-management-only.

- [ ] **Step 4: Write the operations runbook**

`docs/operations/phase-1-runbook.md` contains exact commands for configuration validation,
migration-as-release-step, seed, startup/shutdown, readiness diagnosis, log inspection, rollback to
the previous application image without reversing data migrations, and basic PostgreSQL backup and
restore using `pg_dump`/`pg_restore`. Every destructive restore command must explicitly target a
named disposable/recovery database and warn against using a production target unintentionally.

- [ ] **Step 5: Verify from a fresh disposable environment**

Run: `docker compose -f docker-compose.yml -f docker-compose.e2e.yml down -v`

Run: `docker compose -f docker-compose.yml -f docker-compose.e2e.yml build --no-cache`

Run: `docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d`

Verify migration completion, seed idempotency, API/web health, and all Playwright paths. Record
command names and results in `PROGRESS.md`; do not paste secrets or full environment output.

- [ ] **Step 6: Run every final quality gate once more**

Run: `.venv\Scripts\python.exe -m ruff check app tests alembic`

Run: `.venv\Scripts\python.exe -m pytest -q`

Run from `client`: `npm.cmd test -- --run`

Run from `client`: `npm.cmd run typecheck`

Run from `client`: `npm.cmd run build`

Run from `client`: `npm.cmd run e2e`

Expected: every command exits `0`; no failed or skipped PostgreSQL critical test is accepted.

- [ ] **Step 7: Mark Phase 1 complete only from evidence**

Update `PROGRESS.md` with the migration head, backend test count/result, frontend test result,
production build result, E2E spec result, Docker smoke result, known non-blocking limitations, and
the exact date. Remove obsolete current/next tasks and architectural claims.

- [ ] **Step 8: Commit the final documentation and completion record**

Before the commit, inspect status, staged/unstaged diffs, staged file list, and all Step 6 output.

```powershell
git add README.md PROGRESS.md docs/architecture/phase-1-design.md docs/api/phase-1-contract.md docs/operations/phase-1-runbook.md docs/superpowers/plans/2026-09-04-phase-1-production-ready.md
git commit -m "docs: complete Phase 1 operations and verification guide"
```

- [ ] **Step 9: Report the Phase 1 handoff**

Report verification commands/results, migration head, commit hash/subject, working-tree cleanliness,
local run entry points, bootstrap procedure, and every remaining explicitly excluded Phase 1 item.
Do not push, create a pull request, or publish images unless the user separately requests it.
