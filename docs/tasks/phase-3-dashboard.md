# phase-3-dashboard — Dashboard

## Metadata

- Status: DONE
- Phase: 3
- Plan: User-approved Smart Warehouse frontend implementation phases in this conversation
- Depends on: docs/tasks/phase-2-app-shell-routing.md
- Created: 2026-10-07
- Started: 2026-10-07
- Completed: 2026-10-07

## Goal

Implement the authenticated Dashboard at `/dashboard` from the approved Figma design, using real backend data while preserving the completed Phase 2 App Shell, authentication, API contracts, and RBAC behavior.

## Context

The visual source of truth is Figma file `IoHM7Md1WkS8nt1kH4jrO4`, node `14:2` (Dashboard / Overview). Phase 2 supplies the protected App Shell, Sidebar, Topbar, Breadcrumbs, user menu, routing, and role-aware navigation. The backend remains the authority for authorization.

## In Scope

- Dashboard page composition, page header, KPI cards, inventory overview, operational alerts, empty/error/loading states, and Dashboard-specific formatting derived from available real API responses.
- Reuse of Phase 1 shared UI primitives, design tokens, layout components, formatters, and permissions.
- Figma node `14:2` inspection, local asset use where required, and responsive behavior consistent with the approved desktop design.

## Out of Scope

- Changes to the App Shell, router architecture, authentication flow, backend endpoints, API contracts, RBAC rules, Products, Inventory, Warehouses, Inbound, Outbound, and authentication page redesign.
- Mock business data, hard-coded KPI values, a new UI framework, or package-manager changes.

## Acceptance Criteria

- [x] AC-1 — `/dashboard` renders the approved Figma Dashboard structure within the completed App Shell using Vietnamese UI text.
- [x] AC-2 — All dashboard values, rows, and alerts originate from existing API data; unavailable backend capabilities are shown with appropriate empty or unavailable states rather than mock data.
- [x] AC-3 — Dashboard visibility and actions preserve Phase 2 RBAC behavior; frontend checks remain navigational only.
- [x] AC-4 — Shared UI primitives and formatters are reused where appropriate, without duplicating App Shell or page-generic styles.
- [x] AC-5 — `npm.cmd run build`, `npx.cmd tsc --noEmit`, `git diff --check`, and relevant browser/API integration checks pass.

## Verification Commands

### Focused

- `npm.cmd run build`
- `npx.cmd tsc --noEmit`

### Regression

- Verify an authenticated admin can load `/dashboard` with real API responses.
- Verify non-admin behavior continues to follow Phase 2 route guards and backend authority.
- Verify dashboard loading, error, and empty states without mock business data.

### Static and Diff

- `git diff --check`

## Progress Log

### 2026-10-07 — Created

- Created after `docs/tasks/phase-2-app-shell-routing.md` reached DONE.
- Awaiting the required baseline inspection and `READY -> IN_PROGRESS` transition before implementation.

### 2026-10-07 — READY -> IN_PROGRESS

- Dependency `docs/tasks/phase-2-app-shell-routing.md` is DONE. The Figma design context for node `14:2`, current frontend foundation, route guard, auth provider, API client, backend dashboard, warehouse, inventory, and transaction contracts were inspected.
- Baseline frozen: Goal, Context, In Scope, Out of Scope, Acceptance Criteria, and Verification Commands as recorded above.
- Implementation remains in the current checkout because Phase 1 and Phase 2 are uncommitted workspace baseline changes; creating an isolated worktree would omit those required dependencies.
- The dashboard will request existing `/dashboard/stats`, `/products`, `/warehouses`, `/stock`, and `/transactions` contracts. Warehouse capacity is not available in the current API and will use an explicit unavailable state instead of inferred or mock capacity.

### 2026-10-07 — IN_PROGRESS -> VERIFYING

- Added `DashboardPage` at `/dashboard`, a real-data dashboard overview mapper, dashboard-specific responsive styles, and client types/API methods for existing dashboard and transaction endpoints.
- Reused Phase 1 `PageHeader`, `Button`, `DataTable`, `Badge`, `EmptyState`, `FeedbackMessage`, and shared formatters. No backend endpoint, authentication, token, route-guard, or permission contract was changed.
- The dashboard displays real counts, stock, low-stock alerts, warehouse totals, and recent transactions. It explicitly identifies warehouse capacity as unavailable because the backend does not expose that field.

### 2026-10-07 — VERIFYING -> REVIEWING

- Verification evidence is recorded below. Proceeding with a scope, API-contract, RBAC, and Figma-deviation review only.

### 2026-10-07 — REVIEWING -> DONE

- Review passed. Changes are confined to the Phase 3 dashboard, its existing API client/type surface, its focused test, and this task record. No backend, authentication, token storage, route-guard, or permission behavior was changed.
- Confirmed all application values originate from existing contracts. The only deliberate Figma capability deviation is warehouse capacity and trend comparison data, which are not available from the backend and are represented without mock values.

### 2026-10-09 — Post-completion audit reconciliation

- AC-1 is verified by the recorded Figma node inspection, desktop browser rendering check, and Vietnamese Dashboard implementation.
- AC-2 is verified by the real-API browser dataset, mapper coverage, explicit unavailable-capacity state, and source inspection showing existing API calls only.
- AC-3 is verified by the preserved Phase 2 route guard, permission mapping, and backend auth regression evidence.
- AC-4 is verified by source imports of shared UI primitives, formatters, and the shared dashboard mapper.
- AC-5 is verified by the recorded focused test, browser/API run, TypeScript/build/diff checks, plus the clean `c0727c4` audit build.
- The checklist and review-result enum were reconciled to existing evidence; no new browser or Figma review is claimed.

## Verification Evidence

- Focused mapper test: compiled `client/tests/dashboard-overview.test.js` with its TypeScript source and ran it with Node successfully. The test first failed before the mapper was implemented, then passed.
- `npx.cmd tsc --noEmit` in `client/`: passed.
- `npm.cmd run build` in `client/`: passed.
- `git diff --check`: passed.
- `.venv\\Scripts\\python.exe -m pytest tests\\test_dashboard.py tests\\test_auth.py -q`: 9 passed. Warnings are existing Starlette/httpx and pytest-cache compatibility warnings.
- Browser integration against an isolated local FastAPI SQLite dataset: logged in as an admin and verified `/dashboard` loaded values from existing API responses: 2 products, 22 total stock, 1 warehouse, 1 low-stock item, stock rows, one alert, and two transactions. The Desktop table was adjusted and visually rechecked with no horizontal scroll. The loading, error, and recovery paths were also verified; the empty-data mapper path is covered by the focused test.

## Review Result

- Result: APPROVED
- Findings: none; the existing review recorded only intentional backend-capability deviations.

Figma capability deviations retained intentionally:

- Warehouse capacity percentages and comparison trends are not rendered because no current API contract exposes capacity or comparison-period data.
- Recent activity uses the existing transaction contract, which has no timestamp or reference field, so the UI does not fabricate either field.

## Completion Evidence

- AC-1 through AC-5 satisfied with the verification evidence above.
- Isolated FastAPI and Vite verification processes were stopped after the checks. No commit, push, backend change, or Phase 4 work was performed.
