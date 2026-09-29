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

### 2026-09-27 — Task 8 review coverage correction

- Independent review found the committed product delete-preservation test covered only `stocks`, while the repository guard also checks `inbounds`, `outbounds`, `transactions`, and `purchase_requests`.
- Replaced the stock-only case with parameterized PostgreSQL cases for all five reference tables. Each case directly verifies `ProductRepository.has_references`, attempts API deletion, and confirms both the product and the matching reference row remain persisted with `PRODUCT_IN_USE`.
- The transaction case creates a valid inbound movement link and satisfies the transaction type/link database constraint; its movement belongs to a companion product so the transaction product reference is isolated for mutation verification.
- Mutation RED was observed separately for every reference check by changing that check's product predicate to an impossible ID. Each corresponding parameter case failed at the repository assertion. All temporary mutations were restored; no production behavior changed. The five restored cases passed.
- Focused all-master-data and architecture verification passed: `.venv\Scripts\python.exe -m pytest tests/postgres/test_categories.py tests/postgres/test_suppliers.py tests/postgres/test_products.py tests/unit/test_architecture.py -q` — 74 passed. Full regression passed: `.venv\Scripts\python.exe -m pytest -q` — 188 passed. Ruff and `git diff --check` passed. Only the existing Starlette/httpx and pytest-asyncio deprecation warnings were emitted.

### 2026-09-27 — Internal Task 8 accepted

- Independent re-review of cumulative diff `31670ad..c8505d1` found no remaining Critical, Important, or Minor finding.
- Reviewer verification passed: focused PostgreSQL product suite — 25 passed. All five reference-table cases verify the repository guard, `PRODUCT_IN_USE`, and persistence of both product and referencing row after rejection.
- Task 8 checkpoints are `536ed2f` and `c8505d1`. The detailed review record is `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-8-review-report.md`.
- Internal Task 8 is complete; P1-C01 remains `IN_PROGRESS` and advances to internal Task 9.

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

## Internal Task 9 Evidence (append-only)

### 2026-09-27 — Internal Task 9 implementation and verification

- Confirmed P1-C01's dependency `docs/tasks/process/P-001-file-per-task-workflow.md` is `DONE`, Task 8 is accepted at HEAD `b2de738`, and the approved plan/specification plus `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-9-brief.md` authorize this scope. The P1-C01 baseline and overall `IN_PROGRESS` state remain unchanged.
- PostgreSQL RED: `.venv\Scripts\python.exe -m pytest tests/postgres/test_warehouses.py -q` — 22 failed and 7 passed. The failures reproduced missing paginated reads/delete, coordinate validation, strict/normalized schemas, stable errors, search, and protected-delete behavior.
- Mutation evidence: a temporary direct `session.commit()` caused `test_warehouse_router_module_has_no_sql_or_transaction_operations` to fail. Temporarily disabling all six `WarehouseRepository.has_references` predicates caused the six isolated parameter cases to fail at their direct repository assertion. Restored every mutation; all six API cases then passed and verified `WAREHOUSE_IN_USE` plus persistence of the warehouse and reference row.
- Focused PostgreSQL/constraint/architecture/schema verification passed: `.venv\Scripts\python.exe -m pytest tests/postgres/test_warehouses.py tests/postgres/test_constraints.py tests/unit/test_architecture.py tests/test_warehouses.py -q` — 54 passed.
- Sequential full regression passed against the disposable PostgreSQL database: `.venv\Scripts\python.exe -m pytest -q` — 225 passed. Existing Starlette/httpx and pytest-asyncio deprecation warnings were emitted; no test failed.
- Static and diff verification passed: `.venv\Scripts\python.exe -m ruff check app tests alembic` — all checks passed; `git diff --check` — passed.
- Detailed RED/GREEN and self-review evidence is in the ignored report `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-9-implementer-report.md`. Task 9 changes await checkpoint commit and independent review; P1-C01 remains `IN_PROGRESS`.
- Mutation specificity follow-up: after isolating the transaction fixture's linked inbound in a companion warehouse, each of the six predicates was independently changed to an impossible ID. Its matching reference case failed at `WarehouseRepository.has_references`; each mutation was restored, followed by a passing full focused gate.

### 2026-09-27 — Internal Task 9 accepted

- Independent review of diff `b2de738..cedfcad` found no Critical, Important, or Minor finding.
- Reviewer verification passed: focused PostgreSQL warehouse, constraint, architecture, and schema suite — 54 passed.
- Task 9 checkpoint is `cedfcad`. The detailed review record is `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-9-review-report.md`.
- Internal Task 9 is complete; P1-C01 remains `IN_PROGRESS` and advances to internal Task 10.

## Internal Task 10 Evidence (append-only)

### 2026-09-27 — Internal Task 10 implementation and verification

- Confirmed P1-C01's dependency `docs/tasks/process/P-001-file-per-task-workflow.md` is `DONE`, Task 9 is accepted at HEAD `58ada34`, and the approved Task 10 plan/specification plus `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-10-brief.md` authorize this scope. The P1-C01 baseline and overall `IN_PROGRESS` state remain unchanged.
- PostgreSQL RED: `.venv\Scripts\python.exe -m pytest tests/postgres/test_inventory_reads.py -q` — 20 failed and 2 warnings. Failures reproduced the raw stock/transaction arrays, missing inbound/outbound list/detail routes, missing stock detail, absent pagination/filter validation, resource-specific 404 errors, and incorrect client access to history.
- Architecture mutation RED: temporarily adding `session.scalar(select(Stock))` to `list_stock` made `test_inventory_read_handlers_delegate_queries_and_do_not_manage_transactions` fail; adding `self.repository.session.commit()` to the inventory read service made `test_inventory_service_does_not_manage_read_transactions` fail. Both temporary mutations were restored.
- Final focused verification against the disposable PostgreSQL database: `.venv\Scripts\python.exe -m pytest tests/postgres/test_inventory_reads.py tests/unit/test_architecture.py tests/test_inventory.py -q` — 31 passed. Coverage includes bounded pagination and filter/count parity for all four resources, timestamp/id ordering, all detail routes and not-found codes, strict filters/responses, anonymous and client RBAC, read architecture boundaries, and preserved SQLite write behavior.
- Final full regression against the disposable PostgreSQL database: `.venv\Scripts\python.exe -m pytest -q` — 249 passed. Output contained only the existing Starlette/httpx and pytest-asyncio deprecation warnings.
- Static verification: `.venv\Scripts\python.exe -m ruff check app tests alembic` — all checks passed. `git diff --check` — PASS.
- Added explicit inventory read repository and service methods; exposed paginated stock, inbound, outbound, and transaction reads with stable ordering, strict filters, narrow response schemas, resource-specific detail errors, and `INVENTORY_HISTORY_READ`. Existing inbound/outbound write handlers remain unchanged.
- Detailed RED/GREEN evidence, changed files, self-review, and concerns are recorded in `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-10-implementer-report.md`. Task 10 changes await checkpoint commit and independent review; P1-C01 remains `IN_PROGRESS`.

### 2026-09-27 — Preserve movement write response contract

- Self-review found that initially reusing the expanded movement-read schema for POST responses added `created_by_id` and `created_at` to Task 11 write responses. Added an assertion for the existing inbound POST response shape and observed it fail with those two extra fields.
- Split the strict `InventoryMovementReadResponse` from the existing `InventoryMovementResponse`; all inbound/outbound read routes use the former and POST routes retain the latter. The regression test then passed.
- Re-ran the final focused gate — 31 passed — and full PostgreSQL-backed suite — 249 passed. Ruff and `git diff --check` passed. These final serial results supersede the earlier verification runs.

### 2026-09-27 — Internal Task 10 accepted

- Independent review of diff `58ada34..089f213` found no Critical, Important, or Minor finding.
- Reviewer verification passed serially: PostgreSQL inventory reads — 21 passed; architecture and preserved write-contract checks — 10 passed; `git diff --check` — passed.
- Task 10 checkpoint is `089f213`. The detailed review record is `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-10-review-report.md`.
- Internal Task 10 is complete; P1-C01 remains `IN_PROGRESS` and advances to internal Task 11.

## Internal Task 11 Evidence (append-only)

### 2026-09-27 — Internal Task 11 start

- Confirmed dependency `docs/tasks/process/P-001-file-per-task-workflow.md` is `DONE`, Task 10 is accepted at HEAD `2a1aa4981064345b80e02c8b5cc9c1f1d4dcd751`, and the approved Phase 1 plan/specification plus `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-11-brief.md` authorize this scope. The P1-C01 baseline and overall `IN_PROGRESS` state remain unchanged.
- Frozen Task 11 scope: move inventory write transaction ownership into `InventoryService`, implement safe existing-row locking and concurrent first-stock insertion, preserve the Task 10 POST response contract and RBAC, and add PostgreSQL atomicity, concurrency, and architecture coverage. Verification will use the exact Task 11 gates, run serially against the disposable PostgreSQL database, including ten separate concurrency-suite invocations.
- Implementation has not begun; PostgreSQL RED evidence is pending.

### 2026-09-27 — Internal Task 11 implementation and verification

- PostgreSQL RED: `.venv\Scripts\python.exe -m pytest tests/postgres/test_inventory_transactions.py tests/postgres/test_inventory_concurrency.py -q` — 5 failed, 1 passed. Expected failures showed `InventoryService.create_inbound` and `create_outbound` were missing; the controlled lock test could not reach a row-lock query. Architecture RED — 2 failed — reproduced direct router persistence and missing write-service transaction methods.
- Implemented PostgreSQL `INSERT ... ON CONFLICT DO NOTHING ... RETURNING`, stock row locking, append-only movement and linked stock-transaction writes in the repository; the service now validates references, commits each successful operation once, and rolls back any error. POST routes delegate to those service methods and retain the Task 10 response schema and `INVENTORY_WRITE` authorization.
- Focused PostgreSQL atomicity/concurrency, inventory-read, architecture, and schema gate passed serially: `.venv\Scripts\python.exe -m pytest tests/postgres/test_inventory_reads.py tests/postgres/test_inventory_transactions.py tests/postgres/test_inventory_concurrency.py tests/unit/test_architecture.py tests/test_inventory.py -q` — 39 passed.
- Concurrency repeat gate passed: ten separate serial invocations of `.venv\Scripts\python.exe -m pytest tests/postgres/test_inventory_concurrency.py -q`; each invocation passed all three cases. The controlled lock test confirmed PostgreSQL reported a blocking session while the outbound waited, then passed after the inbound transaction committed.
- Mutation checks were restored before final verification: omitting `FOR UPDATE` made the controlled waiter fail to observe a lock; omitting `ON CONFLICT DO NOTHING` reproduced `uq_stocks_warehouse_product`; omitting outbound rollback left the decremented quantity after simulated transaction-link persistence failure; omitting `inbound_id` violated `ck_transactions_exactly_one_movement`. Assertions cover competing outbound quantity and movement counts.
- Full backend regression passed serially against the disposable PostgreSQL database: `.venv\Scripts\python.exe -m pytest -q` — 257 passed. Ruff passed: `.venv\Scripts\python.exe -m ruff check app tests alembic` — all checks passed. `git diff --check` — passed. The suites emitted the existing Starlette/httpx and pytest-asyncio deprecation warnings only.
- Detailed evidence, changed files, self-review, and concerns are recorded in the ignored `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-11-implementer-report.md`. Task 11 awaits checkpoint commit and independent review; P1-C01 remains `IN_PROGRESS`.

### 2026-09-27 — Internal Task 11 implementation checkpoint

- Implementation checkpoint committed as `0a96c1762ee34fb33634e25c079a07e2695556e3` (`fix(inventory): make stock movements concurrency-safe`). The working tree was clean immediately after the commit.
- Verification evidence above applies to this checkpoint. Task 11 awaits independent review; P1-C01 remains `IN_PROGRESS`.

### 2026-09-27 — Task 11 review correction: exact transaction-call counts

- Independent review found the architecture guard used a set, which could not detect duplicate `commit()` calls. Replaced set membership with per-method counts requiring exactly one `commit()` and one `rollback()` in both `create_inbound` and `create_outbound`.
- RED mutation: temporarily added a second inbound `commit()` and ran `.venv\Scripts\python.exe -m pytest tests/unit/test_architecture.py::test_inventory_write_transactions_are_owned_by_write_service_methods -q`; it failed with observed commit count 2 versus required count 1. Removed the temporary service mutation.
- Post-restore isolated architecture verification passed: `.venv\Scripts\python.exe -m pytest tests/unit/test_architecture.py -q` — 9 passed. `.venv\Scripts\python.exe -m ruff check app tests alembic` — all checks passed; `git diff --check` — passed.
- The requested focused PostgreSQL inventory gate and full pytest regression could not complete because Docker Desktop was unavailable (engine named-pipe missing; localhost port 55432 refused connections). Two stalled pytest processes were stopped after confirming the disposable database was unreachable. Native PostgreSQL on port 5432 rejected the disposable test credentials, and was not used. These PostgreSQL-dependent gates are `NOT VERIFIED` for this correction; concurrency repeats were not rerun because inventory behavior did not change.
- This correction changes only the architecture test and this append-only evidence. The Task 11 implementation and P1-C01 remain pending independent review; no completion status is claimed.

### 2026-09-27 — Exact-count guard verification follow-up

- Confirmed the strengthened assertions execute inside the loop for each write method. Separate temporary duplicate-commit mutations in `create_inbound` and `create_outbound` each failed with observed count 2 versus required count 1; both service mutations were restored.
- Final isolated architecture suite passed after restoration: `.venv\Scripts\python.exe -m pytest tests/unit/test_architecture.py -q` — 9 passed. Ruff and `git diff --check` passed after the final test edit.
- Clarification: the focused PostgreSQL invocation stalled against unavailable Docker-backed PostgreSQL and was stopped after process and port checks. Full `.venv\Scripts\python.exe -m pytest -q` was not run because its PostgreSQL fixtures require that same unavailable endpoint. Both PostgreSQL-dependent gates remain `NOT VERIFIED`; no concurrency repeat was run because inventory behavior was unchanged.

### 2026-09-27 — Task 11 review correction PostgreSQL 18 recovery verification

- Reconnected to the restored disposable `smart_warehouse_test` endpoint at `127.0.0.1:55432`; server reported PostgreSQL 18.3. The temporary database was initially empty, so applied the repository migrations to that named `_test` database. The fresh cluster defaulted to `Asia/Saigon`; set only this disposable database's timezone to UTC to match the inventory timestamp contract.
- Re-ran the focused gate serially after database setup: `.venv\Scripts\python.exe -m pytest tests/postgres/test_inventory_reads.py tests/postgres/test_inventory_transactions.py tests/postgres/test_inventory_concurrency.py tests/unit/test_architecture.py tests/test_inventory.py -q` — 39 passed, with the existing Starlette/httpx and pytest-asyncio warnings.
- Full backend suite passed serially: `.venv\Scripts\python.exe -m pytest -q` — 257 passed, with the same existing warnings. `.venv\Scripts\python.exe -m ruff check app tests alembic` and `git diff --check` both passed.
- This PostgreSQL 18 recovery verification supplements and does not replace the earlier PostgreSQL 16 Task 11 implementation evidence. No concurrency repeat was run because the review correction changes only the architecture guard. P1-C01 remains `IN_PROGRESS` pending independent review disposition.

### 2026-09-27 — Internal Task 11 accepted

- Independent re-review of cumulative diff `2a1aa49..b1e2331` found no remaining Critical, Important, or Minor finding.
- Reviewer verification passed: architecture suite — 9 passed; Ruff and `git diff --check` — passed. Original PostgreSQL 16 implementation evidence and ten concurrency repetitions remain authoritative; PostgreSQL 18 recovery verification passed focused 39 and full 257 tests for the test-only correction.
- Task 11 checkpoints are `0a96c17`, `9785fe9`, `de4f99a`, and `b1e2331`. The detailed review record is `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-11-review-report.md`.
- Internal Task 11 is complete; P1-C01 remains `IN_PROGRESS` and advances to internal Task 12.

## Internal Task 12 Evidence (append-only)

### 2026-09-27 — Internal Task 12 start

- Confirmed dependency `docs/tasks/process/P-001-file-per-task-workflow.md` is `DONE`, Task 11 is accepted at HEAD `e74799fe10b50615a80349d43089b51f15864994`, and the approved Phase 1 plan/specification plus `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-12-brief.md` authorize this scope. P1-C01 remains `IN_PROGRESS`.
- Frozen Task 12 scope: implement single-snapshot PostgreSQL dashboard aggregates behind repository/service layers; reconcile dashboard and centralized permissions; cover every Phase 1 route/action from Tasks 4–11 with valid success prerequisites and denied-role/anonymous outcomes; extend AST architecture guards across all routers and mutation-check them; retain only database-independent dashboard coverage in `tests/test_dashboard.py`.
- Verification: run dashboard/RBAC/architecture gate, full backend pytest, Ruff, and diff checks. Run PostgreSQL-dependent suites serially against only the disposable `smart_warehouse_test` database at `127.0.0.1:55432`; the available migrated cluster is PostgreSQL 18 with database timezone UTC. Do not report PostgreSQL 16 for Task 12.
- Test-first implementation has not begun; RED evidence is pending.

### 2026-09-27 — Internal Task 12 implementation and verification

- Dashboard RED: the first focused collection stopped at the expected `ModuleNotFoundError` for missing `app.dashboard.repository`. Implemented a repository query combining product count, zero-fallback stock sum, and low-stock count in one `SELECT`, a read-only service delegate, and the admin-only router delegation. PostgreSQL coverage asserts exact aggregates, empty-database zero values, and exactly one executed dashboard statement.
- Permission-map RED: the exact Phase 1 permission-map assertion failed on the unused `PRODUCT_READ` permission, which duplicated catalogue access without protecting any route. Removed that unused alias; the centralized mapping now exactly covers catalogue, product write, supplier, warehouse, inventory, dashboard, user-management, and audit capabilities.
- The route/action matrix covers product, category, supplier, warehouse, stock, inbound, outbound, transaction, dashboard, user, audit, and current-user list/detail/create/update/delete/movement actions as applicable. Each allowed role receives the actual success status using valid records and payloads; denied roles receive 403. Anonymous 401s, public register/login, forbidden admin assignment, client inventory/history denial, warehouse master-data denial, and dashboard/user/audit restrictions are covered. Existing Task 5 PostgreSQL tests continue to verify self and other-admin role/status protection.
- The global AST guard parses every `app/**/router.py`, rejects all SQLAlchemy imports and direct session/database operations, and preserves repository no-commit and Task 11 transaction-ownership guards. To satisfy the global no-SQLAlchemy-import contract, removed ORM-only `Session` annotations from auth, audit, dashboard, inventory, master-data, users, and warehouse routers; FastAPI dependency wiring is unchanged. This required touching those seven router files beyond the initially named Task 12 router because each had imported `Session` only for typing.
- Mutation checks: inserting `from sqlalchemy import select` into dashboard router, `session.execute(None)` into warehouse router, `session.add(None)` into users router, and `session.commit()` into audit router each made the global architecture test fail at the expected violation. The synthetic mutation test also checks all four patterns across separate router paths. Every temporary source mutation was removed before final verification.
- PostgreSQL environment verified as server version 18.3, database `smart_warehouse_test` on `127.0.0.1:55432`, timezone `UTC`. This is the migrated disposable test cluster; no PostgreSQL 16 result is claimed for Task 12.
- Focused command passed serially: `.venv\Scripts\python.exe -m pytest tests/postgres/test_dashboard.py tests/postgres/test_rbac_matrix.py tests/unit/test_architecture.py -q` — 55 passed. Full backend regression passed serially: `.venv\Scripts\python.exe -m pytest -q` — 303 passed. Ruff passed: `.venv\Scripts\python.exe -m ruff check app tests alembic` — all checks passed. `git diff --check` — passed. Both pytest runs emitted only the existing Starlette/httpx and pytest-asyncio deprecation warnings.
- Detailed RED/GREEN, coverage inventory, mutation outputs, exact verification, changed files, self-review, and concerns are recorded in ignored `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-12-implementer-report.md`. Task 12 awaits checkpoint commit and independent review; P1-C01 remains `IN_PROGRESS`.

### 2026-09-27 — Internal Task 12 implementation checkpoint

- Task 12 implementation checkpoint committed as `6b891afe4a404eedbbf33c79fb289ba2b798e178` (`test(rbac): enforce the complete Phase 1 permission matrix`). The worktree was clean immediately after the commit.
- Task 12 awaits independent review; P1-C01 remains `IN_PROGRESS`.

### 2026-09-27 — Task 12 independent-review correction

- Review found two coverage gaps: router database calls through local aliases could evade the global AST guard, and denied mutation matrix cases did not assert persisted state remained unchanged. Added alias propagation through chained/local assignments and database/session attributes, including reassignment invalidation; synthetic regressions exercise execute, add, commit, and rollback aliases across dashboard, inventory, and users router-shaped sources. The alias regression was run first and failed before the guard was extended.
- Isolated every route/action case by role. For each denied mutation action, the test snapshots all relevant mapped rows before the request and compares them afterward through a new SQLAlchemy session. Allowed-role cases still perform real mutations with valid payloads and prerequisites. The independent review report was not modified.
- The disposable test database remains `smart_warehouse_test` at `127.0.0.1:55432`, PostgreSQL 18.3 with timezone UTC. No PostgreSQL 16 result is claimed for this correction.
- Focused dashboard/RBAC/architecture gate passed serially: `.venv\Scripts\python.exe -m pytest tests/postgres/test_dashboard.py tests/postgres/test_rbac_matrix.py tests/unit/test_architecture.py -q` — 135 passed. Full backend suite passed serially: `.venv\Scripts\python.exe -m pytest -q` — 383 passed. Ruff passed: `.venv\Scripts\python.exe -m ruff check app tests alembic` — all checks passed. `git diff --check` — passed. Pytest emitted only the existing Starlette/httpx and pytest-asyncio deprecation warnings.
- Test-only correction committed as `60a552cc6d6faa0431b5a42f71a85789c267a500` (`test(rbac): verify denials preserve database state`). Task 12 remains awaiting independent re-review; P1-C01 remains `IN_PROGRESS`.

### 2026-09-28 — Task 12 connection-call boundary correction

- Re-review found the router AST guard did not propagate session/database taint through connection-returning calls. Added taint propagation for known database connection-producing methods (`connection`, `connect`, `raw_connection`, `cursor`, and `execution_options`) and included `exec_driver_sql` among forbidden database operations.
- Test-first evidence: the new synthetic test for `session.connection().execute(...)` failed before the guard change. Regressions now cover chained `session.connection().execute(...)`, chained `exec_driver_sql(...)`, local/chained connection aliases, and `engine.connect()` in dashboard, inventory, users, and warehouse router-shaped sources. Reassignment to a factory-created client and untainted adapter/factory calls remain allowed.
- Verification used the disposable `smart_warehouse_test` endpoint at `127.0.0.1:55432`, PostgreSQL 18.3, timezone UTC; no PostgreSQL 16 result is claimed. The focused dashboard/RBAC/architecture gate passed serially — 137 passed. Full pytest passed serially — 385 passed. Ruff and `git diff --check` passed. Pytest emitted only the existing Starlette/httpx and pytest-asyncio deprecation warnings.
- Test-only guard correction committed as `335347c85975d521f36262348136a135e59e4998` (`test(architecture): guard database connection calls`). The detailed review report was not modified. Task 12 awaits independent re-review; P1-C01 remains `IN_PROGRESS`.

### 2026-09-28 — Task 12 session-derived call-chain correction

- Re-review found `Session.get_bind()` could yield an engine and bypass the router boundary guard. Replaced finite connection-call propagation with general taint propagation through any method call whose receiver is already tainted. The guard detects forbidden database reads/writes and explicit connection acquisition (`get_bind`, `connection`, `connect`, `cursor`, and `raw_connection`) through chained and aliased session-derived calls. Existing commit/rollback guards remain unchanged.
- Test-first evidence: synthetic `session.get_bind().execute(...)` and direct `session.get_bind()` acquisition tests failed before the change. Coverage includes `get_bind().connect().exec_driver_sql(...)`, local and chained engine aliases, reassignment to an untainted factory, and false-positive controls for `_service(session).get()` and unrelated adapter/repository factory chains.
- Verification used the disposable `smart_warehouse_test` endpoint at `127.0.0.1:55432`, PostgreSQL 18.3 with timezone UTC; no PostgreSQL 16 result is claimed. Focused dashboard/RBAC/architecture gate passed serially — 141 passed. Full pytest passed serially — 389 passed. Architecture tests passed after final formatting — 17 passed. Ruff and `git diff --check` passed. Pytest emitted only the existing Starlette/httpx and pytest-asyncio deprecation warnings.
- Test-only correction committed as `5c69ba24141e2f96e46bce80fe54d053e1a1546a` (`test(architecture): trace session-derived database calls`). The review report was not modified. Task 12 awaits independent re-review; P1-C01 remains `IN_PROGRESS`.

### 2026-09-28 — Task 12 bound-method alias correction

- Re-review showed bound methods taken from a tainted database/session receiver lost taint when invoked through a local name. Added explicit local dataflow for tainted values and bound callables. It propagates method identity and taint through simple aliases, tuple assignments/destructuring, invocation results, and further database method chains; reassignment to an untainted factory clears the previous callable/value taint. Bound database operations such as `execute`, `add`, `get_bind`, `connection`, and transaction calls are checked by their method identity, not by the alias variable name.
- Test-first RED reproduced both `acquire = session.get_bind; engine = acquire()` and connection method alias bypasses. Regression coverage includes chained aliases, tuple/simple assignments, `execute` and `add` method aliases, safe reassignment, untainted bound factory methods, and `_service(session).get()` false-positive control. Earlier local-session alias, connection-call, router-wide, RBAC persisted-state, and transaction guard coverage remains in place.
- Verification used the disposable PostgreSQL 18.3 UTC test database `smart_warehouse_test` at `127.0.0.1:55432`; no PostgreSQL 16 result is claimed. Focused dashboard/RBAC/architecture gate passed serially — 144 passed. Full pytest passed serially — 392 passed. Architecture suite passed — 20 passed. Ruff and `git diff --check` passed. Pytest emitted only the existing Starlette/httpx and pytest-asyncio deprecation warnings.
- Test-only correction committed as `0a806c0dfd6977bdb33dc41b156c8c0a15451036` (`test(architecture): track bound database method aliases`). The review report was not modified. Task 12 awaits independent re-review; P1-C01 remains `IN_PROGRESS`.

### 2026-09-28 — Internal Task 12 accepted

- Independent final re-review of cumulative diff `e74799f..70ce726` found no remaining Critical, Important, or Minor finding.
- Reviewer verification passed serially against PostgreSQL 18.3 UTC: dashboard, RBAC matrix, and architecture suite — 144 passed; `git diff --check e74799f..70ce726` — passed. The final implementation verification also passed the full backend suite — 392 passed — and Ruff.
- Task 12 checkpoints are `6b891af`, `a688b0f`, `60a552c`, `0be5d44`, `335347c`, `56f19e0`, `5c69ba2`, `b752c42`, `0a806c0`, and `70ce726`. The detailed review record is `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-12-review-report.md`.
- Internal Task 12 is complete; P1-C01 remains `IN_PROGRESS` and advances to internal Task 13.

## Internal Task 13 Evidence (append-only)

### 2026-09-28 — Internal Task 13 implementation and verification

- Confirmed P1-C01 remains `IN_PROGRESS`, Task 12 is accepted at `7a1399b`, and the approved Phase 1 plan/specification plus `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-13-brief.md` authorize this internal scope.
- Added the frontend test/typecheck toolchain, shared API error/client contracts, query and application providers, accessible async and pagination primitives, role-ready navigation, and a responsive dark-industrial application shell while preserving the existing application for the Task 14 migration.
- Test-first evidence covered missing API client and async-state modules, exact-once 401 handling, backend error-detail preservation, retry boundaries, async accessibility, pagination boundaries, shell semantics, mobile order, and keyboard skip navigation. The two independent-review findings were reproduced with failing shell tests before correction.
- Final serial verification from `client`: `npm.cmd test -- --run` — 5 files and 12 tests passed; `npm.cmd run typecheck` — passed; `npm.cmd run build` — passed with 64 modules; `git diff --check` — passed.
- Implementation checkpoints are `8828f5d` (`feat(web): add feature-ready application foundation`) and `7b0d814` (`fix(web): improve shell keyboard and mobile order`). Detailed implementation evidence is in `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-13-implementer-report.md`.

### 2026-09-28 — Internal Task 13 accepted

- Independent review of cumulative diff `7a1399b..7b0d814` found the initial mobile utility/navigation order and missing keyboard skip link; both were corrected test-first and independently re-reviewed.
- Final re-review found no remaining Critical, Important, or Minor finding. Focused AppShell tests — 3 passed; full frontend suite — 12 passed; typecheck, build, and cumulative diff check — passed.
- The detailed review record is `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-13-review-report.md`. Internal Task 13 is complete; P1-C01 remains `IN_PROGRESS` and advances to internal Task 14.

## Internal Task 14 Evidence (append-only)

### 2026-09-28 — Internal Task 14 implementation and verification

- Confirmed P1-C01 remains `IN_PROGRESS`, Task 13 is accepted at `4c3ae5b`, and the approved Phase 1 plan/specification plus `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-14-brief.md` authorize this internal scope.
- Replaced the legacy monolithic frontend with strict public registration, login, current-user hydration from `/auth/me`, logout, query-cache invalidation, protected/role-aware routing, and typed role-derived navigation under the Task 13 application shell. Task 15–17 screens remain explicitly labelled placeholders.
- Test-first coverage verifies registration cannot submit a role, backend field mapping, token lifecycle, startup loading, missing-token behavior, authoritative current user, public/protected/role redirects, navigation visibility, `401` cleanup, ordinary authenticated `403` preservation, and shell accessibility.
- Independent review found two stale-session paths. Corrections bind unauthorized callbacks to the originating request/session generation, including token reuse, and clear a newly issued token/cache when login cannot establish `/auth/me`, while preserving an existing authenticated session on ordinary `403`.
- Final serial verification from `client`: focused auth/API/app suite — 6 files and 29 tests passed; full frontend suite — 8 files and 34 tests passed; typecheck — passed; production build — passed with 180 modules; cumulative `git diff --check` — passed.
- Implementation checkpoints are `9b1b4a9` (`feat(web): add secure authentication and role-aware routes`) and `892e2b1` (`fix(web): bind auth invalidation to session generation`). Detailed implementation evidence is in `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-14-implementer-report.md`.

### 2026-09-28 — Internal Task 14 accepted

- Independent final re-review of cumulative diff `4c3ae5b..892e2b1` found no remaining Critical, Important, or Minor finding. Login, hydration, logout, late-response, reused-token, `401`, and `403` paths were reviewed against the frozen contract.
- Reviewer verification passed: focused suite — 29 passed; full frontend suite — 34 passed; typecheck, build, and cumulative diff check — passed.
- The detailed review record is `.superpowers/sdd/2026-09-04-phase-1-production-ready/task-14-review-report.md`. Internal Task 14 is complete; P1-C01 remains `IN_PROGRESS` and advances to internal Task 15.
