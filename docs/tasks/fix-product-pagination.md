# fix-product-pagination — Restore complete product joins in warehouse views

## Metadata

- Status: DONE
- Phase: Post-implementation frontend regression repair
- Plan: User-approved follow-up to finding F-1 in `docs/tasks/post-commit-audit-c0727c4.md`, approved 2026-10-11
- Depends on: docs/tasks/phase-7-inbound-outbound.md
- Created: 2026-10-11
- Started: 2026-10-11
- Completed: 2026-10-11

## Goal

Fix the confirmed first-page-only product lookup so the Dashboard, Inventory, and Warehouses views correctly join all products to stock, status, alerts, and transaction labels when there are more than 100 products.

## Context

Finding F-1 in the post-commit audit identifies five views that call `api.products()` (page 1, `page_size=100`) while the Phase 7 API client already provides `api.productsAll()`. With a referenced product on page 2, `buildInventoryRows` drops the stock row, while `buildDashboardOverview` can show a misleading healthy status because a missing product's reorder level defaults to zero. The fix uses current API contracts and the existing frontend architecture.

## In Scope

- Change only product-list loading and the associated data mapping in `client/src/pages/DashboardPage.tsx`, `InventoryPage.tsx`, `StockDetailPage.tsx`, `WarehousesPage.tsx`, and `WarehouseDetailPage.tsx` as needed.
- Reuse the existing `api.productsAll()` method without changing API endpoints, request contracts, pagination semantics, or the products-list screen.
- Add focused frontend regression tests covering product records across multiple pages, inventory stock rows, warehouse summary totals, and dashboard low-stock alerts.
- Preserve existing loading/error behavior, authentication, token handling, route guards, backend RBAC, and real API data.
- Record test/build evidence and findings in this task file only.

## Out of Scope

- Backend changes, product CRUD flow changes, UI redesign, Figma visual review, dependency or package-manager changes, and unrelated audit findings.
- Changing existing task records, removing unrelated files, staging, committing, pushing, or deploying.

## Acceptance Criteria

- [x] AC-1 — All five affected pages obtain every product page before joining stock, warehouse, and transaction data; no stock record is lost solely because its product falls on page 2 or later.
- [x] AC-2 — Dashboard stock status and alerts use the actual reorder threshold of page-2 products; warehouse totals and inventory detail resolve those products correctly.
- [x] AC-3 — Existing API endpoints, authentication, RBAC, product-list behavior, and user-visible loading/error states are preserved, without fake business data.
- [x] AC-4 — Focused tests reproduce the >100-product failure and pass after the change, including representative single-page and multi-page cases.
- [x] AC-5 — Frontend build, TypeScript checks, relevant regression tests, and `git diff --check` pass; the resulting diff is independently reviewed without commit/push.

## Verification Commands

### Focused

- Execute the appropriate existing `client/tests/` Node tests and new focused pagination regression tests; use the existing TypeScript/Node test workflow.

### Regression

- In `client/`: `npm.cmd run build`.
- In `client/`: `npx.cmd tsc --noEmit`.
- Confirm product-list flows retain their intentionally paginated API behavior and that the authenticated views still use their existing token and error handling.

### Static and Diff

- `git diff --check`
- `git status --short`
- Review the diff for only the five affected pages, focused frontend tests, and this task file.

## Progress Log

### 2026-10-11 — Created

- User approved this specific task path and Native Subagent remediation for finding F-1.
- Depends on the completed Phase 7 implementation that introduced `api.productsAll()`; this audit follow-up does not amend or resume the separate post-commit audit task.

### 2026-10-11 — READY -> IN_PROGRESS

- Validated the user-approved follow-up authority and F-1 identifier in the referenced audit; explicit dependency `docs/tasks/phase-7-inbound-outbound.md` is DONE.
- Goal, Context, In Scope, Out of Scope, Acceptance Criteria, and Verification Commands are frozen as written. Only the selected task, five named pages, and focused frontend tests may change.
- Inspected the existing dirty working tree. Pre-existing configuration, plans, task records, and untracked files are preserved; no staging, commit, push, or dependency changes are authorized.
- Traced the defect from all five page loaders through `api.products()` to joins consuming only `Page.items`. Existing `api.productsAll()` fetches every page without changing endpoint or authentication contracts.

### 2026-10-11 — IN_PROGRESS -> VERIFYING

- Replaced only the five selected page loaders' first-page product requests with the existing `api.productsAll()` and passed its array directly into unchanged joins.
- Added consumer-level Node regression tests running the real compiled page effects, API requests, and joins against complete one-page, 101-product, and 201-product fixtures. React hook hosting and authenticated route context are test substitutes; no production fake data or dependencies were added.
- Test-first reproduction after correcting test-harness compilation: 6 passed and 11 failed for the expected first-page-only labels, missing stock, understated warehouse totals, omitted later-page errors, and premature loading completion. After the minimal fix: 17 passed, 0 failed.
- Full frontend regression, production build, TypeScript checks, and final diff verification follow. Independent review remains pending.

### 2026-10-11 — VERIFYING -> REVIEWING

- All final verification commands passed. The source diff contains only product-list loading and direct-array mapping changes in the five selected pages; pre-existing dirty files are preserved.
- AC-1 through AC-4 have evidence below. AC-5 remains unchecked until independent review. The implementing Native Subagent does not approve its own diff or mark this task DONE.
- No staging, commit, push, backend change, API helper change, package change, or browser/Figma claim was made.

### 2026-10-11 — Independent review: REVIEWING -> DONE

- Main agent independently inspected all five source diffs, the complete focused regression test, `api.productsAll()`, and the existing product-list, auth, token, error, and loading paths. No blocking finding was identified in this task's scope.
- Independently recompiled the five page entry points and seven existing test files with the documented TypeScript CLI command (exit 0); reran `node --test tests/product-pagination.test.js` (17 passed, 0 failed) and the documented compiled existing frontend tests (9 Node subtests passed, 0 failed, plus top-level assertions).
- Independently reran `npm.cmd run build` (exit 0, 77 Vite modules), `npx.cmd tsc --noEmit` (exit 0), and `git diff --check` (exit 0). No staged files were present.
- Confirmed AC-1 through AC-5 against the implementation, tests and diff; no additional fix cycle was required. These tests use substituted React hooks and an API fixture; they are not browser or live-backend integration evidence, and no such verification is claimed.
- No commit, push, deployment, history rewrite, API contract change, or alteration to unrelated dirty files was performed.

## Verification Evidence

- From `client/`, compiled the five page entry points and all seven existing test files using the installed TypeScript CLI:

```powershell
npx.cmd tsc --ignoreConfig --target es2022 --module commonjs --moduleResolution bundler --noCheck --jsx react-jsx --esModuleInterop --skipLibCheck --allowJs --rootDir . --outDir node_modules/.tmp/pagination-tests src/pages/DashboardPage.tsx src/pages/InventoryPage.tsx src/pages/StockDetailPage.tsx src/pages/WarehousesPage.tsx src/pages/WarehouseDetailPage.tsx tests/api-error-status.test.js tests/auth-errors.test.js tests/dashboard-overview.test.js tests/inventory-overview.test.js tests/movement-list.test.js tests/product-list.test.js tests/warehouse-summary.test.js
```

- Compilation exit code 0. `--noCheck` emits the CommonJS test harness only; independent production TypeScript checks below perform type validation. Generated output remains under ignored `node_modules/.tmp/`.
- `node --test tests/product-pagination.test.js`: 17 passed, 0 failed. Five single-page cases, five 101-product page consumer cases, a 201-product/three-page API case, five later-page error cases, and delayed-second-page loading coverage passed. Test-only fetch responses contain full documented Product, Warehouse, Stock, DashboardStats, Transaction, and Page contracts; requests retain existing URLs and protected-endpoint bearer tokens.
- The 101-product fixtures verify stock product 101, reorder threshold 10, quantity 3, low status, warehouse product count 2, total quantity 23, low-stock count 1, dashboard alert count 1, transaction labels, and both detail views. The single-page fixtures make only the first product request. `api.products()` still returns its 100-item page, and unchanged `ProductsPage.tsx` still consumes that paginated response.
- All seven existing frontend test files passed using the emitted CommonJS files:

```powershell
node -e "const fs=require('node:fs'); const folder='./node_modules/.tmp/pagination-tests/tests'; for(const f of fs.readdirSync(folder).filter(f=>f.endsWith('.test.js'))) require(folder+'/'+f);"
```

- Existing-suite result: 9 Node subtests passed, 0 failed, plus the top-level assertion scripts for API status, Dashboard overview, and product filtering passed; exit code 0.
- Test harness setup initially attempted the removed TypeScript JavaScript transpiler API and `moduleResolution=node10`; both were corrected before the valid test-first reproduction. Node test discovery inside `node_modules` returned zero tests/failed explicit discovery, so existing compiled tests were loaded directly with the successful command above; the zero-test invocation is not claimed as verification.
- `npm.cmd run build`: exit code 0; TypeScript build and Vite production build passed, 77 modules transformed.
- `npx.cmd tsc --noEmit`: exit code 0, no diagnostics.
- `git diff --check`: exit code 0. `git diff --staged --name-only`: empty. Final `git status --short` confirms only the five selected pages, this new focused test, and this selected task were changed by this implementation; unrelated pre-existing changes remain.
- Source inspection confirms unchanged 401 logout handlers, bearer-token arguments, role/permission checks, error/loading branches, endpoints and ProductsPage behavior. No real browser or Figma execution was required or performed for this bounded data-loading repair.

## Review Result

- Result: APPROVED
- Findings: No blocking findings within this bounded product-pagination task. Browser and live-backend integration remain unexecuted, outside the task's required verification commands.

## Completion Evidence

- AC-1 through AC-5 checked with source-diff review, 17 focused regression tests, 9 existing Node subtests plus top-level assertions, frontend build, TypeScript check and `git diff --check` passing on 2026-10-11.
- Task-specific changes: `client/src/pages/DashboardPage.tsx`, `InventoryPage.tsx`, `StockDetailPage.tsx`, `WarehousesPage.tsx`, `WarehouseDetailPage.tsx`, `client/tests/product-pagination.test.js`, and this task record. Changes remain uncommitted and unstaged.
