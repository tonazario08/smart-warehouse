# Smart Warehouse

Smart Warehouse Phase 1 is a PostgreSQL-backed modular monolith with a FastAPI API and a React/Vite web client. It delivers authentication, centralized RBAC, master data, warehouses, atomic inbound/outbound inventory, stock and transaction history, an admin dashboard, user management, and administrative audit history.

Anonymous business access is limited to registration and login. Products, categories, warehouses, stock, inventory history, dashboard, users, and audit data all require an authenticated role. Operational health endpoints remain public for probes.

## Prerequisites

Use Docker Desktop with Compose for the supported integration environment. Local development and quality gates additionally require Python 3.12+, Node.js 20.19+, and npm. Chromium for E2E tests is installed through Playwright.

## Configure the environment

Create the local environment file in PowerShell:

```powershell
Copy-Item .env.example .env
```

Edit `.env` before starting any service. At minimum, set a non-empty `POSTGRES_PASSWORD`, a matching `DATABASE_URL` such as `postgresql+psycopg://smart_warehouse:<password>@db:5432/smart_warehouse`, a unique `JWT_SECRET_KEY` of at least 32 characters, and all six `SEED_*` email/password values. Seed passwords must contain 12 to 128 characters. Do not commit `.env`.

Validate interpolation without starting containers:

```powershell
docker compose config --quiet
```

## Start a fresh local stack

Migration is an explicit release step and completes before the API starts:

```powershell
docker compose up -d db migrate
docker compose --profile bootstrap run --rm bootstrap
docker compose up -d api web
docker compose ps -a
```

The seed command is idempotent. It creates the configured admin, warehouse operator, client, and a small reference dataset only when missing; it never replaces existing credentials or business records.

Open the web UI at `http://localhost:8080`, the API at `http://localhost:8000/api/v1`, and generated OpenAPI documentation at `http://localhost:8000/docs`.

Probe the running service:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health/live
Invoke-RestMethod http://localhost:8000/api/v1/health/ready
```

`health/live` verifies the process. `health/ready` also executes a database query and returns `503` when PostgreSQL is unavailable.

Stop containers while preserving the database volume with `docker compose down`. Use `docker compose down -v` only when intentionally deleting local database data.

## Quality gates

Install backend and frontend dependencies once:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Set-Location client
npm.cmd ci
npx.cmd playwright install chromium
Set-Location ..
```

Run the backend suite against its disposable PostgreSQL service:

```powershell
docker compose -f docker-compose.test.yml up -d db_test
$env:TEST_DATABASE_URL = "postgresql+psycopg://smart_warehouse_test:test-only@127.0.0.1:55432/smart_warehouse_test"
.\.venv\Scripts\python.exe -m ruff check app tests alembic
.\.venv\Scripts\python.exe -m pytest -q
docker compose -f docker-compose.test.yml down -v
```

Run frontend gates:

```powershell
Set-Location client
npm.cmd test -- --run
npm.cmd run typecheck
npm.cmd run build
Set-Location ..
```

The E2E suite uses the isolated project name `smart-warehouse-phase1-task19-e2e`, an internal PostgreSQL port, disposable test credentials/data, and web port `58080`. Follow the exact fresh-stack procedure in the operations runbook before running:

```powershell
Set-Location client
npm.cmd run e2e
Set-Location ..
```

## Documentation

The implemented architecture is documented in [docs/architecture/phase-1-design.md](docs/architecture/phase-1-design.md). The complete endpoint, schema, filter, RBAC, and error contract is in [docs/api/phase-1-contract.md](docs/api/phase-1-contract.md). Release, health, logs, rollback, backup, restore, and fresh verification procedures are in [docs/operations/phase-1-runbook.md](docs/operations/phase-1-runbook.md). Verified completion evidence is recorded in [PROGRESS.md](PROGRESS.md).
