# phase-7-inbound-outbound — Inbound and Outbound

## Metadata

- Status: DONE
- Phase: 7
- Plan: User-approved Smart Warehouse frontend implementation phases in this conversation
- Depends on: docs/tasks/phase-6-warehouses.md
- Created: 2026-10-07
- Started: 2026-10-07
- Completed: 2026-10-07

## Goal

Implement authenticated Inbound and Outbound list and create experiences from the approved Figma designs, using only existing inventory movement contracts and preserving real stock behavior, authentication, and RBAC.

## Context

The approved visual source is Figma file `IoHM7Md1WkS8nt1kH4jrO4`, nodes `36:10` (Inbound / List), `36:247` (Outbound / List), `37:104` (Inbound / Create), and `37:248` (Outbound / Create). Phase 6 is a required completed dependency.

## In Scope

- Inbound and Outbound lists, creation forms, real loading/error/empty states, and post-submission navigation using current APIs.
- Reuse of the existing App Shell, shared UI, permission helpers, stock/product/warehouse contracts, and current protected routes.

## Out of Scope

- Backend/API contracts, authentication, token handling, RBAC authority, App Shell, product, inventory, warehouse, dashboard, or package-manager changes.
- Mock movement data, invented timestamps, actor or reference fields, a new UI framework, and Phase 8 work.

## Acceptance Criteria

- [x] AC-1 — `/inbound`, `/inbound/new`, `/outbound`, and `/outbound/new` reflect their approved Figma structures inside the existing App Shell.
- [x] AC-2 — All movement and form data uses current APIs; unavailable information is explicit rather than fabricated.
- [x] AC-3 — Only roles with existing inventory-write permission can create movements; backend remains authoritative.
- [x] AC-4 — Shared primitives, formatters, and components are reused without duplicating generic behavior.
- [x] AC-5 — build, TypeScript, diff, focused tests, relevant backend tests, and available browser/API verification pass.

## Verification Commands

### Focused

- `npm.cmd run build`
- `npx.cmd tsc --noEmit`

### Regression

- Verify inbound/outbound creation changes stock through the existing backend and respects inventory-write authorization.

### Static and Diff

- `git diff --check`

## Progress Log

### 2026-10-07 — Created

- Created after `docs/tasks/phase-6-warehouses.md` reached DONE.
- Dependency is complete. Awaiting Figma and API-context inspection plus user approval of the bounded Phase 7 design before the required `READY -> IN_PROGRESS` transition.

### 2026-10-07 — READY -> IN_PROGRESS

- Dependency `docs/tasks/phase-6-warehouses.md` is DONE. The user approved the Figma-based bounded design for Inbound and Outbound list/create routes.
- Baseline frozen. Existing inventory movement endpoints and permission behavior will be preserved; unavailable transaction metadata will not be invented.

### 2026-10-07 — IN_PROGRESS -> VERIFYING

- Replaced the Inbound and Outbound placeholders with shared real-data list and creation pages. Existing `/transactions`, `/inbounds`, and `/outbounds` contracts remain unchanged.
- Focused frontend checks and inventory/auth backend regression tests have passed. Browser integration and final review remain in progress.

### 2026-10-07 — VERIFYING -> IN_PROGRESS

- Independent review found that movement views could silently omit transactions and products beyond the first 100-product API page. It also identified missing-metadata disclosure and a load-error/empty-state collision. The implementation returns to IN_PROGRESS to address these findings without changing backend contracts.

### 2026-10-07 — IN_PROGRESS -> VERIFYING

- Added pagination across all current product pages for movement lists and creation selections, localized API error states, kept load errors distinct from empty data, and disclosed transaction metadata unavailable from the current API.

### 2026-10-07 — VERIFYING -> REVIEWING

- Re-ran focused tests, production build, TypeScript, diff validation, relevant backend regressions, isolated-browser checks, and the complete backend suite. The independent review findings were rechecked against the updated implementation.

### 2026-10-07 — REVIEWING -> DONE

- Review passed with no remaining blocking Phase 7 findings. The work is confined to inbound/outbound frontend pages, a shared movement helper, one product-pagination API helper, types, styling, tests, and their routes. Backend endpoints, authentication, token handling, RBAC authority, and later phases did not change.

### 2026-10-09 — Post-completion audit reconciliation

- `Started` is set from the existing dated `READY -> IN_PROGRESS` entry; no date was inferred.
- AC-1 is verified by the recorded Figma-based design approval and browser loading of all four list/create routes inside App Shell.
- AC-2 is verified by current transaction/product/warehouse API calls, multi-page product coverage, and explicit disclosure of unavailable transaction metadata.
- AC-3 is verified by inventory-write route guards and the recorded inventory/auth backend authorization tests.
- AC-4 is verified by source reuse of shared UI primitives, formatters, and the movement helper.
- AC-5 is verified by the recorded focused suite, browser/API run, relevant backend tests, TypeScript/build/diff checks, the later migration repair, and the clean `c0727c4` audit test/build run.
- The checklist and review-result enum were reconciled to existing evidence; no new browser or Figma review is claimed.

## Verification Evidence

- Focused movement-helper test: failed first because the helper did not exist, then passed with 2 tests.
- The focused test harness initially used a Node ESM import without its `.js` extension. After correcting that test-only import, the compiled focused suite passed with 3 tests, including a two-page product pagination case.
- `npx.cmd tsc --noEmit`, `npm.cmd run build`, and `git diff --check`: passed after the final changes.
- `.venv\\Scripts\\python.exe -m pytest tests\\test_inventory.py tests\\test_auth.py -q`: 11 passed with existing dependency/cache warnings.
- Browser integration against an isolated local FastAPI SQLite dataset: authenticated login redirected to the protected dashboard; `/inbound`, `/inbound/new`, `/outbound`, and `/outbound/new` loaded inside the App Shell using real transaction, product, and warehouse data. The lists disclose transaction metadata unavailable from the current API. No movement was submitted through the browser; backend inventory tests verify existing inbound/outbound stock effects and authorization.
- Complete backend suite: 52 passed, 2 failed. `tests/test_migration.py::test_initial_revision_upgrades_an_empty_database` and `tests/test_seed.py::test_seed_is_idempotent_and_preserves_existing_user_credentials` fail because the pre-existing `alembic/env.py` replaces the test-configured Alembic URL with `get_settings().database_url`. Phase 7 did not change backend or migration files.
- The isolated FastAPI and Vite verification processes were stopped. No commit, push, backend change, or Phase 8 implementation was performed.

## Review Result

- Result: APPROVED
- Findings: none; the existing review retained only documented API metadata and edit-capability deviations.

Figma capability deviations retained intentionally:

- The current `GET /transactions` response contains only transaction type, warehouse, product, and quantity. It does not provide timestamp, actor, or reference fields. The list says so explicitly instead of fabricating them.
- The current movement API has no edit endpoint. The Figma list edit affordance is therefore omitted rather than presented as a non-functional control.

## Completion Evidence

- AC-1 through AC-5 satisfied with the verification evidence above.
