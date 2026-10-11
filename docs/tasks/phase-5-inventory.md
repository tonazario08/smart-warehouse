# phase-5-inventory — Inventory

## Metadata

- Status: DONE
- Phase: 5
- Plan: User-approved Smart Warehouse frontend implementation phases in this conversation
- Depends on: docs/tasks/phase-4-products.md
- Created: 2026-10-07
- Started: 2026-10-07
- Completed: 2026-10-07

## Goal

Implement the authenticated Inventory overview and stock-detail experiences from the approved Figma designs while preserving current inventory API contracts, authentication, RBAC, and real-data behavior.

## Context

The approved visual source is Figma file `IoHM7Md1WkS8nt1kH4jrO4`, nodes `29:164` (Inventory / Overview) and `29:384` (Inventory / Stock Detail). Phase 4 is a required completed dependency.

## In Scope

- Inventory overview, search/filter presentation supported by real API data, stock-detail view, loading, error, and empty states.
- Reuse of the established shared UI, App Shell, routes, and existing stock, product, and warehouse API contracts.

## Out of Scope

- Backend/API contracts, authentication, token, RBAC, App Shell, product, warehouse, inbound, outbound, dashboard, or package-manager changes.
- Mock inventory data, unsupported stock-history fields, a new UI framework, and Phase 6 work.

## Acceptance Criteria

- [x] AC-1 — `/inventory` and `/inventory/:warehouseId/:productId` reflect the approved Figma structures within the existing App Shell.
- [x] AC-2 — All data derives from existing stock, product, and warehouse APIs, and unavailable capabilities use an explicit state rather than mock data.
- [x] AC-3 — Existing read/write role behavior remains unchanged; frontend visibility never replaces backend authorization.
- [x] AC-4 — Shared primitives and formatters are reused without duplicating App Shell or generic styles.
- [x] AC-5 — build, TypeScript, diff, focused tests, and browser/API verification pass.

## Progress Log

### 2026-10-07 — Created

- Created after `docs/tasks/phase-4-products.md` reached DONE.
- Awaiting Figma/context inspection and user approval before the required `READY -> IN_PROGRESS` transition.

### 2026-10-07 — READY -> IN_PROGRESS

- Dependency `docs/tasks/phase-4-products.md` is DONE. The user approved the design after Figma and current-contract inspection.
- Baseline frozen. Stock overview and detail will use existing stock, product, and warehouse APIs. Transaction metadata absent from the current API will not be invented.

### 2026-10-07 — IN_PROGRESS -> VERIFYING

- Replaced the Inventory route placeholders with overview and stock-detail pages. They join the existing stock, product, and warehouse responses only; no backend contract, authentication behavior, token handling, or permissions were changed.
- Added focused helper coverage for the real-data join, low-stock threshold, search, and warehouse filtering behavior.

### 2026-10-07 — VERIFYING -> REVIEWING

- Build, type checking, focused frontend tests, inventory/auth backend regression tests, diff checking, and browser integration against an isolated local API database completed. Proceeding with scope and design review.

### 2026-10-07 — REVIEWING -> DONE

- Review passed. Phase 5 remains limited to authenticated Inventory routes, shared inventory presentation helpers, and page styling. The API, backend, App Shell, authentication, RBAC authority, and subsequent phases remain unchanged.

### 2026-10-09 — Post-completion audit reconciliation

- AC-1 is verified by the recorded Figma/context design approval and browser verification of both inventory overview and stock-detail routes.
- AC-2 is verified by source calls to existing stock, product, and warehouse APIs, focused join/filter coverage, and the explicit unavailable history state.
- AC-3 is verified by the shared permission helper, route protection, role-visible action behavior, and recorded inventory/auth backend tests.
- AC-4 is verified by source imports of shared Badge, Button, DataTable, EmptyState, FeedbackMessage, Input, PageHeader, Select, and formatters.
- AC-5 is verified by the recorded focused tests, browser/API run, backend regressions, TypeScript/build/diff checks, plus the clean `c0727c4` audit build.
- The checklist and review-result enum were reconciled to existing evidence; no new browser or Figma review is claimed.

## Verification Evidence

- Focused inventory-helper test: compiled `client/tests/inventory-overview.test.js` with the TypeScript helper and ran it with Node successfully. It failed first because the helper did not exist, then passed with 2 tests.
- `npx.cmd tsc --noEmit` in `client/`: passed.
- `npm.cmd run build` in `client/`: passed.
- `git diff --check`: passed.
- `.venv\\Scripts\\python.exe -m pytest tests\\test_inventory.py tests\\test_auth.py -q`: 11 passed. Existing Starlette/httpx, asyncio, and pytest-cache warnings remain.
- Browser integration against an isolated local FastAPI SQLite dataset: protected Inventory navigation redirected to Login before authentication; login then loaded real stock rows, stock totals, low-stock status, filter controls, and the stock-detail route. The detail route exposed its calculated level, role-visible inbound/outbound actions, and explicit unavailable transaction-history state.
- The isolated FastAPI and Vite verification processes were stopped. No commit, push, backend change, or Phase 6 implementation was performed.

## Review Result

- Result: APPROVED
- Findings: none; the existing review retained only the documented transaction-history capability deviation.

Figma capability deviation retained intentionally:

- The existing transaction API does not supply timestamp, actor, or reference data required by the approved stock-history presentation. The detail page renders an explicit Vietnamese unavailable state instead of fabricated history records.

## Completion Evidence

- AC-1 through AC-5 satisfied with the verification evidence above.
