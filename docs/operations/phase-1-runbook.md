# Phase 1 Operations Runbook

## Configuration preflight

Create `.env` from `.env.example`, replace every placeholder, and keep the file outside version control. Production mode requires the `postgresql+psycopg` synchronous driver and a unique JWT secret of at least 32 characters. Database and seed values must not be blank.

```powershell
Copy-Item .env.example .env
docker compose config --quiet
```

Treat a failed config check as a release blocker. Do not bypass required variable interpolation with empty values.

## Release sequence

Migration is a one-shot release step. Run it once before replacing or scaling API processes; API startup does not run Alembic itself.

```powershell
docker compose build api web migrate bootstrap
docker compose up -d db
docker compose up migrate
docker compose ps -a
```

Confirm `migrate` exited with code `0`. The current migration head is `20260904_0002` and can be checked with:

```powershell
docker compose run --rm migrate alembic current
```

Migration 0002 preflights collisions in `lower(trim(users.email))`, `upper(trim(products.sku))` and `upper(trim(warehouses.code))` before normalizing rows or applying DDL. A collision blocks the upgrade and reports field names, not row values. Stop for an approved legacy-data reconciliation; do not bypass the check, reset an existing database or delete conflicting business records automatically.

Run the secure idempotent bootstrap only when the configured admin, warehouse, client, and reference data are required:

```powershell
docker compose --profile bootstrap run --rm bootstrap
```

The command requires all six `SEED_*` credentials, validates them before opening a database connection, does not print passwords, creates missing fixed records, and preserves existing credentials and business rows. The three normalized emails must be distinct. If a configured email already belongs to a different role, bootstrap fails and rolls back instead of reassigning the account or replacing its password. Resolve configuration/identity ownership explicitly before retrying.

Start application services after migration:

```powershell
docker compose up -d api web
docker compose ps -a
```

The supported local URLs are web `http://localhost:8080`, API `http://localhost:8000/api/v1`, and OpenAPI UI `http://localhost:8000/docs`.

## Shutdown and restart

Preserve database data during normal shutdown:

```powershell
docker compose down
```

Restart current images and retain the volume:

```powershell
docker compose up -d db migrate api web
```

`docker compose down -v` deletes the named PostgreSQL volume. Use it only for an explicitly disposable environment after checking the rendered project name and volume.

## Health and diagnosis

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health
Invoke-RestMethod http://localhost:8000/api/v1/health/live
Invoke-RestMethod http://localhost:8000/api/v1/health/ready
```

`health/live` checks that the process responds. `health/ready` executes `SELECT 1`; a `503 DATABASE_UNAVAILABLE` means the process is alive but PostgreSQL is unavailable.

Inspect dependency state and one-shot exit codes:

```powershell
docker compose ps -a
docker compose logs --tail 200 db migrate bootstrap api web
docker compose logs --since 10m api
```

For failed readiness, check `db` health first, then `migrate` exit code, then API logs and the effective `DATABASE_URL` source. Never print `.env`, JWT secrets, seed passwords, or full container environments into tickets or progress records.

## Application rollback without schema rollback

Before replacing a known-good local Compose release, identify the generated image names and retain rollback tags:

```powershell
docker compose images
docker image tag smart-warehouse-api:latest smart-warehouse-api:rollback
docker image tag smart-warehouse-web:latest smart-warehouse-web:rollback
```

If the new application release fails but migration `20260904_0002` is compatible with the previous application image, retag and recreate only application services:

```powershell
docker image tag smart-warehouse-api:rollback smart-warehouse-api:latest
docker image tag smart-warehouse-web:rollback smart-warehouse-web:latest
docker compose up -d --no-build --force-recreate api web
Invoke-RestMethod http://localhost:8000/api/v1/health/ready
```

Verify the exact names shown by `docker compose images` before tagging; project names can change generated image names. Do not run `alembic downgrade` as part of an application rollback. Database rollback requires a separately reviewed migration/restore procedure and an approved recovery point.

## PostgreSQL backup

Create the destination directory, write the custom-format dump inside the database container, then copy it out. This avoids sending binary dump data through the PowerShell text pipeline.

```powershell
New-Item -ItemType Directory -Force -Path .\backups | Out-Null
docker compose exec db pg_dump -U smart_warehouse -d smart_warehouse -Fc -f /tmp/smart_warehouse.dump
docker compose cp db:/tmp/smart_warehouse.dump .\backups\smart_warehouse.dump
docker compose exec db rm -f /tmp/smart_warehouse.dump
```

Protect the dump as sensitive operational data and test recovery before relying on it.

## PostgreSQL restore rehearsal

The following commands are destructive only to the explicitly named disposable database `smart_warehouse_recovery`. Never substitute a production database name and never run `dropdb` until the resolved target has been checked.

```powershell
$recoveryDatabase = 'smart_warehouse_recovery'
if ($recoveryDatabase -ne 'smart_warehouse_recovery') { throw 'Unexpected restore target' }
docker compose exec db dropdb -U smart_warehouse --if-exists $recoveryDatabase
docker compose exec db createdb -U smart_warehouse $recoveryDatabase
docker compose cp .\backups\smart_warehouse.dump db:/tmp/smart_warehouse.dump
docker compose exec db pg_restore -U smart_warehouse --no-owner --no-privileges -d $recoveryDatabase /tmp/smart_warehouse.dump
docker compose exec db psql -U smart_warehouse -d $recoveryDatabase -c 'SELECT count(*) FROM users;'
docker compose exec db rm -f /tmp/smart_warehouse.dump
```

Keep the recovery database isolated. Remove it only after the rehearsal evidence is recorded:

```powershell
$recoveryDatabase = 'smart_warehouse_recovery'
if ($recoveryDatabase -ne 'smart_warehouse_recovery') { throw 'Unexpected cleanup target' }
docker compose exec db dropdb -U smart_warehouse --if-exists $recoveryDatabase
```

## Fresh disposable E2E verification

The overlay defaults to project `smart-warehouse-phase1-task19-e2e`, an internal database, disposable volume, automatic migration/bootstrap ordering, and web port `58080`. The procedure below guards the rendered project name before any destructive cleanup; Compose overrides must not silently redirect it to an existing environment. Supply explicit test-only values needed while Compose interpolates the base file:

```powershell
$env:POSTGRES_PASSWORD = 'e2e-postgres-password-2026'
$env:DATABASE_URL = 'postgresql+psycopg://smart_warehouse_e2e:e2e-postgres-password-2026@db:5432/smart_warehouse_e2e'
$env:JWT_SECRET_KEY = 'e2e-only-jwt-secret-key-with-at-least-32-characters'
$env:SEED_ADMIN_EMAIL = 'e2e-admin@example.com'
$env:SEED_ADMIN_PASSWORD = 'e2e-admin-password-2026'
$env:SEED_WAREHOUSE_EMAIL = 'e2e-warehouse@example.com'
$env:SEED_WAREHOUSE_PASSWORD = 'e2e-warehouse-password-2026'
$env:SEED_CLIENT_EMAIL = 'e2e-client@example.com'
$env:SEED_CLIENT_PASSWORD = 'e2e-client-password-2026'

$composeFiles = @('-f', 'docker-compose.yml', '-f', 'docker-compose.e2e.yml')
$rendered = docker compose @composeFiles config --format json | ConvertFrom-Json
if ($rendered.name -ne 'smart-warehouse-phase1-task19-e2e') { throw 'Unexpected E2E project' }

docker compose @composeFiles down -v --remove-orphans
docker compose @composeFiles build --no-cache
docker compose @composeFiles up -d
docker compose @composeFiles ps -a
```

Migration and bootstrap must exit `0`; database and API must be healthy. Verify bootstrap idempotency without exposing credential values:

```powershell
$before = docker compose @composeFiles exec -T db psql -U smart_warehouse_e2e -d smart_warehouse_e2e -Atc "SELECT count(*) FROM users; SELECT md5(string_agg(email || ':' || password_hash, ',' ORDER BY email)) FROM users;"
docker compose @composeFiles run --rm bootstrap
$after = docker compose @composeFiles exec -T db psql -U smart_warehouse_e2e -d smart_warehouse_e2e -Atc "SELECT count(*) FROM users; SELECT md5(string_agg(email || ':' || password_hash, ',' ORDER BY email)) FROM users;"
if (($before -join "`n") -ne ($after -join "`n")) { throw 'Seed changed users or credential hashes' }
```

Run the eight real Playwright scenarios and clean up the exact disposable project:

```powershell
Set-Location client
$env:E2E_BASE_URL = 'http://127.0.0.1:58080'
npm.cmd run e2e
Set-Location ..
docker compose @composeFiles down -v --remove-orphans
docker volume inspect smart-warehouse-phase1-task19-e2e_e2e_postgres_data
```

The final `docker volume inspect` must report that the volume does not exist. Never use this `down -v` sequence with the default production/local Compose project.

These scenarios use the active Vietnamese Figma UI for login/refresh/logout, three-role navigation/guards, 401 cleanup, 403 session retention, product CRUD, warehouse create/read/edit, inbound/outbound/409, stock/history and dashboard. Registration, category/supplier mutations, managed-user administration/audit and warehouse deletion remain explicit real API steps where no approved UI exists. Do not activate the retained legacy router to make E2E assertions pass. Trace, video and screenshots are disabled to avoid storing authentication payloads; diagnostics still require careful handling.

Playwright accepts only loopback web ports `58080` or `58081`. If a separately approved isolated project uses `58081`, match `E2E_WEB_PORT` and `E2E_BASE_URL` and independently validate its exact project/volume identity before adapting any cleanup command. Never target the running development origin or reuse the default project guard for another project.

## Complete quality gate

With disposable PostgreSQL available at port `55432`:

```powershell
docker compose -f docker-compose.test.yml up -d db_test
$env:TEST_DATABASE_URL = 'postgresql+psycopg://smart_warehouse_test:test-only@127.0.0.1:55432/smart_warehouse_test'
.\.venv\Scripts\python.exe -m ruff check app tests alembic
.\.venv\Scripts\python.exe -m pytest -q
Set-Location client
npm.cmd audit --json
npm.cmd run test:all
npm.cmd run typecheck
npm.cmd run build
Set-Location ..
docker compose -f docker-compose.test.yml down -v
```

`test:all` runs both Vitest (legacy capability tests and separate active-Figma API/provider/route tests) and every retained Node-host test. Running `npm.cmd test -- --run` alone omits the host suite and is not the complete frontend gate.

No failed or skipped PostgreSQL critical test is acceptable. After this backend/frontend block passes and the test database is removed, execute the entire **Fresh disposable E2E verification** procedure above, starting with its test-only environment values and project-name guard and ending with its exact `down -v` cleanup. Its isolated stack must be running before `npm.cmd run e2e`; the `db_test` service alone is not an E2E application stack. Remove only the explicitly named disposable test/E2E resources after evidence is captured.
