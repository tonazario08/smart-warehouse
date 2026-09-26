# P1-C01 — Complete Phase 1 Production Readiness

## Metadata

- Status: IN_PROGRESS
- Phase: Phase 1
- Plan: docs/superpowers/plans/2026-09-04-phase-1-production-ready.md
- Specification: docs/superpowers/specs/2026-09-04-phase-1-production-ready-design.md
- Depends on: docs/tasks/process/P-001-file-per-task-workflow.md
- Created: 2026-09-26
- Started: 2026-09-26
- Completed: not completed

## Goal

Complete every remaining requirement of the approved Phase 1 production-ready design and implementation plan so the Smart Warehouse basic modular monolith is verified end to end and ready for Phase 2.

## Context

Phase 1 has partial uncommitted implementation but no authoritative completion evidence. The existing Phase 1 plan contains twenty numbered workstreams spanning backend, PostgreSQL, frontend, runtime packaging, E2E automation, CI, and documentation. Under Model A, those workstreams are executed within this single corrective task.

## In Scope

- Audit the current repository against all twenty workstreams in the Phase 1 implementation plan.
- Preserve valid existing implementation and complete every missing backend, database, frontend, runtime, test, CI, and documentation requirement.
- Use test-driven development for new behavior and bug fixes.
- Maintain the approved API, RBAC, transaction, audit, migration, security, and deployment contracts.
- Update the Phase 1 plan checklist only from verified implementation evidence.
- Record all P1-C01 state transitions, progress, verification, review, and completion evidence in this file.

## Out of Scope

- Phase 2 functionality.
- Cloud deployment, image publishing, remote pushes, or pull requests.
- Unrelated refactoring or changes to local-only files and personal documents.
- Rewriting Git history or force operations.

## Acceptance Criteria

- [ ] AC-1 — Core configuration, stable error contracts, pagination, health probes, and PostgreSQL test foundations satisfy the approved Phase 1 contracts.
- [ ] AC-2 — Database migrations, integrity constraints, administrative audit, authentication, authorization, and transaction ownership satisfy the approved design.
- [ ] AC-3 — Backend user, master-data, warehouse, stock, inbound, outbound, transaction-history, and dashboard workflows are complete and covered by focused and PostgreSQL-backed tests.
- [ ] AC-4 — The React client provides the approved authentication, role-aware navigation, dashboard, administration, master-data, warehouse, inventory, movement, and history workflows.
- [ ] AC-5 — Seed, migration, Docker runtime, liveness/readiness, non-root images, and Compose ordering satisfy the production-readiness contract.
- [ ] AC-6 — Ruff, backend tests, frontend tests, type checking, production build, PostgreSQL integration, and Playwright critical paths pass with reproducible evidence.
- [ ] AC-7 — CI quality gates and generated-artifact exclusions cover backend, frontend, migration, and E2E verification without publishing or deployment side effects.
- [ ] AC-8 — README, architecture, API contract, operations runbook, and Phase 1 completion record match the delivered implementation.
- [ ] AC-9 — All twenty plan workstreams are reconciled against the repository and checked complete only where the recorded evidence proves completion.
- [ ] AC-10 — Independent review approves the complete Phase 1 diff with no unresolved Critical or Important finding.

## Verification Commands

### Focused

Run each focused RED and GREEN command required by the active internal workstream, recording the command, expected failure, implementation result, and passing output in this task file.

### Regression

```powershell
.venv\Scripts\python.exe -m pytest -q
Set-Location client
npm.cmd test -- --run
npm.cmd run typecheck
npm.cmd run build
```

### Static and Diff

```powershell
.venv\Scripts\python.exe -m ruff check app tests alembic
git diff --check
git status --short
git diff
git diff --staged
```

### PostgreSQL, Runtime, and E2E

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://smart_warehouse_test:test-only@localhost:55432/smart_warehouse_test"
docker compose -f docker-compose.test.yml up -d db_test
.venv\Scripts\python.exe -m pytest tests/postgres -q
docker compose -f docker-compose.yml -f docker-compose.e2e.yml build --no-cache
docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d
Set-Location client
npm.cmd run e2e
```

## Progress Log

### 2026-09-26 — Bootstrap authorization

- User approved creation of this exact task path as an exception because the authoritative corrective task did not yet exist.
- The existing Phase 1 specification and implementation plan remain the binding design and execution authorities.
- No implementation state transition has occurred yet.

### 2026-09-26 — READY -> IN_PROGRESS

- Dependency `docs/tasks/process/P-001-file-per-task-workflow.md` verified `DONE`.
- Approved Phase 1 specification and the plan authority for `P1-C01` verified.
- Goal, Context, In Scope, Out of Scope, Acceptance Criteria, and Verification Commands are frozen as the execution baseline.
- Execution uses the isolated `phase1-completion` worktree while preserving unrelated changes in the original checkout.
- User requested continuous execution through the Phase 1 plan, subject only to destructive, security-sensitive, external-side-effect, or irreparably ambiguous blockers.

### 2026-09-26 — Preflight plan audit

- All twenty internal workstreams and their shared files/interfaces were reviewed before implementation.
- Sequential ownership was confirmed for shared backend, frontend router/navigation, package, fixture, and documentation files.
- Task 13 contains one internal example/prose conflict; execution follows the explicit `vi.stubGlobal('fetch', ...)` requirement and does not add MSW.
- JWT `sub` will use the string form of the numeric user identifier and will be parsed at the database boundary.
- Destructive Compose cleanup is limited to the named disposable test/E2E projects and never targets production or unnamed data.
- Official SDD helper scripts cannot run because WSL/bash is unavailable; the recovery ledger is maintained manually in the git-ignored SDD workspace.
- The untracked legacy `docs/plans/current-task.md` was intentionally not ported into the worktree and is not used for routing; P-001's authoritative completion evidence remains unchanged.

### 2026-09-26 — Internal Task 1 implementation evidence

- Focused Task 1 verification passed: `.venv\Scripts\python.exe -m pytest tests/unit/test_config.py tests/unit/test_pagination.py tests/test_error_contract.py tests/test_health.py -q` — 40 passed.
- Regression verification passed: `.venv\Scripts\python.exe -m pytest -q` — 67 passed; `.venv\Scripts\python.exe -m ruff check app tests alembic` — all checks passed; `git diff --check` — passed.
- A new RED/GREEN correction rejects a production JWT secret consisting only of whitespace. The focused test failed before the validator fix because no `ValidationError` was raised, and passed after measuring the stripped value's length.
- The detailed Task 1 implementer report is `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-1-implementer-report.md`.

### 2026-09-26 — Internal Task 1 independent-review correction

- Independent review reproduced acceptance of a whitespace-padded known JWT placeholder. The test-first regression case failed before the correction because configuration raised no `ValidationError`.
- Production validation now trims the configured secret once and uses that normalized value for both minimum-length and known-placeholder checks. The regression case passed after the correction.
- Post-fix verification passed: focused Task 1 suite — 41 passed; full pytest suite — 68 passed; Ruff — all checks passed; `git diff --check` — passed.
- Detailed RED/GREEN output and post-review evidence are appended to `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-1-implementer-report.md`.

### 2026-09-26 — Internal Task 1 accepted

- Independent re-review of cumulative diff `5337e86..7aa8a5a` found no remaining Critical, Important, or Minor finding.
- Reviewer verification passed: focused Task 1 suite — 41 passed; Ruff — all checks passed; `git diff --check` — passed.
- Task 1 implementation checkpoints are `06810d2` and `7aa8a5a`. The detailed review record is `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-1-review-report.md`.
- Internal Task 1 is complete; P1-C01 remains `IN_PROGRESS` and advances to internal Task 2.

### 2026-09-26 — Internal Task 2 implementation evidence

- Focused PostgreSQL migration test first failed as expected because `postgres_url` was not yet provided. After adding the disposable service and fixtures, `.venv\Scripts\python.exe -m pytest tests/postgres/test_migrations.py -q` passed — 1 passed against PostgreSQL 16.
- Fail-closed URL check verified with `TEST_DATABASE_URL` naming `warehouse`: pytest stopped at fixture setup with `TEST_DATABASE_URL must name a database ending in _test` before connecting.
- Migration URL precedence verified by setting `DATABASE_URL` to an intentionally invalid, different database while Alembic received the explicit `postgres_url`; migration still downgraded to base, upgraded to head, and matched all 13 expected schema tables.
- Full regression passed: `.venv\Scripts\python.exe -m pytest -q` — 68 passed. `.venv\Scripts\python.exe -m ruff check app tests alembic` — all checks passed.
- The initial Compose invocation exposed a shared default project/network name with pre-existing local containers. The test Compose file now has a dedicated `smart-warehouse-test` project name and starts without orphan warnings.
- Detailed RED/GREEN, implementation, verification, and concern record: `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-2-implementer-report.md`.

### 2026-09-26 — Internal Task 2 accepted

- Independent review of diff `0667bbe..93bff3e` found no Critical, Important, or Minor finding.
- Reviewer diagnostics verified that a missing `TEST_DATABASE_URL` fails closed, the explicit PostgreSQL test URL passes the migration test, Ruff passes, and `git diff --check 0667bbe..93bff3e` passes.
- Internal Task 2 checkpoint is `93bff3e`. The detailed review record is `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-2-review-report.md`.
- Internal Task 2 is complete; P1-C01 remains `IN_PROGRESS` and advances to internal Task 3.

### 2026-09-26 — Internal Task 3 implementation evidence

- Test-first PostgreSQL gate initially failed all 14 migration and constraint cases because the audit table and production checks/indexes were absent. After implementation, the focused gate passed with 14 passed.
- A coordinate regression exposed PostgreSQL `CHECK` semantics accepting an unknown result when one coordinate was `NULL`; the pair check now explicitly requires both values in the ranged branch. The regression went from one failing parameter case to a passing focused gate.
- A migration normalization regression was observed by temporarily removing the three canonicalization updates: upgrade failed when the normalized warehouse check found legacy lowercase/padded code. Restoring `lower(trim(email))`, `upper(trim(sku))`, and `upper(trim(code))` made both migration paths pass and stored the expected canonical values.
- Verification passed: `.venv\Scripts\python.exe -m pytest tests/postgres/test_migrations.py tests/postgres/test_constraints.py -q` — 14 passed; `.venv\Scripts\python.exe -m pytest -q` — 81 passed; `.venv\Scripts\python.exe -m ruff check app tests alembic` — all checks passed; `git diff --check` — passed.
- The focused and full suites emitted only existing FastAPI/Starlette and pytest-asyncio deprecation warnings. No migration or application failure remains in this workstream.
- Detailed RED/GREEN output, changed files, self-review, and migration data note are recorded in `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-3-implementer-report.md`.

### 2026-09-26 — Task 3 review correction evidence

- Independent review reproduced a SQLite downgrade failure: `upgrade head` succeeded, while `downgrade 20260829_0001` raised `NotImplementedError` at direct check-constraint removal.
- Added `tests/test_migrations.py` first and observed that failure. Changed downgrade to remove functional indexes before dropping the warehouse and transaction checks through Alembic batch operations.
- Verification passed: `.venv\Scripts\python.exe -m pytest tests/test_migrations.py -q` — 1 passed; focused PostgreSQL migration/constraint tests — 14 passed; `.venv\Scripts\python.exe -m pytest -q` — 82 passed; `.venv\Scripts\python.exe -m ruff check app tests alembic` — all checks passed; `git diff --check` — passed.
- Full and focused suites emitted only the existing FastAPI/Starlette and pytest-asyncio deprecation warnings. Independent review report was left unchanged.

### 2026-09-26 — Internal Task 3 accepted

- Independent re-review of cumulative diff `b07f076..6752f58` found no remaining Critical, Important, or Minor finding.
- Reviewer verification passed: SQLite migration round-trip — 1 passed; PostgreSQL migration and constraint suite — 14 passed.
- Task 3 implementation checkpoints are `edb9b41` and `6752f58`. The detailed review record is `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-3-review-report.md`.
- Internal Task 3 is complete; P1-C01 remains `IN_PROGRESS` and advances to internal Task 4.

### 2026-09-26 — Internal Task 4 implementation evidence

- Test-first auth/schema and PostgreSQL integration run initially produced the expected RED findings: public registration accepted a supplied role, request schemas did not normalize email or forbid extra fields, and the token helper still required a role claim. The first run showed 8 failures and 3 passes; the disabled-account scenario was then rewritten to seed the real PostgreSQL session directly after its initial fixture probe was invalid.
- Focused auth, PostgreSQL, and error-contract verification passed: `.venv\Scripts\python.exe -m pytest tests/unit/test_auth_schemas.py tests/postgres/test_auth_integration.py tests/test_auth.py tests/test_error_contract.py -q` — 24 passed.
- Full regression passed: `.venv\Scripts\python.exe -m pytest -q` — 90 passed. `.venv\Scripts\python.exe -m ruff check app tests alembic` — all checks passed. `git diff --check` — passed.
- PostgreSQL 16 test database was started with `docker compose -f docker-compose.test.yml up -d db_test`; auth integration tests passed against the disposable `smart_warehouse_test` database.
- Detailed RED/GREEN, boundary, file, self-review, and concern record: `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-4-implementer-report.md`.

### 2026-09-26 — Task 4 verification follow-up

- A test-first expiry regression initially failed because token creation hard-coded 30 minutes instead of honoring `Settings.jwt_expire_minutes`; the helper now uses the configured lifetime, and `.venv\Scripts\python.exe -m pytest tests/postgres/test_auth_integration.py::test_access_token_contains_only_identity_and_lifecycle_claims -q` passed after correction.
- Repeated final verification after this correction: focused auth/PostgreSQL/error suite — 24 passed; full pytest suite — 90 passed; Ruff — all checks passed; `git diff --check` — passed.

### 2026-09-26 — Task 4 review correction evidence

- Independent review identified that the temporary legacy `UserRole` argument to `create_access_token` selected process-wide settings. A test-first regression showed the helper did not reject that argument; a custom-secret case also verifies token signing and decoding use the same explicitly supplied Settings object.
- Removed the legacy role fallback and made `Settings` mandatory. Updated the dashboard, inventory, master-data, and warehouse test callers to pass the default app Settings explicitly.
- Focused regression passed: `.venv\Scripts\python.exe -m pytest tests/unit/test_auth_schemas.py tests/postgres/test_auth_integration.py tests/test_auth.py tests/test_error_contract.py -q` — 25 passed. Full regression passed: `.venv\Scripts\python.exe -m pytest -q` — 91 passed. Ruff and `git diff --check` passed.
- Detailed correction evidence and expanded file list are appended to `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-4-implementer-report.md`; the independent review report was left unchanged.

### 2026-09-26 — Internal Task 4 accepted

- Independent re-review of cumulative diff `501eb6f..eefd763` found no remaining Critical, Important, or Minor finding.
- Reviewer verification passed: focused auth and updated caller suite — 36 passed; Ruff — all checks passed; `git diff --check` — passed.
- Task 4 implementation checkpoints are `3a70150` and `eefd763`. The detailed review record is `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-4-review-report.md`.
- Internal Task 4 is complete; P1-C01 remains `IN_PROGRESS` and advances to internal Task 5.

### 2026-09-26 — Internal Task 5 implementation evidence

- Implemented admin-only user creation, paginated listing, detail, role and active-status updates, plus read-only paginated audit listing and detail. User creation, role changes, and status changes commit with allowlisted audit rows in the same service transaction.
- Focused PostgreSQL/unit verification passed: `.venv\Scripts\python.exe -m pytest tests/unit/test_audit_payload.py tests/postgres/test_users_audit.py tests/postgres/test_auth_integration.py -q` — 35 passed, 2 existing deprecation warnings.
- Rollback was failure-injected by patching `AuditRepository.add` and calling `UserService.create`; an independent PostgreSQL `Session` found neither the attempted user nor a matching audit row. A separate route test confirmed the safe generic 500 response.
- Regression verification passed: `.venv\Scripts\python.exe -m pytest -q` — 120 passed, 2 existing deprecation warnings. `.venv\Scripts\python.exe -m ruff check app tests alembic` — all checks passed. `git diff --check` — passed.
- Audit package import cycle was reproduced by importing `app.audit.service` before implementation. Lazy package exports preserve both existing `AuditLog` import forms; the direct package-export/service import smoke check passed.
- The repository boundary regression first failed because loaded-user `change_role` was missing. Adding repository-owned role/status changes made the test pass while `Session.commit` was patched to fail.
- Ruling: Task 5 trims/lowercases email only and preserves password whitespace. The plan's illustrative global `str_strip_whitespace=True` changed the supplied secret; the test failed before the correction, and Task 4 normalizes only email. Cost if wrong: an operator expecting trimming must communicate the exact supplied password.
- Ruling: make the existing `AuditLog` package exports lazy to resolve the reproduced import cycle while preserving direct class imports. Cost if wrong: an external caller relying on eager module initialization must use the preserved class export.
- Detailed RED/GREEN, transaction evidence, changed files, verification, and self-review are recorded in `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-5-implementer-report.md`.

### 2026-09-26 — Internal Task 5 implementation checkpoint

- Implementation commit: `013093f0088149de63a309ca6d5d812c724dcf0f` (`feat(users): add audited admin account management`), based on accepted Task 4 commit `ba555ce`.
- The worktree was clean immediately after the implementation commit. P1-C01 remains `IN_PROGRESS`; Task 5 awaits independent review and acceptance evidence.

### 2026-09-26 — Internal Task 5 accepted

- Independent review of cumulative diff `ba555ce..0d2f1f3` found no implementation finding. The only Minor evidence discrepancy was corrected from 33 to 35 focused tests, then re-reviewed clean.
- Reviewer verification passed: focused user/audit/auth suite — 35 passed; targeted rollback, authorization, and duplicate-email diagnostics — 9 passed; Ruff and `git diff --check` — passed.
- Task 5 checkpoints are `013093f` and `0d2f1f3`. The detailed review record is `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-5-review-report.md`.
- Internal Task 5 is complete; P1-C01 remains `IN_PROGRESS` and advances to internal Task 6.

### 2026-09-26 — Internal Task 6 implementation evidence

- PostgreSQL RED run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_categories.py tests/unit/test_architecture.py -q` — 14 failed and 8 passed. Failures reproduced public category reads, missing category detail, absent strict schema validation, unstable category errors, accepted indirect cycles, and the existing router/repository boundaries.
- Intermediate GREEN run had 21 passed and one remaining failure: category deletion returned the global `DATABASE_CONFLICT` rather than `CATEGORY_IN_USE`. Mapping category-delete integrity failures in the service to the stable in-use error resolved it.
- Final focused PostgreSQL and architecture verification passed: `.venv\Scripts\python.exe -m pytest tests/postgres/test_categories.py tests/unit/test_architecture.py -q` — 22 passed. Coverage includes authentication, all-role reads, admin-only mutations, pagination/detail, stable reference/conflict/delete errors, direct and multi-level cycles, termination over a pre-existing corrupt cycle, normalized strict names, and repository/router boundaries.
- Full regression passed against the disposable PostgreSQL database: `.venv\Scripts\python.exe -m pytest -q` — 140 passed. Ruff passed: `.venv\Scripts\python.exe -m ruff check app tests alembic` — all checks passed. `git diff --check` passed. Test output contained only the existing Starlette/httpx and pytest-asyncio deprecation warnings.
- The category routes now use `CategoryRepository` and `CategoryService`; missing credentials return the `AUTHENTICATION_REQUIRED` code required by the category contract. Product and supplier routes were moved unchanged into `app/master_data/_legacy_router.py` so `app/master_data/router.py` contains no direct SQL or transaction operations. This shifts the implementation location for their planned Task 7/8 service slices; those tasks should continue from `_legacy_router.py` while retaining the public API.
- Detailed RED/GREEN output, files, verification, self-review, and the route-location note are recorded in `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-6-implementer-report.md`.

### 2026-09-26 — Task 6 review-test correction evidence

- Independent review reported one Minor transparency finding: the architecture test name implied the composed master-data router was clean while inspecting only `router.py`, despite `_legacy_router.py` intentionally containing the deferred product/supplier handlers.
- Renamed the assertion to `test_category_router_module_has_no_sql_or_transaction_operations` and added `test_legacy_router_contains_only_deferred_product_and_supplier_routes`, which constrains the legacy module to the ten planned product/supplier route-handler pairs and fails if a category handler is placed there.
- Regression RED was verified by temporarily adding a category route to `_legacy_router.py`: `.venv\Scripts\python.exe -m pytest tests/unit/test_architecture.py::test_legacy_router_contains_only_deferred_product_and_supplier_routes -q` — 1 failed because `temporary_category_route` appeared outside the allowed handler set. The temporary mutation was removed.
- GREEN verification passed against disposable PostgreSQL: `.venv\Scripts\python.exe -m pytest tests/postgres/test_categories.py tests/unit/test_architecture.py -q` — 23 passed. Full regression: `.venv\Scripts\python.exe -m pytest -q` — 141 passed. Ruff: `.venv\Scripts\python.exe -m ruff check app tests alembic` — all checks passed. `git diff --check` — passed. The only output warnings were the existing Starlette/httpx and pytest-asyncio deprecations.
- The independent review report remains unchanged. This correction changes only architecture tests and this append-only evidence; Task 7/8 handlers remain deferred in `_legacy_router.py`.

### 2026-09-26 — Internal Task 6 accepted

- Independent re-review of cumulative diff `4a92896..57d5d8c` found no remaining Critical, Important, or Minor finding.
- Reviewer verification passed: focused PostgreSQL category and architecture suite — 23 passed; `git diff --check` — passed. The legacy allowlist now defers only the explicit supplier/product Task 7/8 surface.
- Task 6 implementation checkpoints are `01755bb` and `57d5d8c`. The detailed review record is `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-6-review-report.md`.
- Internal Task 6 is complete; P1-C01 remains `IN_PROGRESS` and advances to internal Task 7.

### 2026-09-26 — Internal Task 7 implementation evidence

- PostgreSQL RED run: `.venv\Scripts\python.exe -m pytest tests/postgres/test_suppliers.py tests/unit/test_architecture.py -q` — 15 failed and 8 passed. Failures exposed unnormalized supplier values, permissive request schemas, absent search, unstable domain errors, referenced-supplier deletion behavior, and supplier routes still present in `_legacy_router.py`.
- Delete regression investigation showed a successful delete also cleared the persisted product's nullable `supplier_id`; SQLAlchemy's relationship handling nulled the foreign key before PostgreSQL `RESTRICT` could reject the delete. A failing preservation assertion confirmed the behavior. `SupplierRepository.has_products()` and a service-level guard now return `SUPPLIER_IN_USE` before ORM deletion.
- Focused PostgreSQL and architecture verification passed: `.venv\Scripts\python.exe -m pytest tests/postgres/test_suppliers.py tests/postgres/test_categories.py tests/unit/test_architecture.py -q` — 49 passed.
- Full regression passed against disposable PostgreSQL: `.venv\Scripts\python.exe -m pytest -q` — 166 passed. `.venv\Scripts\python.exe -m ruff check app tests alembic` — all checks passed. `git diff --check` — passed.
- Test output contained only the existing Starlette/httpx and pytest-asyncio deprecation warnings.
- Implementation checkpoint: `b5c695edeb80996799da7e119e0d627be2123dc0` (`refactor(suppliers): add validated domain service`), based on accepted Task 6 checkpoint `57d5d8c`.
- The detailed RED/GREEN, RBAC/filter/error/architecture coverage, verification, changed-file list, and self-review are recorded in `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-7-implementer-report.md`. Task 7 awaits independent review; P1-C01 remains `IN_PROGRESS`.

### 2026-09-27 — Task 7 architecture guard review correction

- Independent review identified a Minor regression-guard gap: the master-data router architecture test did not detect direct `Session.get`, query, persistence, or transaction calls, and its name described categories only.
- Renamed the assertion to cover the master-data router and added AST detection for direct session/database receiver calls to `get`, `execute`, `scalars`, `scalar`, `query`, `add`, `delete`, `flush`, `refresh`, `commit`, and `rollback`. Service delegation remains unflagged because the receiver is a service-factory call rather than a direct database receiver.
- Mutation RED was observed by temporarily adding `session.get(Supplier, supplier_id)` to `get_supplier`: `.venv\Scripts\python.exe -m pytest tests/unit/test_architecture.py::test_master_data_router_module_has_no_sql_or_transaction_operations -q` — failed with the detected `session.get()` call. The temporary mutation was removed.
- Post-fix focused PostgreSQL supplier/category and architecture verification passed — 49 passed. Full regression passed — 166 passed. Ruff and `git diff --check` passed; only existing deprecation warnings were emitted.
- The Task 7 review report remains unchanged. This correction does not alter supplier or product behavior; P1-C01 remains `IN_PROGRESS`.

### 2026-09-27 — Internal Task 7 accepted

- Independent re-review of cumulative diff `4d8f22e..6212d77` found no remaining Critical, Important, or Minor finding.
- Reviewer verification passed: focused PostgreSQL supplier/category and architecture suite — 49 passed. The architecture guard detects direct session/database calls while allowing service delegation, and product Task 8 handlers remain unchanged.
- Task 7 checkpoints are `b5c695e`, `235d4ee`, and `6212d77`. The detailed review record is `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-7-review-report.md`.
- Internal Task 7 is complete; P1-C01 remains `IN_PROGRESS` and advances to internal Task 8.

### 2026-09-27 — Internal Task 8 implementation evidence

- PostgreSQL RED run reproduced public product reads, raw SKU handling, permissive create/update schemas, missing filter/reference/domain-error behavior, update conflict behavior, and the remaining legacy router. After correcting test setup for a required warehouse address and the `stocks` table name, the product/architecture RED run reported 12 failed and 12 passed for the expected missing behavior.
- Product and architecture GREEN verification passed: `.venv\Scripts\python.exe -m pytest tests/postgres/test_products.py tests/unit/test_architecture.py -q` — 24 passed.
- Focused all-master-data and architecture verification passed: `.venv\Scripts\python.exe -m pytest tests/postgres/test_categories.py tests/postgres/test_suppliers.py tests/postgres/test_products.py tests/unit/test_architecture.py -q` — 70 passed.
- Full regression passed against the disposable PostgreSQL database: `.venv\Scripts\python.exe -m pytest -q` — 184 passed. Ruff passed: `.venv\Scripts\python.exe -m ruff check app tests alembic` — all checks passed. `git diff --check` passed.
- Verification emitted only the existing Starlette/httpx and pytest-asyncio deprecation warnings. An overlapping test attempt against the same disposable DB was discarded; final focused and full runs were executed sequentially. A stale-data-sensitive test assertion was adjusted to check product inclusion rather than assume an empty table, then the sequential final runs passed.
- Product routes now use `ProductRepository` and `ProductService`; the composed master-data router no longer includes `_legacy_router.py`, which has been deleted. Product delete checks stock, inbound, outbound, transaction, and purchase-request references before ORM deletion to preserve all dependent rows.
- Detailed RED/GREEN evidence, RBAC/filter/reference/delete/architecture coverage, changed files, verification, and self-review are recorded in `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-8-implementer-report.md`.

## Verification Evidence

### Focused

- Result: PENDING

### Regression

- Result: PENDING

### Static and Diff

- Result: PENDING

### PostgreSQL, Runtime, and E2E

- Result: PENDING

## Review Result

- Result: PENDING
- Findings: independent review not started

## Completion Evidence

- Final status: not completed
