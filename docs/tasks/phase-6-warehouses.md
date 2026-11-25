# phase-6-warehouses — Warehouses

## Metadata

- Status: DONE
- Phase: 6
- Plan: User-approved Smart Warehouse frontend implementation phases in this conversation
- Depends on: docs/tasks/phase-5-inventory.md
- Created: 2026-10-07
- Started: 2026-10-07
- Completed: 2026-10-07

## Goal

Implement the authenticated Warehouse list, detail, and create/edit experiences from the approved Figma designs while preserving real warehouse APIs, authentication, RBAC, and existing application behavior.

## Context

The approved visual source is Figma file `IoHM7Md1WkS8nt1kH4jrO4`, nodes `33:6` (Warehouses / List), `34:89` (Warehouses / Detail), and `35:150` (Warehouses / Create Edit). Phase 5 is a required completed dependency.

## In Scope

- Warehouse list, detail, and create/edit presentation backed by current APIs, plus loading, error, empty, and permission-appropriate states.
- Reuse of established shared UI, App Shell, routes, and existing warehouse/stock/product contracts.

## Out of Scope

- Backend/API contracts, authentication, token handling, RBAC authority, App Shell, product, inventory, inbound, outbound, dashboard, or package-manager changes.
- Mock warehouse data, unsupported capacity/history fields, a new UI framework, and Phase 7 work.

## Acceptance Criteria

- [x] AC-1 — `/warehouses`, `/warehouses/new`, `/warehouses/:id`, and `/warehouses/:id/edit` reflect the approved Figma structures inside the existing App Shell.
- [x] AC-2 — Warehouse and associated inventory data derives only from existing API responses; unavailable information is explicit rather than fabricated.
- [x] AC-3 — Existing route/write visibility remains role-appropriate and backend authorization remains authoritative.
- [x] AC-4 — Shared primitives, formatters, and existing page conventions are reused without duplicating generic components or styles.
- [x] AC-5 — build, TypeScript, diff, focused tests, and available browser/API verification pass.

## Verification Commands

### Focused

- `npm.cmd run build`
- `npx.cmd tsc --noEmit`

### Regression

- Verify the protected Warehouse routes and read/write role behavior against existing API responses.

### Static and Diff

- `git diff --check`

## Progress Log

### 2026-10-07 — Created

- Created after `docs/tasks/phase-5-inventory.md` reached DONE.
- Dependency is complete. Awaiting Figma/context inspection and user approval of the bounded Phase 6 design before the required `READY -> IN_PROGRESS` transition.

### 2026-10-07 — READY -> IN_PROGRESS

- Dependency `docs/tasks/phase-5-inventory.md` is DONE. The user approved the Figma-based bounded design for Warehouse list, detail, and create/edit routes.
- Baseline frozen. The implementation will preserve the existing `GET /warehouses`, `GET /warehouses/{id}`, `POST /warehouses`, and `PUT /warehouses/{id}` contracts. Fields unsupported by that API, including the Figma status control, will not be fabricated.

### 2026-10-07 — IN_PROGRESS -> VERIFYING

- Replaced all Warehouse route placeholders with real list, detail, and create/edit pages. The implementation only extends the existing API client with warehouse endpoints that already exist on the backend.
- Added focused coverage for warehouse inventory aggregation and search, including warehouses without a stock record.

### 2026-10-07 — VERIFYING -> REVIEWING

- Focused frontend checks, build, type checking, diff checking, relevant backend regression tests, and isolated browser/API verification completed. Proceeding with scope, API, RBAC, and Figma capability review.

### 2026-10-07 — REVIEWING -> DONE

- Review passed. The completed work is confined to Warehouse frontend pages, API client/type declarations for existing warehouse contracts, the shared warehouse summary helper, and page styling. No backend endpoint, authentication, token, RBAC authority, App Shell, or subsequent phase changed.

### 2026-10-09 — Post-completion audit reconciliation

- `Started` is set from the existing dated `READY -> IN_PROGRESS` entry; no date was inferred.
- AC-1 is verified by the recorded Figma-based design approval, browser verification of list, detail, and shared edit-form rendering, and source inspection of the same form component's create mode.
- AC-2 is verified by source calls to current warehouse, stock, and product APIs, aggregation tests, and the explicit unsupported-status disclosure.
- AC-3 is verified by protected write routes, shared permission checks, and recorded warehouse/auth backend tests.
- AC-4 is verified by source imports of shared UI primitives, inventory helpers, formatters, and existing App Shell conventions.
- AC-5 is verified by the recorded focused tests, browser/API run, relevant backend regressions, TypeScript/build/diff checks, the later migration repair, and the clean `c0727c4` audit test/build run.
- The checklist and review-result enum were reconciled to existing evidence; no new browser or Figma review is claimed.

## Verification Evidence

- Focused warehouse-summary test: compiled `client/tests/warehouse-summary.test.js` with the TypeScript helpers and ran it with Node successfully. It failed first because the helper did not exist, then passed with 2 tests.
- `npx.cmd tsc --noEmit` in `client/`: passed.
- `npm.cmd run build` in `client/`: passed.
- `git diff --check`: passed.
- `.venv\\Scripts\\python.exe -m pytest tests\\test_warehouses.py tests\\test_auth.py -q`: 9 passed. Existing Starlette/httpx, asyncio, and pytest-cache warnings remain.
- Browser integration against an isolated local FastAPI SQLite dataset: authenticated Warehouse list loaded real KPI and table data; the detail route showed its real warehouse and stock rows; the edit form fetched and prefilled the existing warehouse. The status capability was disclosed instead of fabricated.
- Full backend suite result: 52 passed and 2 failed. `tests/test_migration.py::test_initial_revision_upgrades_an_empty_database` and `tests/test_seed.py::test_seed_is_idempotent_and_preserves_existing_user_credentials` fail because the pre-existing change in `alembic/env.py` always replaces the test-configured Alembic URL with `get_settings().database_url`. This task did not modify backend or migration files.
- The isolated FastAPI and Vite verification processes were stopped. No commit, push, backend change, or Phase 7 implementation was performed.

## Review Result

- Result: APPROVED
- Findings: none; the existing review retained only the documented status-field and icon capability deviations.

Figma capability deviations retained intentionally:

- The approved form contains a warehouse-status control, but the current warehouse API has no status field. The implemented form clearly explains that limitation and submits only supported fields.
- Figma specifies an icon-only edit control. The current local asset set has no matching edit SVG, and temporary Figma asset URLs cannot be used in code. The implementation uses an accessible Vietnamese `Sửa` action instead.

## Completion Evidence

- AC-1 through AC-5 satisfied with the focused verification evidence above.
