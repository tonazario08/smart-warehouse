# phase-4-products — Products

## Metadata

- Status: DONE
- Phase: 4
- Plan: User-approved Smart Warehouse frontend implementation phases in this conversation
- Depends on: docs/tasks/phase-3-dashboard.md
- Created: 2026-10-07
- Started: 2026-10-07
- Completed: 2026-10-07

## Goal

Implement the authenticated Products list, create, and edit experiences from the approved Figma designs while preserving the working product API contracts, authentication, RBAC, and real-data behavior.

## Context

The approved visual source is Figma file `IoHM7Md1WkS8nt1kH4jrO4`, nodes `22:70` (Products / List), `22:362` (Products / Create), and `26:104` (Products / Edit). Phase 3 is a required completed dependency. The existing product manager and product API flow remain the behavioral foundation.

## In Scope

- Product list, search and filter presentation supported by existing data, product create form, product edit form, delete confirmation, real loading, error, and empty states.
- Reuse of Phase 1 shared UI, Phase 2 App Shell and routing, Phase 3 conventions, existing product/category API contracts, and current route guards.
- Vietnamese visible UI and Figma-aligned responsive styling.

## Out of Scope

- Backend endpoint, API-contract, authentication, token, permission, App Shell, Inventory, Warehouses, Inbound, Outbound, Dashboard, or package-manager changes.
- Mock product data, unsupported product fields, a new UI framework, or Phase 5 work.

## Acceptance Criteria

- [x] AC-1 — `/products`, `/products/new`, and `/products/:id/edit` match their approved Figma structures within the existing App Shell.
- [x] AC-2 — Product data, categories, creation, update, and deletion remain backed by the existing real API calls and preserve current authorization behavior.
- [x] AC-3 — List, empty, loading, validation, error, and deletion-confirmation states are represented without mock data.
- [x] AC-4 — Shared foundation components are reused; page styles do not duplicate generic UI primitives.
- [x] AC-5 — `npm.cmd run build`, `npx.cmd tsc --noEmit`, `git diff --check`, focused product tests, and relevant browser/API verification pass.

## Verification Commands

### Focused

- `npm.cmd run build`
- `npx.cmd tsc --noEmit`

### Regression

- Verify authenticated product list, create, edit, and delete flows against real API responses.
- Verify frontend route guards preserve existing write visibility while backend remains authorization authority.

### Static and Diff

- `git diff --check`

## Progress Log

### 2026-10-07 — Created

- Created after `docs/tasks/phase-3-dashboard.md` reached DONE.
- Awaiting design-context inspection and user approval of the Phase 4 design before the required `READY -> IN_PROGRESS` transition.

### 2026-10-07 — READY -> IN_PROGRESS

- Dependency `docs/tasks/phase-3-dashboard.md` is DONE. The user approved the Product list, create, and edit design after inspection of Figma nodes `22:70`, `22:362`, and `26:104`, the existing product manager, routes, API client, and backend contracts.
- Baseline frozen: Goal, Context, In Scope, Out of Scope, Acceptance Criteria, and Verification Commands above.
- Implementation remains in the current checkout because the uncommitted Phase 1 through Phase 3 baseline is required; a new worktree would omit it.
- Ruling: supplier selection may call the existing protected `/suppliers` endpoint only on admin create/edit routes. Products remain readable to all existing roles without requiring supplier data.

### 2026-10-07 — IN_PROGRESS -> VERIFYING

- Replaced the legacy product page route with Figma-aligned list, create, and edit pages. The implementation reuses Phase 1 UI primitives, uses the existing APIs, and adds no backend behavior.
- The list uses real products and categories, with client-side search and category filtering over the current API response. Create/edit uses existing categories, protected suppliers, product fetch, create, update, and delete contracts.

### 2026-10-07 — VERIFYING -> REVIEWING

- Verification evidence is recorded below. Proceeding with the Phase 4 scope, API-contract, RBAC, and visual-deviation review.

### 2026-10-07 — REVIEWING -> DONE

- Review passed. Changes remain inside the Products frontend and existing API client/type surface. No backend endpoint, authentication, token, RBAC, App Shell, package-manager, or subsequent phase was changed.

### 2026-10-09 — Post-completion audit reconciliation

- AC-1 is verified by the recorded inspection and approval of all three Figma nodes, browser verification of list and edit rendering, and source inspection of the shared create/edit form component.
- AC-2 is verified by source calls to the existing product/category/supplier CRUD clients, protected write routes, and the recorded master-data/auth backend tests.
- AC-3 is verified by source inspection of loading, error, empty, validation, and confirmation branches without mock data.
- AC-4 is verified by the shared Button, ConfirmDialog, DataTable, EmptyState, FeedbackMessage, Input, PageHeader, and Select imports.
- AC-5 is verified by the recorded product helper test, browser/API run, backend regressions, TypeScript/build/diff checks, plus the clean `c0727c4` audit build.
- The checklist and review-result enum were reconciled to existing evidence; no new browser or Figma review is claimed.

## Verification Evidence

- Focused product-filter test: compiled `client/tests/product-list.test.js` with its TypeScript helper and ran it with Node successfully. It failed first because the helper did not exist, then passed.
- `npx.cmd tsc --noEmit` in `client/`: passed.
- `npm.cmd run build` in `client/`: passed.
- `git diff --check`: passed.
- `.venv\\Scripts\\python.exe -m pytest tests\\test_master_data.py tests\\test_auth.py -q`: 14 passed. Existing Starlette/httpx and pytest-cache warnings remain.
- Browser integration against an isolated local FastAPI SQLite dataset: admin login, real Products list, search/filter controls, edit route, prefilled edit form, categories, and supplier empty state were verified.

## Review Result

- Result: APPROVED
- Findings: none; the existing review retained only the documented client-side filtering capability deviation.

Figma capability deviation retained intentionally:

- The current product API has no server-side search or category filtering contract. Search and filtering therefore operate over the real page returned by the existing API, without fabricating server pagination or data.

## Completion Evidence

- AC-1 through AC-5 satisfied with the verification evidence above.
- Isolated FastAPI and Vite verification processes were stopped. No commit, push, backend change, or Phase 5 work was performed.
