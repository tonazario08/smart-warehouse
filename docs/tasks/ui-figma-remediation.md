# ui-figma-remediation — Align approved Smart Warehouse screens with Figma

## Metadata

- Status: DONE
- Phase: Post-delivery cross-phase visual remediation (one executable milestone)
- Plan: User-approved Figma comparison and remediation, 2026-10-11; approved file `IoHM7Md1WkS8nt1kH4jrO4` and the node IDs below
- Depends on: docs/tasks/phase-2-app-shell-routing.md, docs/tasks/phase-3-dashboard.md, docs/tasks/phase-4-products.md, docs/tasks/phase-5-inventory.md, docs/tasks/phase-6-warehouses.md, docs/tasks/phase-7-inbound-outbound.md, docs/tasks/phase-8-authentication.md
- Created: 2026-10-11
- Started: 2026-10-11
- Completed: 2026-10-15

## Goal

Correct independently observed frontend visual and usable-interaction deviations across the previously delivered React/TypeScript pages, using approved Figma components and layouts while preserving the working FastAPI, authentication, token, and RBAC contracts. Distinguish feasible frontend parity from design elements that require new backend capabilities.

## Context

- Figma file: `IoHM7Md1WkS8nt1kH4jrO4`. Approved nodes: shell `5:3`; dashboard `14:2`; products `22:70`, `22:362`, `26:104`; inventory `29:164`, `29:384`; warehouses `33:6`, `34:89`, `35:150`; movement `36:10`, `36:247`, `37:104`, `37:248`; auth `40:2`, `40:39`, `40:67`, `40:103`.
- Initial read-only Figma audit identified shared control/form typography and width mismatches, incomplete products/inventory/warehouse/movement views, inconsistent action labels and missing frontend-driven previews and filters. This audit is design/source comparison; runtime browser pixel parity remains unverified.
- The existing backend does not expose warehouse operational status, movement timestamp/actor/reference in transaction responses, password recovery routes, warehouse capacity/region, or trends. Do not fabricate any of these values or create nonfunctional links.
- Earlier completed pagination task `docs/tasks/fix-product-pagination.md` is a separate checkpoint; preserve its all-products join fix.

## In Scope

- Adjust existing frontend shared CSS/UI primitives and local font delivery to match the approved Inter-based visual system, without a new UI framework.
- Align existing page/form/list/detail layouts, headings, data columns, responsive behavior, filtered/paginated views, loading/empty/error states, and accessible controls to available real API fields.
- Where data is already available, implement derived zero/low-stock statuses, meaningful warehouse summaries, movement stock preview, and Figma-appropriate action labels with no alteration to business rules.
- Improve shell/auth presentation only where compatible with supported routes and authentication behavior; preserve frontend permission visibility and backend authority.
- Add/adjust focused frontend tests as warranted. Record actual Figma comparisons, static checks, browser verification performed, and unresolved unsupported backend requirements.

## Out of Scope

- Changing FastAPI routes, schemas, database, token storage key `smart-warehouse-token`, login/refresh/logout behavior, backend RBAC, API client contracts, package manager, or application architecture.
- Fake product/stock/transaction data, invented history fields or capacity trends, fabricated reference IDs, unsupported status toggles, fake forgot/reset-password functionality, and nonfunctional settings/support destinations.
- Legacy shared-task files under `docs/plans/`, unrelated local changes, destructive Git commands, push/deploy, and commits of this task's new implementation without a separate explicit approval.

## Acceptance Criteria

- [x] AC-1 — Shared Inter typography, controls, table, PageHeader, spacing and form width respond consistently and visually follow approved Figma without regressing accessibility.
- [x] AC-2 — Product list/create/edit align with Figma; usable filters, true product paging, real supplier/status fields, and preservation of existing description/API behavior are verified.
- [x] AC-3 — Inventory overview and stock detail show correct zero/low/healthy distinctions and other available data in Figma-aligned layouts without invented history.
- [x] AC-4 — Warehouse list/detail/create/edit use Figma-aligned forms, location and inventory summaries; no fictitious warehouse operating status, capacity, or region is represented as fact.
- [x] AC-5 — Inbound/outbound list/create show Figma-aligned fields and interactions, supported filtering and stock-after-movement preview; backend stock validation remains authoritative.
- [x] AC-6 — Dashboard, shell and auth visual details match supported Figma elements, preserving navigation, routing, RBAC and existing auth semantics.
- [x] AC-7 — Actual frontend API flows use real responses with stable error/loading states; focused tests and full frontend build/TypeScript regression pass; backend tests pass if touched or as integration baseline.
- [x] AC-8 — Each approved screen receives source/Figma verification and relevant runtime browser inspection; unsupported backend fields and any unverified browser scenarios are explicitly marked NOT VERIFIED rather than claimed DONE.

## Verification Commands

### Focused

- Run relevant `client/tests/` tests, plus any new targeted regression tests for filters, paging, stock derivation and form submission.
- Compare implementation with the approved Figma node design contexts and screenshots for all affected screens.
- Inspect live frontend in browser at desktop 1440px and narrower widths where browser integration is available; test authenticated navigation, forms and states without inventing data.

### Regression

- In `client/`: `npm.cmd run build`.
- In `client/`: `npx.cmd tsc --noEmit`.
- In repository root: `python -m pytest -q` if applicable; use `.venv/Scripts/python.exe` when available.

### Static and Diff

- `git diff --check`
- `git status --short`
- Review every changed file against task scope and check that no tracked changes from other tasks were overwritten.

## Progress Log

### 2026-10-11 — Created

- User explicitly approved the remediation task path and use of native subagents; separate prior completed work was committed in three local logical checkpoints before remediation.
- Native read-only Figma review identified frontend-solvable gaps and missing backend response fields. No frontend remediation implementation has started yet.

### 2026-10-11 — READY -> IN_PROGRESS

- Confirmed all seven declared phase dependencies have status DONE; all required approved Figma nodes and the remediation work are scoped in the single selected task.
- Frozen Goal, Context, In Scope, Out of Scope, Acceptance Criteria and Verification Commands. Native implementation workstreams will be scoped to disjoint frontend files; only the main agent updates this task record.
- Preserved all unrelated dirty/untracked files. No push, history changes, backend implementation, or new-package additions are authorized.

### 2026-10-14 — Resumed implementation and verification scope

- Continued this single task from its frozen IN_PROGRESS baseline. Reconfirmed all seven declared phase dependencies are DONE. Preserved the existing frontend remediation and all unrelated dirty/untracked files; no legacy shared-task file was read or changed.
- Reproduced two missing supplier-choice regressions with 101 products: client role cannot access a supplier referenced only on page 2; admin has the same problem when the supplier-name lookup fails. Both tests failed on the missing second supplier before implementation and passed after the fix.
- ProductsPage now derives stable supplier/category references from public productsAll independently of visible/filter result rows, preserves selected values, keeps server pagination for unfiltered product reading, displays lookup loading/error/retry, and never requests the supplier directory for client role. A separate regression reproduced the missing category reference beyond the first directory page and passed after the same reference-source correction.
- ProductFormPage now preserves a selected category/supplier absent from the first directory lookup page using its real ID fallback. The regression failed before this correction. Existing product descriptions and payload fields are preserved on create/edit.
- Reproduced duplicate DELETE submission while a request was pending (2 calls rather than 1), then guarded the mutation and added busy/disabled state to ConfirmDialog, including cancellation while busy. The regression passed after correction; no real product was deleted.
- Added locally served Inter v4.1 variable WOFF2 and its unmodified SIL OFL license. Source: https://github.com/rsms/inter/tree/v4.1 . Font size 352240 bytes; SHA-256 693B77D4F32EE9B8BFC995589B5FAD5E99ADF2832738661F5402F9978429A8E3.
- Extended the existing frontend hook-host tests using the real page effects/API client with controlled network fixtures. Added assertions for cross-page filters, stable choices after empty results, failed lookup retry, form payload/description preservation, movement stock preview, stale-response exclusion, authoritative outbound rejection, protected 401/403/503 handling, zero/null warehouse coordinates, and administrative action visibility. Fixtures are test-only, never runtime data.
- This continuation edited only ProductsPage.tsx, ProductFormPage.tsx, shared/ui/ConfirmDialog.tsx, shared/styles/base.css, shared/assets/fonts/InterVariable.woff2 and OFL.txt, tests/products-warehouses-remediation.test.js, and this task document. Other pre-existing changes remain owned by their original work.

### 2026-10-14 — IN_PROGRESS -> VERIFYING

- Implementation changes above are ready for regression and independent review. Baseline and AC text remain frozen; every AC remains unchecked because visual/runtime coverage is incomplete. No commit, push, deployment, backend/API/auth/RBAC/token-storage change or new package was performed.
- Verification is NOT COMPLETE. Await the actual regression results recorded below and the missing browser scenarios; this transition is not DONE or APPROVED.

### 2026-10-14 — VERIFYING -> IN_PROGRESS (source review findings)

- Reopened implementation for verified in-scope source findings: `ConfirmDialog` currently relies on `<dialog open>` without a modal/focus lifecycle; recovery screens solicit credentials despite absent recovery APIs; the decorative remember-login indicator and nonfunctional notification control can mislead users. Review the action-button icon mismatch against approved Figma without compromising semantics or accessibility.
- Preserve all existing dirty changes, API/auth/RBAC contracts, and the frozen task baseline. Browser inspection remains NOT VERIFIED because the native browser tool currently fails before executing its first JavaScript command (`failed to write kernel assets: The system cannot find the path specified. (os error 3)`).
- Only the selected remediation task is reopened. No commit, push, deployment, or backend changes are authorized.

### 2026-10-15 — Three authorized remediation rounds and independent browser review

- Continued the same IN_PROGRESS task and frozen scope from HEAD `3404b6b`. Used exactly one native subagent for the three fix/test rounds; the main agent independently reviewed source, Figma and rendered browser behavior. No new executable task or phase was started.
- Round 1: separated failed product deletion feedback from list-load errors and rendered it inside ConfirmDialog, keeping the table intact; added explicit category/supplier directory retry. Three new behavior regressions failed before the fixes and passed afterward. Replaced product edit/delete and warehouse action drawings with downloaded local Figma assets, keeping action labels, permissions and destinations.
- Round 2: restored the approved dashboard and warehouse KPI indicators and product/warehouse pagination chevrons. Reused byte-identical downloaded assets without editing SVG contents or overriding intrinsic dimensions.
- Round 3: actual 390px browser inspection found nameless collapsed sidebar links and horizontal document overflow on products, warehouse list and warehouse detail. Added persistent Vietnamese navigation/account labels, route-derived area breadcrumbs, correct active/inactive sidebar assets, inventory indicator/action/pagination assets, semantic visually-hidden captions, and flat, positioned DataTable scroll wrappers. Seven new regression cases failed before the accessibility/breadcrumb fixes and passed afterward.
- Main-agent browser measurements confirmed the overflow correction: products document width equals viewport width (390px in the recorded sample); warehouse list/detail document width equals their 375px layout viewport with a scrollbar. Tables retain their own horizontal scrolling. Before the fix, those document widths were 1031px, 1021px and 847px respectively.
- Native Brave access was recovered, and the user logged in manually. API was initially not listening; the existing local API and Vite servers were started for verification after confirming database connectivity and CORS. Brave input/focus snapshots later became inconsistent, so verification continued through the connected in-app browser after a separate manual user login. Browser screenshots that showed another foreground app were discarded as visual evidence.
- Actual in-app verification reached all approved screen variants with real API reads, at 1440x1024 and representative 390x844 layouts. Full rendered parity is not approved: independent final review found the remaining Auth deviations listed below. All three authorized fix/test/review rounds have been used; no fourth implementation round was performed.
- No business records were created, modified or deleted during browser verification. Real create/update/delete and movement submission scenarios remain NOT VERIFIED. Unit/hook-host network fixtures are regression evidence only, not live end-to-end mutation evidence.
- Status remains IN_PROGRESS; review is CHANGES_REQUIRED. AC-1, AC-3, AC-4 and AC-8 have combined source/Figma, regression and relevant browser evidence. AC-2, AC-5 and AC-7 remain unchecked pending live mutation-flow verification; AC-6 remains unchecked for confirmed Auth visual deviations. No completion date or DONE transition is recorded.
- Preserved all pre-existing unrelated tracked/untracked changes, including the legacy production plan, `.vscode/`, report/testing/rules documents, and `.docx`. `LegacyProductsPage.tsx` was already untracked before this continuation and was left untouched. No staging, commit, push, deployment, backend/API/AuthProvider/router/permission-helper changes or package changes were made.

### 2026-10-15 — Approved additional Auth correction round

- The user explicitly approved one additional fix/test/review round for the two outstanding Auth visual findings. This extends the previous three-round execution limit only; the selected task, frozen baseline and API/authentication constraints remain unchanged.
- Continue from IN_PROGRESS. The native implementer is limited to `client/src/pages/AuthPages.tsx` and `client/src/pages/auth.css`, with focused test changes only if needed. Main agent owns this task record and independent browser/Figma review. Preserve all pre-existing dirty changes; no staging/commit/push is authorized.
- Fresh Figma design contexts and screenshots confirmed the desktop Auth card targets at 1440x1024: login top 206px/height 550px, forgot top 254px/height 440px, reset top 216px/height 520px, error top 180px/height 610px. All card widths are 420px; login/error CTA contents align to the left inset.

### 2026-10-15 — IN_PROGRESS -> VERIFYING (additional Auth round)

- Native implementation changed only the existing Auth files: an error-state presentation class, per-variant responsive desktop offsets, the error card's minimum height, and Auth-scoped left alignment for full-width CTA content. Authentication handlers and shared Button styles remain unchanged.
- Native verification reported build/TypeScript/diff-check PASS and the corrected full frontend suite 87 passed. Main-agent rendered browser review is now in progress; this transition does not approve AC-6 or complete the task.

### 2026-10-15 — Additional Auth round verification and scoped review completed

- Main-agent independent source/browser review confirmed both approved Auth findings are resolved. The full task remains VERIFYING because live business mutation scenarios under AC-2, AC-5 and AC-7 are still pending; no DONE or overall APPROVED claim is made.
- At an explicit 1440x1024 browser viewport, real rendered card rectangles match fresh Figma contexts: login x=770/y=206/w=420/h=550; forgot x=770/y=254/w=420/h=440; reset x=770/y=216/w=420/h=520; real invalid-login error x=770/y=180/w=420/h=610. Auth CTA computed `justify-content:flex-start` and 14px inline padding. The existing locally served brand SVG loaded at its intrinsic 22x22 dimensions.
- Submitted only deliberately invalid, non-user login test credentials to exercise the actual API error. Editing the fields removed the alert/error-specific class and restored normal 550px height/y=206; both credential inputs were cleared after verification. No business records or authentication settings were modified.
- Confirmed responsive error rendering at 390x844 (no horizontal overflow; card bottom approximately 730px within the 844px document) and 768x1024 (610px card ending at y=929). At 1024x600 and 1440x600, desktop card top clamps to 32px, bottom is 642px and the document extends to 674px, so lower content remains reachable through normal vertical scrolling. Both recovery screens still have zero credential fields and no protected AppShell.
- Additional minimum-width observation: at a nominal 320px desktop-emulation viewport with a classic 15px vertical scrollbar, layout client width is 305px while the unchanged global body minimum is 320px. The document can therefore scroll horizontally by 15px; the 288px Auth card's right edge is 304px and its fields remain within the layout viewport. This inherited global-width limitation was not changed by the approved two-finding Auth round, and no universal 320px parity claim is made.
- Native implementer ran build, TypeScript, corrected full frontend suite (87 passed, 0 failed/skipped/cancelled), and diff check. Main agent independently reran build (89 modules), `npx.cmd tsc --noEmit` and `git diff --check`: all PASS. Backend code was untouched and its previously recorded 54-pass baseline was not rerun for these presentation-only changes.
- Only `client/src/pages/AuthPages.tsx` and `client/src/pages/auth.css` were edited by the native implementer in this additional round; main agent updated only this selected task record. No new framework/assets/dependencies or brittle decorative CSS tests were introduced. Shared Button, authentication handlers, API contracts, token storage, role permissions and other dirty changes remain unchanged.
- New ignored screenshot evidence: `client/node_modules/.tmp/remediation-browser/auth-login-aligned-desktop.jpg`, `auth-error-aligned-desktop.jpg`, `auth-error-aligned-mobile.jpg`. The earlier screenshots remain historical before-correction evidence. Viewport override was reset and browser test inputs cleared. No files staged, committed or pushed.

## Verification Evidence

### Focused

- 2026-10-14: final focused remediation suite contains 25 passing tests. Together with the existing 17 pagination tests and 17 helper/auth/API assertions, all frontend tests pass: 59 tests, 0 failures, 0 skipped.
- Product reference and duplicate-deletion regressions were observed failing before their respective fixes. Movement preview, async stock errors/stale responses, protected-load errors, form payloads, permission visibility and existing all-products joins were exercised through real page effects and the unchanged API client against controlled responses. These tests do not run a DOM or prove browser/API end-to-end flows.
- Reproducible PowerShell preparation in client/ (all output stays in ignored node_modules/.tmp):

```powershell
npx.cmd tsc --project tsconfig.app.json --noEmit false --module commonjs --moduleResolution bundler --outDir node_modules/.tmp/remediation-c/src --rootDir src
$remediationTests = Get-ChildItem tests/*.test.js | ForEach-Object { $_.FullName }
npx.cmd tsc --ignoreConfig --allowJs --checkJs false --module commonjs --moduleResolution bundler --target es2022 --jsx react-jsx --esModuleInterop --skipLibCheck --outDir node_modules/.tmp/remediation-suite --rootDir . src/vite-env.d.ts @remediationTests
$env:PRODUCT_PAGINATION_SOURCE_ROOT = './node_modules/.tmp/remediation-c/src'
$compiledHelpers = Get-ChildItem node_modules/.tmp/remediation-suite/tests/*.test.js | Where-Object { $_.Name -notin 'product-pagination.test.js', 'products-warehouses-remediation.test.js' } | ForEach-Object { $_.FullName }
node --test @compiledHelpers tests/product-pagination.test.js tests/products-warehouses-remediation.test.js
```

- Tooling probes initially failed on removed TypeScript node10 resolution and mixed CommonJS/import.meta execution of product-pagination.test.js and products-warehouses-remediation.test.js; the correct bundler resolution plus source ESM host-test invocation above passes. A Windows literal wildcard probe collected 0 tests and is not counted as verification.
- Figma MCP get_design_context returned reference code and actual screenshots for every approved node in file IoHM7Md1WkS8nt1kH4jrO4: shell 5:3; dashboard 14:2; products 22:70, 22:362, 26:104; inventory 29:164, 29:384; warehouses 33:6, 34:89, 35:150; movement 36:10, 36:247, 37:104, 37:248; auth 40:2, 40:39, 40:67, 40:103. No sparse-response warning was returned. This is source/design inspection, not a claim of full rendered parity.
- Source/design comparisons confirmed the Inter typography, 38px shared controls, 26px headers, 18px form-card padding, paired fields, inventory status sections, warehouse location/summary structure and movement stock-preview sections. Unsupported warehouse status/capacity/region, movement history timestamps/actor/reference, trends and recovery APIs remain unavailable; no corresponding runtime values were invented.
- Actual native Brave screenshot/AX inspection reached http://localhost:5173/login with the real application, blank credential fields and the brand/card structure. Browser zoom was 90%; no exact 1440px or narrow viewport was verified. There was no authenticated session. The in-app browser was unavailable; a separate native Brave window was used. A subsequent viewport inspection was interrupted when the window was minimized. Authenticated screens, form submissions, visual asset geometry, keyboard/focus behavior and mobile parity remain NOT VERIFIED. A DevTools indicator showed 3 errors, whose details were not inspected, so no clean-browser-console claim is made.

### Regression

- Pre-remediation baseline: backend `54 passed`; frontend production build passed; `npx.cmd tsc --noEmit` passed; previously isolated product-pagination tests `17 passed`. These do not verify the new UI task.
- 2026-10-14 final source: npm.cmd run build passed (79 modules; local InterVariable-DiVDrmQJ.woff2 352.24 kB emitted); npx.cmd tsc --noEmit passed; full frontend execution above passed 59 tests.
- 2026-10-14: .venv/Scripts/python.exe -m pytest -q passed: 54 tests, 3 warnings. Existing dependency warnings concern Starlette/httpx and asyncio.get_event_loop_policy; the additional PytestCacheWarning reports a local OneDrive cache-directory creation conflict. No backend source or dependencies were changed.
- Actual local backend readiness returned 200 with status ready. GET /products?page=1&page_size=100 and GET /categories?page_size=100 each returned page 1, page_size 100, total 1 and one real item. These endpoint smoke results are separate from fixture-based regression tests and do not verify protected frontend flows or the 101-product browser scenario.

### Static and Diff

- 2026-10-14: git diff --check passed. git status --short was inspected against the initial dirty file list. No API client, app auth/router, permissions, backend, package manifest or lockfile diff was introduced. No files were staged or committed.
- Font binary signature is wOF2, file length is 352240 bytes, and SHA-256 matches the value in Progress Log. Its OFL license is included locally. The production build resolves the local URL successfully; actual glyph rendering and per-screen geometry still need browser verification.
- Existing unrelated tracked docs/superpowers/plans/2026-09-04-phase-1-production-ready.md and all existing unrelated untracked files/directories remain untouched. Existing remediation files not edited in this continuation also remain unchanged.

## Review Result

- Result: APPROVED (2026-10-15, main-agent independent review of native implementation, supported Figma/source comparisons, real browser/API flows and regression evidence). See the final AC-2/5/7 continuation below; earlier partial-verification entries are retained as history, not current blockers. Approval covers the frozen frontend capability-preserving scope, not unsupported backend features or unexecuted browser scenarios.
- Resolved: failed DELETE feedback hidden behind the modal; unretryable product directory names; unnamed collapsed navigation/account controls; table hidden-label overflow; mismatched hand-drawn action icons, active navigation icons, KPI indicators and pagination assets. Recovery routes now explain unavailability before soliciting any credentials; unsupported Topbar controls are explicitly disabled. These are supported by source, focused regression and the browser evidence below.
- P3 Auth card placement: RESOLVED by the approved additional round. Actual desktop login/forgot/reset/error card rectangles now match their four approved Figma targets; shorter desktop windows retain a 32px top inset with reachable vertical overflow.
- P3 Auth CTA alignment: RESOLVED by Auth-scoped full-width button alignment and 14px inline padding. Shared Button styles and authentication behavior were not changed.
- Earlier missing-verification checkpoint, superseded by the final continuation below: live create/update/delete and inbound/outbound submissions, busy modal behavior during a real request, and separate warehouse/client browser sessions. At that checkpoint the database had one product/warehouse/stock record and no transactions. Live cross-page and separate-role browser scenarios remain NOT VERIFIED; the final continuation records the actual mutation, populated-row and zero-stock coverage gained afterward.
- Existing API limitations remain: only the first 100 directory names are returned by the unchanged category/supplier helpers; real referenced later-page IDs retain usable fallbacks. Entirely unreferenced later-page directory choices are not added. Warehouse operational status/capacity/region, historical actor/time/reference responses, trends and recovery APIs remain unsupported. No such values or destinations were fabricated.

## 2026-10-15 — Verification and acceptance evidence before AC-2/5/7 continuation

### Fresh automated verification

- Main agent independently reran `npm.cmd run build`: PASS, 89 transformed modules; local Inter font emitted successfully.
- Main agent independently reran `npx.cmd tsc --noEmit`: PASS.
- Main agent rebuilt and ran the complete frontend suite: 87 reported tests, 87 passed, 0 failures/skips/cancellations.
- Main agent independently reran `.venv/Scripts/python.exe -m pytest -q`: 54 passed, 3 existing warnings (Starlette/httpx deprecation, asyncio policy deprecation, OneDrive pytest cache conflict).
- Main agent ran `git diff --check`: PASS. Diff inspection found no changes in backend, API client, AuthProvider/router, permission helper, package manifest or lockfile.
- The earlier evidence recipe needs an additional ESM-host exclusion now that `ui-shell-remediation.test.js` exists. Its compiled CommonJS version fails under the ESM test invocation (`exports is not defined`); the corrected, freshly executed recipe is below. The historical 59-test result above is retained as history; 77 and 80 were intermediate observed suite counts, and 87 is the current runner result.

```powershell
npx.cmd tsc --project tsconfig.app.json --noEmit false --module commonjs --moduleResolution bundler --outDir node_modules/.tmp/remediation-c/src --rootDir src
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$remediationTests = Get-ChildItem tests/*.test.js | ForEach-Object { $_.FullName }
npx.cmd tsc --ignoreConfig --allowJs --checkJs false --module commonjs --moduleResolution bundler --target es2022 --jsx react-jsx --esModuleInterop --skipLibCheck --outDir node_modules/.tmp/remediation-suite --rootDir . src/vite-env.d.ts @remediationTests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$env:PRODUCT_PAGINATION_SOURCE_ROOT = './node_modules/.tmp/remediation-c/src'
$compiledHelpers = Get-ChildItem node_modules/.tmp/remediation-suite/tests/*.test.js | Where-Object { $_.Name -notin 'product-pagination.test.js', 'products-warehouses-remediation.test.js', 'ui-shell-remediation.test.js' } | ForEach-Object { $_.FullName }
node --test @compiledHelpers tests/product-pagination.test.js tests/products-warehouses-remediation.test.js tests/ui-shell-remediation.test.js
```

### Browser and Figma evidence

- Figma MCP `get_design_context`, with screenshots, was freshly inspected for all 18 approved nodes in this continuation. The design file was not modified.
- Desktop viewport override: 1440x1024; narrow override: 390x844. Overrides were reset afterward. These are explicit browser viewport dimensions, not native-window screenshot dimensions. Layout client width can be 375/1425 when a vertical scrollbar occupies 15px.
- Shell/dashboard: real admin navigation, active destination, disabled unsupported Topbar controls, real stats/stock/warehouse data and empty recent movements were inspected. Sidebar width=248px, h1=26px, shared form controls=38px. Inter and #F7F9FB application background were confirmed through rendered styles. KPI assets render 8x8; sidebar/search/notification assets 20x20; brand mark asset 22x22. All inspected images loaded with nonzero intrinsic dimensions.
- Products list/create/edit: real product/category/supplier reads, ID-backed form hydration, search with empty results, stable options and reset, both forms' 1128px desktop width, accessible action labels, edit/delete assets=16x16 inside 28px buttons, and pagination chevrons=16x16 inside 32px buttons were inspected. The preserved description field is an intentional capability-preserving addition to the reference forms. Create/update/DELETE submission is NOT VERIFIED live.
- ConfirmDialog: real native `:modal` state, initial Huy focus, Tab between actions, Escape cancellation and trigger-focus restoration were observed without deleting any product. Boundary Tab/Shift+Tab can move focus into browser chrome, but did not establish access to an underlying application control; no stricter focus-wrap claim is made. Busy/error request cases have hook-host regression evidence only.
- Inventory overview/detail: real quantity 25 and threshold 10, healthy status, comparison meter, filters, layout and explicitly unavailable history were inspected. Refresh at `/inventory/1/1` restored the protected page; backend access logs recorded real `GET /api/v1/auth/me` responses. Zero/low distinctions are covered by focused tests; their live browser examples are NOT VERIFIED with the current dataset.
- Warehouse list/detail/create/edit: real stock totals, location null fallbacks, summaries, form hydration, filters, both form layouts and real product navigation were inspected. Unsupported operating status/capacity/region are absent. No warehouse mutation was submitted.
- Inbound/outbound list/create: both real empty-list states and both form layouts were inspected. Selecting the real warehouse/product and quantity 5 produced inbound preview 25 + 5 = 30; selecting outbound quantity 30 produced preview 25 - 30 = -5 and a Vietnamese warning. No stock-changing request was submitted. Populated transaction rows and authoritative live rejection remain NOT VERIFIED; existing regression/backend tests cover those cases.
- Authentication: the user logged in manually through the real API; backend logs recorded successful `POST /api/v1/auth/login` and `GET /api/v1/auth/me`. Authenticated `/login` returned to dashboard. Actual logout returned to `/login`; refresh stayed logged out; direct unauthenticated `/inventory/1/1` redirected to `/login`. Both recovery routes rendered outside AppShell, with no credential fields and explicit unavailability. A deliberately invalid, non-user test account produced the real Vietnamese invalid-credentials alert. Test inputs were cleared afterward.
- `/` and a deliberately unknown local route both resolved deterministically to `/dashboard` in the admin session. Warehouse/client visibility has focused tests for the real Sidebar component; separate browser sessions for those roles remain NOT VERIFIED.
- Native Brave's earlier Console errors were observed as API connection-refused failures before API restart, together with Vite connection loss before the frontend restart. The inspected in-app browser console reported no captured warning/error entries during the final check; this does not assert every possible browser state is error-free.
- Local generated screenshot evidence (ignored, not source files): `client/node_modules/.tmp/remediation-browser/products-desktop.jpg` and `auth-login-desktop.jpg`. They illustrate the final product layout and the remaining normal-login alignment finding. No screenshot/build/cache artifact is staged.

### AC assessment

| Criterion | Assessment | Evidence and limit |
| --- | --- | --- |
| AC-1 | VERIFIED | Shared geometry/assets/styles, modal keyboard/cancellation and corrected 390px narrow layouts observed; supporting regression passes. Corrected Auth placement is verified under AC-6; the inherited nominal-320px scrollbar/minimum-width limit is documented above. |
| AC-2 | PARTIAL / NOT VERIFIED | List/filter/form source, tests and browser reads verified; live product create/update/delete preservation still pending. |
| AC-3 | VERIFIED | Shared status derivation and meter tested; real overview/detail render inspected, unsupported history not fabricated. Live zero/low samples not observed. |
| AC-4 | VERIFIED | All four warehouse route variants inspected against Figma; real location/stock summaries and absence of fictitious fields confirmed. Mutation execution is outside this checked layout/data assessment. |
| AC-5 | PARTIAL / NOT VERIFIED | Both directions' forms, empty lists and real previews inspected; live submissions/populated rows not verified. |
| AC-6 | VERIFIED | Prior routing/auth/admin shell evidence plus the approved additional Auth round's exact desktop geometry, CTA alignment, real invalid-login error and responsive checks. Unsupported recovery UI remains an explicit capability-driven deviation. |
| AC-7 | PARTIAL / NOT VERIFIED | Real read/auth responses and regression verified; live business mutation flows still pending. |
| AC-8 | VERIFIED | Every approved screen variant received fresh source/Figma comparison and relevant runtime inspection; limitations and deviations explicitly recorded. This is comparison coverage, not a parity approval. |

### Files changed in this continuation

- Existing task-owned frontend files: `client/src/pages/ProductsPage.tsx`, `WarehousesPage.tsx`, `DashboardPage.tsx`, `WarehouseDetailPage.tsx`, `InventoryPage.tsx`, `dashboard.css`, `inventory.css`, `products-list-remediation.css`, `warehouses-list-remediation.css`; `client/src/shared/layout/Sidebar.tsx`, `UserMenu.tsx`, `Breadcrumbs.tsx`; `client/src/shared/ui/DataTable.tsx`; `client/src/shared/styles/base.css`; `client/tests/products-warehouses-remediation.test.js`, `ui-shell-remediation.test.js`.
- New local Figma SVGs under `client/src/shared/assets/figma/`: `edit.svg`, `delete.svg`, `kpi-blue.svg`, `kpi-green.svg`, `kpi-warning.svg`, `product-previous.svg`, `product-next.svg`, `dashboard-inactive.svg`, `products-active.svg`, `inventory-active.svg`.
- Task record: `docs/tasks/ui-figma-remediation.md`. Existing dirty remediation files outside this list were inspected/preserved, not rewritten in this continuation. The full working tree remains dirty and uncommitted.

## Completion Evidence

- Completed on 2026-10-15 after the final review below. All eight frozen ACs have supporting source/design, relevant rendered-browser and automated evidence; AC-2/5/7 include real local API mutations and failure/loading/retry observations, not only fixture tests/build.
- No backend, API contracts, auth/router/RBAC/token key, dependencies or package-manager changes. No staging, commit, push or deployment. Existing unrelated dirty files remain unchanged.
- Known capability and verification limits remain explicit in Review Result and the final continuation. Completion does not claim every API failure, role session, 101-product browser dataset or nominal-320px emulated-scrollbar layout was exercised live.

## 2026-10-15 — AC-2, AC-5 and AC-7 continuation

### VERIFYING -> IN_PROGRESS

- User explicitly requested completion of AC-2, AC-5 and AC-7. Live browser product creation returned 201; updates returned 200 and preserved supplier/category IDs, description and active state. Duplicate SKU returned the real 409 and preserved editable form values. With temporary network latency, real mutation inputs, cancellation and submit controls were disabled while pending; latency is a browser-only verification setting, not a mocked response.
- Native source review confirmed a remaining Vietnamese-text defect: failed product DELETE forwards the backend English detail to the modal. The existing regression incorrectly expected that English text. A read-only in-memory expectation for Vietnamese failed against the current implementation. Reopened implementation for a scoped ProductsPage deletion-message correction and its regression only; preserve API calls, 401/logout behavior and modal/list lifecycle.
- Created clearly tagged local test products `AC-20261015-CRUD` (ID 2, no inventory references) and `AC-20261015-MOVE` (ID 3, movement verification). Existing DEMO-001 is unchanged. No DELETE has been submitted; per-action confirmation for ID 2 is pending. Movement records cannot be removed through the existing API and will be explicitly reported, not silently deleted through the database.
- Frozen scope and AC text are unchanged. No backend/config/API/auth/RBAC change, staging, commit, push or deployment is authorized.

### IN_PROGRESS -> VERIFYING

- Native implementer corrected only product DELETE feedback in `ProductsPage.tsx` and the focused remediation tests. Four regression cases (409, 403, 404 and network failure) failed before the message correction and passed after it. They assert Vietnamese feedback, retained modal/table and recovery. The DELETE endpoint, request payload, 401/logout and modal controls remain unchanged.
- Implementation is stable for main-agent independent source and browser verification. Native-reported automated results are not substituted for the independent results below.

### VERIFYING -> REVIEWING

- Main agent independently reran the full frontend recipe above after the correction: 90 reported tests, 90 passed, zero failed/skipped/cancelled; `npm.cmd run build` passed (89 modules); `npx.cmd tsc --noEmit` passed. This continuation's fresh backend baseline was 54 passed with the same 3 existing warnings. `git diff --check` passed.
- Real browser/API verification used the unchanged application at `http://localhost:5173`, the existing backend at port 8000 and the user's manually authenticated admin session. CDP output was reduced to endpoint/status and rendered DOM state; no authorization headers, token or credentials were printed. Temporary latency/offline settings changed network transport only, never response bodies or business data. They were restored to online/zero latency.
- Product ID 2: POST `/products` returned 201; edit hydration restored the saved description, category/supplier IDs, unit, threshold and status. PUT returned 200, changing the name and active state without losing description; combined SKU/category/supplier/inactive filters returned only that product. A real duplicate-SKU PUT returned 409, retained the draft and showed Vietnamese feedback. A subsequent successful update persisted a new Vietnamese description, independently confirmed through GET.
- User explicitly confirmed permanent deletion of ID 2 at action time. The browser DELETE returned 204, closed the modal and refreshed the list; independent GET `/products/2` returned 404. During the delayed real DELETE, `dialog:modal` remained true, `aria-busy` was true, both buttons were disabled, focus was on the dialog and Escape did not close it. Only this newly created test product was removed; it cannot be recovered through the current API.
- Product ID 3 (`AC-20261015-MOVE`): real inbound preview 0 + 2 = 2; POST `/inbounds` returned 201. The inbound list displayed transaction ID 1, correct SKU/product/warehouse and +2; combined search/warehouse/product filters worked. Real outbound preview 2 - 3 = -1 showed a warning but allowed backend validation. POST `/outbounds` returned 409, kept the form values, refreshed stock to 2 and produced Vietnamese feedback; the outbound list was still empty. A valid quantity 2 then previewed 2 - 2 = 0 and POST returned 201; the list showed transaction ID 2 and -2. The inventory screen confirmed this product at 0 and DEMO-001 unchanged at 25. No duplicate transaction was introduced by the rejected request.
- Delayed real create/inbound/outbound submissions visibly disabled fields, cancel and submit, with the Vietnamese processing label. Transport-offline navigation to inbound rendered its Vietnamese error/retry state. Restoring transport and clicking retry rendered loading, then the real populated table without logging out. No runtime API response was mocked.
- Both populated movement lists were inspected at 1440x1024 and 390x844; their document width equalled the 390px client viewport at narrow size. Earlier all-18-node Figma/source and browser layout evidence remains applicable: this round changes only error wording, not layout/assets. Unsupported transaction timestamp/actor/reference response fields remain absent, not fabricated.
- One attempted outbound verification was interrupted by development-server reload while the implementation changed; no outbound response was captured for that attempt, so it is not counted as a request/result. The stable-source attempt above is the observed 409. Two selector probes failed because accessible matching differed from their guesses; fresh DOM inspection resolved them and no business operation was blindly repeated.
- Local test footprint: ID 2 was deleted with approval; ID 3 remains with stock 0 in warehouse 1, inbound ID 1, outbound ID 1 and stock transaction IDs 1/2. Current API offers no movement cleanup/undo. No direct database cleanup was performed and existing product/stock records were not changed. The test product description explicitly identifies it as local verification data, not real operations.
- Ignored screenshot evidence: `product-conflict-live.jpg`, `product-delete-confirm-live.jpg`, `product-deleted-live.jpg`, `inbound-created-live.jpg`, `outbound-rejected-live.jpg`, `outbound-created-live.jpg`, `inbound-populated-mobile.jpg`, under `client/node_modules/.tmp/remediation-browser/`. No generated evidence/build artifacts are staged.
- Remaining scenario limits: live 101-product cross-page browsing and separate warehouse/client browser sessions were not run; corresponding real component/API-client regression cases cover their logic. Live DELETE 403/404/409 and service-503 scenarios were not induced; localized failure/modal preservation is covered by focused tests. These limits are not presented as runtime verification. Browser/Figma evidence, real successful/rejected business requests and automated regressions together support review of the frozen ACs, not tests/build alone.

### Independent review and REVIEWING -> DONE

- Main agent independently reviewed the native correction and focused tests: status-specific DELETE wording is Vietnamese, unknown/network errors use a safe Vietnamese fallback, and 401 still takes the unchanged logout branch. No endpoint/payload, authorization, data mutation sequence or modal/list lifecycle was changed. The new tests use the backend's exact 409 detail and assert retained table/open modal, with separate 403/404/network assertions. No additional finding requires implementation in this round.
- Read-only persistence inspection independently confirmed warehouse 1/product 1 remains quantity 25 and product 3 quantity 0. Test inbound/outbound each have ID 1, quantity 2 and the submitted test references; exactly stock transactions 1 (inbound) and 2 (outbound) exist. No failed-outbound transaction or duplicate successful submission was stored.
- AC-2: VERIFIED by prior approved Figma/source/browser layout comparison, 101-product paging/filter regressions, real combined filters, create/edit hydration and payload persistence, real duplicate conflict, approved DELETE 204 and subsequent GET 404. Live 101-product browser paging remains explicitly unexecuted; it is not claimed as browser evidence.
- AC-5: VERIFIED by prior approved Figma/form comparison plus both directions' real previews, submissions, populated/filtered rows, backend 409 rejection with unchanged stock/no transaction, final stock 0 and desktop/390px render inspection. Unavailable history fields remain omitted.
- AC-7: VERIFIED by real reads/auth evidence and the real business writes/rejections/loading/modal/error/retry observations above, independent 90/90 frontend tests, production build, TypeScript, 54-test backend baseline and diff check. Controlled failure regressions remain distinct from live responses.
- AC-1/3/4/6/8 retain their previously recorded evidence. The native implementer did not approve its own work: the main agent performed this source/browser/test review. Exactly one native subagent was used; no new task or phase was started.
- Changed in this continuation: `client/src/pages/ProductsPage.tsx`, `client/tests/products-warehouses-remediation.test.js` and this selected task record only. All other remediation/unrelated working-tree changes were preserved. Final review result: APPROVED within the frozen scope; task transitions REVIEWING -> DONE with no commit/push.
