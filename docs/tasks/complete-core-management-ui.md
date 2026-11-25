# complete-core-management-ui — Hoàn thiện giao diện quản trị đang hoạt động

## Metadata

- Status: DONE
- Milestone: M2, exactly one executable task
- Plan: embedded M2 implementation plan below, identifier `complete-core-management-ui`; roadmap docs/superpowers/plans/2026-10-16-project-completion.md, section M2
- Specification: docs/superpowers/specs/2026-10-16-project-completion-design.md and proposed M2 interaction specification below
- Depends on: docs/tasks/define-completion-baseline.md
- Created: 2026-10-16
- Started: 2026-10-16
- Completed: 2026-10-17
- Implementation/design approval: APPROVED by human `duyệt` after the explicit M2 written-plan/interaction approval handoff; isolated worktree explicitly selected separately

## Goal

Đưa năm phân hệ người dùng, danh mục, nhà cung cấp, lịch sử giao dịch và nhật ký quản trị vào router/AppShell đang dùng, với giao diện tiếng Việt, API thật và quyền hiện có; không thay thế luồng xác thực hoặc triển khai nghiệp vụ của milestone khác.

## Context and authority

- Human approved creation of this exact previously nonexistent task by replying `duyệt` to the proposal naming docs/tasks/complete-core-management-ui.md. This permits task preparation, not unseen design approval, source implementation, other task creation or Git publication.
- Dependency M1 is DONE/APPROVED after human written-baseline review. Approved specification SHA256: 28339403DB1F3812396E2F7DE5A767072FB73FA54A82273DAE4EF1613EF03B17; roadmap SHA256: 0563304A518493AA8E27C90950DDD6F71288E30027BD09A1D8541CD8C6D92E5F. Do not modify them or reopen M1 to record M2 progress.
- Source baseline: feat/figma-ui-v2 at d8b3fa82b4b77cba5a3faed49738bf5ebe5c46d6. Existing M1 documents and unrelated untracked editor/report/spec/testing/legacy/personal files remain untouched and excluded. Revalidate actual HEAD and overlapping changes before implementation; never overwrite drift.
- Active client/src/App.tsx mounts app/AuthProvider.tsx and app/router.tsx. The five feature pages exist but import features/auth/useAuth.ts, which expects a different AuthContext and an ApiClient. Their query hooks also require QueryClientProvider. Existing app/Providers.tsx is query-only, but exports a global singleton cache; mounting it without session isolation is not a safe substitute for bridging the active auth session.
- Existing feature API factories already support the required backend contracts. Reuse their data/form/mutation logic while adapting context, shared UI and Vietnamese copy. Do not merely expose English legacy pages or mount the old auth/shell tree.
- Screens below have no newly approved dedicated Figma frames in this task. App Shell node 5:3 is the existing visual foundation, not proof of approval for invented management frames. This proposed interaction description must be approved before code.

## In Scope

- Five protected destinations inside the active AppShell, route-derived active navigation, Vietnamese breadcrumbs and role-aware links/actions described below.
- Adapt the existing feature pages, API factories, form schemas and related tests. Reuse shared Button/Input/Select/DataTable/PageHeader/FeedbackMessage/EmptyState/ConfirmDialog/Pagination and formatters; avoid page-specific duplicate foundations.
- A bounded API/context bridge and session-scoped query cache for these new routes, preserving the active AuthProvider, current central request generation/401 cleanup and token key.
- Vietnamese labels, confirmations, field validation, status/error/empty/loading messages and accessible names on all newly exposed UI, including reused nested inventory components.
- Server pagination, supported filters, all relevant category-parent/record label lookups, validation/conflict/forbidden handling, safe destructive-action confirmation and focus behavior.
- Frontend and guarded real-API/E2E regression, browser/responsive/accessibility checks and honest design-reference verification. Use exactly one reusable native implementer for later code and main independent review, maximum three correction rounds.
- This task is the only M2 execution/state/evidence/review ledger. Its embedded plan/spec are proposals until approved and frozen at READY -> IN_PROGRESS.

## Out of Scope

- Backend, database schema/migrations, API contract or RBAC grant changes; new user deletion/admin creation/password reset endpoints; password recovery redesign.
- New auth provider/login/token storage scheme, wholesale legacy Providers/AppShell migration, UI framework, package manager or dependency change.
- Redesigning existing approved dashboard/product/inventory/warehouse/inbound/outbound screens; unrelated legacy cleanup or compiling the unknown LegacyProductsPage.
- Transfers, B2B requests, AI/data preparation/forecasting/replenishment/anomalies/GIS/assistant, or starting M3-M12.
- Settings/support destinations, fabricated business records or fake success states. No real/demo database mutation for verification: use only the explicitly guarded disposable stack/database.
- Editing M1/history/shared plan progress, reading docs/plans/ or .env/secrets, deleting unknown files/resources, stage/commit/push/PR/deploy/merge/history changes without separate authority.

## Proposed M2 interaction specification

The following routes/labels/layout are engineering proposals for human review, not approved Figma exports. Preserve the existing sidebar, topbar, Inter, token colors, spacing and responsive shell. New pages use a PageHeader, a surface panel, shared forms/tables/feedback and server pagination, default page size 20. No second shell or page business logic in App.tsx.

| Destination | Visible label | Allowed route/read roles | Supported write actions |
| --- | --- | --- | --- |
| /users | Người dùng | admin | Create client/warehouse accounts, change supported managed roles, activate/deactivate; confirm role/status changes. Admin records remain protected per existing API. No user delete or admin-create action. |
| /categories | Danh mục | admin, warehouse, client | admin only: create/edit name and parent, delete with shared confirmation. Read-only roles see no mutations. Resolve parents/options beyond the first lookup page. |
| /suppliers | Nhà cung cấp | admin, warehouse | admin only: create/edit/delete existing name/email/phone/address fields. Preserve server search and conflict/in-use errors. |
| /transactions | Giao dịch | admin, warehouse | Read-only. Filter by warehouse/product/date range/type; show direction, product, warehouse, quantity, actor, linked movement and timestamp. No history edit/delete or invented transfer type. |
| /audit | Nhật ký quản trị | admin | Read-only. Existing action/target type/target ID filters; show only allowlisted safe before/after fields. Translate action/role/state codes for display; never dump arbitrary payload/password fields. |

Proposed navigation makes category read access visible to all three backend-authorized roles; this is a new navigation proposal, not a change to backend grants. Preserve all existing destinations/role behavior; add only these supported links. Sidebar must remain scrollable without hiding the account/logout control as item count grows. Do not use Settings/Support to stand in for these pages.

Keep current denied-route behavior from RouteGuard and login return location. Anonymous access redirects to /login; a 403 displays a Vietnamese authorization/error state without logging the user out. Clearing invalid authentication still follows the existing 401 policy. Filter submission resets the page to 1; empty last pages after deletion recover without a misleading missing-resource error. Mutation failure preserves entered values and actionable retry/confirmation state.

Existing Figma source: https://www.figma.com/design/IoHM7Md1WkS8nt1kH4jrO4/Smart-Warehouse-%E2%80%94-UI-UX-v2?node-id=5-3 . Before implementation, read the Figma design-to-code skill and get_design_context for file IoHM7Md1WkS8nt1kH4jrO4 node 5:3; record actual result. Use approved local SVGs or reviewed local additions, not temporary asset URLs or an icon framework. Dedicated management layouts are verified against the approved interaction description, not falsely reported as matching nonexistent Figma frames. Missing connector/reference evidence remains NOT VERIFIED until resolved or the human explicitly approves a documented alternative.

## Preserved API and permission contracts

- POST /api/v1/auth/login and GET /api/v1/auth/me; localStorage smart-warehouse-token, hydration/logout/invalid-token and stale-response guards unchanged.
- Users: GET/POST /api/v1/users, GET /api/v1/users/{id}, PATCH /api/v1/users/{id}/role and /status; backend ManagedRole accepts only client/warehouse. Do not offer unsupported admin promotion or invented deletion/password actions.
- Categories: GET/POST /api/v1/categories and GET/PUT/DELETE /api/v1/categories/{id}; existing parent, reference and conflict rules remain authoritative.
- Suppliers: GET/POST /api/v1/suppliers and GET/PUT/DELETE /api/v1/suppliers/{id}, existing search/pagination.
- History: GET /api/v1/transactions and GET /api/v1/transactions/{id}; current warehouse_id/product_id/created_from/created_to/transaction_type/page/page_size contract.
- Audit: GET /api/v1/audit-logs and GET /api/v1/audit-logs/{id}; existing action/target_type/target_id pagination/filter and safe field policy. No audit write API is added.
- Lookup GETs for existing products/warehouses/categories as currently supported; no mock labels or first-page-only correctness assumption.
- Frontend permission additions mirror app/auth/dependencies.py: catalog:read (all roles), supplier:write (admin), inventory:history:read (admin/warehouse), user:manage and audit:read (admin). Keep existing product:read alias/entries untouched; existing product:write covers category mutations as in the backend. Do not widen any backend permission.

## Future implementation file allowlist

The following source/test allowlist is approved for M2 implementation by the human handoff approval. This canonical task remains the only progress ledger; implementation runs in the isolated worktree recorded below.

| Boundary | Proposed files |
| --- | --- |
| Central request bridge | Modify client/src/api.ts only to export the existing generic request transport and add scoped Vietnamese error-code messages if required, without changing current request/session behavior. Create client/src/shared/api/createManagementApiClient.ts and client/src/shared/api/createManagementApiClient.test.ts. |
| Query/auth integration | Create client/src/app/ManagementProvider.tsx and client/src/app/ManagementProvider.test.tsx. Keep app/AuthProvider.tsx, features/auth/AuthProvider.tsx and their token lifecycle unchanged. Do not mount the legacy AuthProvider or global query singleton. |
| Active navigation | Modify client/src/app/router.tsx, client/src/shared/layout/Sidebar.tsx, client/src/shared/layout/Breadcrumbs.tsx and client/src/shared/lib/permissions.ts. Create client/src/shared/lib/permissions.test.ts; extend active router/AppShell integration tests only as needed. |
| Users | Modify client/src/features/users/UsersPage.tsx, UserCreateForm.tsx, UserActions.tsx, schemas.ts and UsersPage.test.tsx. Keep supported API factory/types; no new backend fields. |
| Categories | Modify client/src/features/categories/CategoriesPage.tsx, schemas.ts, api.ts and CategoriesPage.test.tsx; lookup extension may add an all-pages read helper using the existing collector, without changing mutation contracts. |
| Suppliers | Modify client/src/features/suppliers/SuppliersPage.tsx, schemas.ts and SuppliersPage.test.tsx. |
| History/audit | Modify client/src/features/transactions/TransactionsPage.tsx, TransactionsPage.test.tsx, client/src/features/audit/AuditPage.tsx and AuditPage.test.tsx. |
| Reused inventory copy | Modify client/src/features/inventory/InventoryFilters.tsx and InventoryLabels.tsx only for optional Vietnamese copy/localization at M2 call sites; preserve existing default behavior and lookup logic. Existing inventory tests remain regression gates. |
| Shared presentation | Create client/src/shared/styles/management.css, imported only by the management boundary. Modify shared/layout/app-shell.css only if additional navigation needs safe scrolling. Extend shared/ui/Pagination.tsx and its test only with compatible optional Vietnamese labels if needed; other consumers retain defaults. |
| Local icons | If approved design needs missing icons, create only users.svg, categories.svg, suppliers.svg, transactions.svg and audit.svg under client/src/shared/assets/icons/; label them local proposed assets, not unverified Figma exports. |
| Active-context testing | Create client/src/test/renderManagementRoute.tsx and client/src/app/management-routes.integration.test.tsx; update the five scoped feature test contexts/selectors without weakening assertions or rewriting unrelated legacy tests. |
| Real E2E | Create client/e2e/management-ui.spec.ts; only extend client/e2e/helpers.ts and client/e2e/admin-management.spec.ts where necessary for explicit UI coverage while retaining backend security assertions. |
| Approved E2E port amendment | Modify client/playwright.config.ts only to permit the additional isolated loopback port 18082; keep all existing origin/protocol/port/security restrictions. |
| Approved E2E navigation amendment | Modify client/e2e/auth-client.spec.ts only to align the three role-visible navigation matrices with approved M2 routes, retaining all authentication, token, hydration, logout, 401/403 and forbidden-route assertions. |

Other source/test files require explicit scope review before editing. Do not edit active auth, switch providers or expand the allowlist ad hoc when an adapter test fails.

## Acceptance Criteria

- [x] AC-1 — Exact authority/HEAD, M1 DONE dependency and approved written interaction/implementation description are recorded before IN_PROGRESS; actual Figma shell-context evidence or explicitly approved alternative is recorded without claiming new approved frames.
- [x] AC-2 — All five destinations resolve inside the current AppShell with Vietnamese breadcrumbs, route-derived active navigation, supported role visibility and working anonymous/denied direct-URL behavior; existing routes/login remain intact.
- [x] AC-3 — Management calls use the active token and central request/session handling. Current-session 401 clears authentication, stale-session 401 cannot log out a later session, 403 does not log out, and query data/errors cannot cross logout/account/role boundaries. No second auth provider/global shared session cache.
- [x] AC-4 — Users UI exercises only supported create/role/status actions against real APIs; admin account protections, field validation, conflicts, pending/cancel/confirmation and safe error handling are preserved. No credential is printed or stored in query keys/audit/feedback.
- [x] AC-5 — Category/supplier read and admin mutation UI works with real server paging/search. Parent/label lookup resolves records beyond the first page, prevents invalid self-parent selection, preserves entered values on failure and handles conflict/in-use/last-page deletion states.
- [x] AC-6 — History/audit remain read-only, filters map exactly to existing API fields, invalid IDs/date ranges are rejected, page reset and lookup failures/retry work, and audit output contains only allowlisted safe fields. No guessed business data or links to absent detail routes.
- [x] AC-7 — All visible new UI text/accessibility labels/errors are Vietnamese; shared primitives/styles/formatters are reused. Keyboard, focus/confirmation, responsive tables/nav at desktop/mobile, loading/empty/error/forbidden and actual browser/design checks have concrete evidence, not build-only claims.
- [x] AC-8 — Native RED/GREEN, full frontend tests/typecheck/build, unchanged-backend RBAC regression and guarded real E2E pass with actual commands/counts/target identification. Unavailable runtime or visual checks stay NOT VERIFIED. No missing regression is silently skipped.
- [x] AC-9 — Main independently reviews the entire allowed diff and each AC, with at most three native correction rounds; exclusions are preserved, no other milestone/backend/dependency change or Git publication occurs without explicit authority. Mark DONE only with all mandatory evidence.

## Embedded M2 Implementation Plan

> Future execution uses one reusable native implementer and main review. Steps here are planned instructions, not completion evidence. Human approval of this description and explicit execution authority are still required.

**Goal:** Connect existing management capabilities to the active Vietnamese application without changing authentication or backend contracts.

**Architecture:** A management-only provider group lives under the existing protected AppShell and wraps the five new destinations. Reuse legacy feature API/form logic through a narrow active-session transport adapter and per-session QueryClient. Existing business pages/auth providers remain mounted as before.

**Tech Stack:** Existing React/TypeScript/Vite, TanStack Query, react-hook-form/Zod, npm and plain token-based CSS; no package/dependency changes.

**Spec:** Approved M1 stable design and Proposed M2 interaction specification in this task; approval is pending.

### Review Focus

Session/cache leaks and stale 401 responses; unsupported user-role actions; lookup records beyond page 100; raw English/server/audit payload exposure; route/keyboard/responsive regressions. Each is covered by the corresponding explicit test step below.

### Interfaces and implementation decisions

- Export the existing `request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T>` from client/src/api.ts without changing its body/lifecycle semantics. It already coordinates current versus stale generations and unauthorized listeners.
- Add `createManagementApiClient(readToken: () => string | null): ApiClient`. Implement a narrow ApiClient-compatible adapter whose request method delegates to that central request transport, not a second fetch/auth implementation. Convert central ApiError to the existing shared ApiError shape while preserving status/code/field association, exposing sanitized Vietnamese UI messages and no raw credential/payload detail. Non-API failures use a safe Vietnamese fallback. Do not let error conversion bypass central stale-session handling.
- Add `ManagementProvider({ children }: { children: ReactNode })` and `useManagementSession(): { client: ApiClient; user: User | null }`, using `User` from client/src/types.ts and the current app/useAuth hook. Migrate only the five management feature page hook imports. Do not change features/auth/useAuth or the old auth provider globally.
- Scope QueryClient lifetime to the authenticated identity/token/role inside the management route group; cancel/clear on scope change or unmount, never store raw tokens in cache keys/persistence, and disable mutation retries/4xx query retries. Tests must exercise delayed old promises and same-browser account switches, not only fresh mounts.
- Reuse createUsersApi/createCategoriesApi/createSuppliersApi/createTransactionsApi/createAuditApi signatures unchanged. Category lookup may add `listAll(): Promise<Category[]>` using supported paginated reads and collectAllPages; list table pagination stays server-driven. Keep date filters converted to the existing ISO contract and display through formatDateTime.
- Expose route permissions with the existing `can(role, permission)`/RouteGuard model; new frontend entries mirror server grants. No action-only frontend check replaces API authorization. App.tsx remains composition-only and needs no business-page logic.

### Planned test and implementation sequence

- [x] Step 1: Obtain/review shell context and approve the proposed five-screen interaction/role description. Confirm exact file allowlist, safe test environment, dependency and baseline; only then record READY -> IN_PROGRESS and freeze Goal/Context/In Scope/Out of Scope/AC/Verification Commands.
- [x] Step 2: Add `createManagementApiClient.test.ts` cases for active bearer token, unchanged request payloads, 204 success, sanitized 409/422 fields, current 401, stale 401 after re-login and 403. Run `npx.cmd vitest run src/shared/api/createManagementApiClient.test.ts` from client/; record behavioral RED before adapter implementation, then GREEN. Do not accept a type/import setup failure as behavioral RED.
- [x] Step 3: Add `ManagementProvider.test.tsx` cases `usesActiveAuthWithoutLegacyProvider`, `discardsCacheBetweenAccounts`, `ignoresOldSessionResults`, `preservesNewSessionAfterDelayed401` and `doesNotLogoutOn403`. Implement the provider/adapter with the declared interfaces; verify these plus existing active AuthProvider/API tests before exposing pages.
- [x] Step 4: Add permissions/active-router tests for all five paths across admin/warehouse/client/anonymous, forbidden direct URLs, breadcrumbs and active links; confirm they fail for absent routes before adding only the management route group/navigation. Existing login/product/inventory/warehouse routes remain regression gates.
- [x] Step 5: Adapt the users UI to the active management session/shared controls, translate schema/copy and preserve managed-role/admin-record protections. Existing/new users tests cover create/409/422/cancel/role/status/pending and sensitive-field exclusion. Add real UI flow to E2E rather than re-labeling API-only tests as browser coverage.
- [x] Step 6: Adapt categories/suppliers similarly. Pin parent lookup beyond first page, own-ID exclusion, read-only role controls, search/filter page reset, in-use deletion rejection, pending cancellation/failure draft retention and last-page deletion recovery. Do not truncate lookup data or fabricate labels to make assertions pass.
- [x] Step 7: Adapt transactions/audit and optional nested copy props. Pin API query names, invalid date/target ID rejection, server pagination, missing lookup and retry states, read-only controls and allowlisted audit field rendering. Test absent detail-route fallback as text, not a broken navigation link.
- [x] Step 8: Consolidate shared management styles/formatters/confirmations and Vietnamese labels, including optional Pagination/inventory copy. Review keyboard navigation, focus return, accessible names, table overflow and sidebar/logout visibility. Do not modify the approved layout of existing business pages to fix management styling.
- [x] Step 9: Run targeted GREEN, full frontend gates, guarded unchanged-backend RBAC suite and real disposable-stack E2E. Inspect the browser for each screen/role/state at desktop and mobile, with explicit evidence/reference notes. Record VERIFYING before final checks; failure returns to IN_PROGRESS before code edits.
- [x] Step 10: Main independent whole-diff/per-AC review; reuse the same native implementer if needed, maximum three fix/test/review rounds. Record REVIEWING -> DONE only with all mandatory evidence. Present the diff; wait for separate Git authority, and do not start another milestone automatically.

## Verification Commands

Creation/documentation only: `git status --short`; `git rev-parse HEAD`; `git diff`; `git diff --staged`; `git diff --check`; direct whitespace/conflict-marker/required-heading/path checks on this untracked task. Confirm M1 DONE, stable spec/plan fingerprints unchanged and no source/index changes. This does not verify any implementation AC.

Future code verification from client/:

```text
npx.cmd vitest run src/shared/api/createManagementApiClient.test.ts src/app/ManagementProvider.test.tsx src/app/management-routes.integration.test.tsx src/shared/lib/permissions.test.ts
npm.cmd run test:all
npm.cmd run typecheck
npm.cmd run build
npm.cmd run e2e -- e2e/management-ui.spec.ts
npm.cmd run e2e
```

Existing active auth/router/API/product/inventory/warehouse tests and legacy feature tests must remain green. Counts are read from actual output, never assumed from the baseline. New test paths above do not exist yet and must not be reported as executed at task creation.

Backend remains unchanged, but before real integration approval run `python -m pytest -q` and `python -m ruff check app tests alembic` in the verified task environment, with TEST_DATABASE_URL internally set only after guarding the disposable `_test` database/container/loopback target. Full PostgreSQL suites are sequential; never point truncating fixtures at the demo/development DB.

Guard the exact isolated E2E project/database and allowed loopback port before Playwright. Reuse established test helpers for disposable records, do not inspect browser session storage through browser-control tools, do not print credentials, and do not delete arbitrary/demo rows. User-driven browser verification cannot permanently delete nontrivial data without the applicable confirmation.

Browser/design evidence must list route, role, state, viewport and inspected reference. Use the Figma MCP with its required skill before design-context calls; only claim comparison actually performed. Unsupported backend/API execution is explicitly INTEGRATION VERIFICATION PENDING, not runtime PASS.

## Progress Log

### 2026-10-16 — Unique task creation approved

- Human approved creating this exact M2 task after M1 completion. Created only this file; it is the sole selected executable task for future M2 work. No source edit, other task creation, code dispatch, package install, runtime mutation or Git publication is authorized/performed in this creation step.
- Read-only scoping identified the active-versus-legacy auth-context mismatch, query-provider requirement, existing typed API factories, Vietnamese-copy gaps and backend role/action restrictions. Proposed the bounded central-transport/session-cache bridge instead of changing login/token behavior or mounting the old auth tree.
- The embedded interaction specification, role-visible navigation changes and implementation plan await human approval. Keep READY and Started not started; do not freeze an IN_PROGRESS baseline or implement from a task-creation approval alone.

### 2026-10-16 — Creation-time self-review and document checks

- Main reviewed scope coverage, concrete transport/provider interfaces, role/API parity, negative input/session cases, future file boundaries and verification commands. The central request adapter reuses current generation-aware 401 cleanup instead of inventing a parallel auth lifecycle; the optional copy/localization boundary preserves unrelated legacy consumers. These are proposed decisions, not implemented or runtime-verified behavior.
- In-memory PowerShell assertions returned exit 0: required task sections; READY/not-started/pending-approval gates; exactly nine unchecked ACs and five proposed routes; exact M1 dependency DONE/APPROVED; unchanged approved spec/roadmap fingerprints; eighteen existing source references; no whitespace/conflict markers; unchanged baseline HEAD/index/tracked source and excluded LegacyProductsPage hash.
- Only this new task file was created. No Figma context call, code change, behavioral RED/GREEN, backend/frontend build/test, real integration/browser verification or native code dispatch was performed. Do not convert document checks into implementation acceptance evidence. Stop at the written-plan/interaction-approval handoff.

### 2026-10-16 — Human implementation approval and READY -> IN_PROGRESS

- Human replied `duyệt` to the explicit question approving the design/plan in this task and native M2 implementation. This supersedes proposal/pending language retained in the creation history above and below; it does not approve another milestone or Git publication. Human separately selected `Dùng worktree riêng (đề xuất)` in the workspace-preference question.
- Native worktree tool created and attached C:/Users/TQUOCTOAN/.codex/worktrees/m2-core-management-ui/smart-warehouse at exact source baseline d8b3fa82b4b77cba5a3faed49738bf5ebe5c46d6, initially clean. Main checkout and its untracked/unknown files are not copied or modified. This file at the main checkout is the sole canonical task ledger, not duplicated into the source worktree. The implementer reads this exact task and its stable M1 references by absolute path.
- Verified dependency docs/tasks/define-completion-baseline.md is DONE/APPROVED, both approved stable-output SHA256 values and excluded LegacyProductsPage fingerprint match the Context baseline. Only M2 executes. Freeze Goal, Context and authority, In Scope, Out of Scope, Acceptance Criteria and Verification Commands now; no source implementation preceded this transition.
- Figma skill figma-design-to-code was read and official get_design_context succeeded for IoHM7Md1WkS8nt1kH4jrO4 node 5:3, with screenshot inspected before implementation. Shell reference: 1440 px frame, 248 px sidebar, 72 px topbar, Inter and the existing approved token palette. Transactions has the reference two-arrow SVG; use its exported local asset, never its temporary URL at runtime. Other missing management icons are proposed local assets under the approved allowlist, not claimed Figma exports. There are no newly approved dedicated management Figma frames: those screens follow the now human-approved interaction specification here.
- Clean baseline verification from the worktree: npm.cmd ci --no-audit --no-fund succeeded without lockfile/dependency edits; npm.cmd run test:all passed 22 Vitest files / 156 tests and 90 host tests, zero failures/skips; npm.cmd run build passed (90 modules). These are pre-implementation baseline results, not M2 completion evidence.
- Skill execution ruling: apply subagent-driven-development and TDD with one reusable native implementer and main independent review, as explicitly required by the user/repository. Do not create extra reviewers, task ledgers, automatic commits or worktree cleanup. Maximum three correction rounds. Production code is owned by the native implementer; main owns this ledger and independent checks.

| Preflight boundary | Producer / consumer contract | Conflict / consistency ruling |
| --- | --- | --- |
| Transport | Export existing central request; adapter returns legacy ApiClient-compatible client to unchanged feature factories | Preserve central generation-aware 401 handling; sanitize converted errors; no alternate auth transport |
| Session/cache | Active app AuthProvider -> management-only provider -> five feature pages | Identity/token/role-scoped QueryClient, cancellation/clear and delayed-response tests; no singleton or legacy auth mount |
| Navigation | Existing permissions/RouteGuard/router/sidebar/breadcrumbs consume added backend-parity grants | Five approved paths only; existing route/role contracts unchanged; shell CSS only for safe navigation scrolling |
| Shared presentation | Existing primitives and optional localized Pagination/inventory copy -> new management pages | Preserve legacy defaults and unrelated screens; management CSS imported at its own boundary |
| Verification | Existing API factories + real isolated stack -> new active-context/unit/E2E checks | Baseline clean; do not target the running demo at port 18081; guard a separate disposable stack before any write |

- Step 1 complete. AC-1 has authority/dependency/baseline/Figma preflight evidence. Remaining ACs stay NOT VERIFIED until implementation and actual tests/browser/review evidence exist. No backend, package, index, commit, push, merge or unrelated task change.

### 2026-10-16 — Approved scope amendment: isolated E2E port

- Reason: bind probes confirmed existing allowed ports 58080 and 58081 unavailable; port 18081 serves the preserved demo. Loopback port 18082 successfully bound during the read-only availability check.
- Approver: human user, explicit answer `Duyệt dùng cổng 18082 cho E2E M2` to the question naming client/playwright.config.ts and the separate disposable stack/database. Add only that file and port to the approved allowlist; no API, firewall, demo, backend or dependency change. Goal and all acceptance criteria remain unchanged.
- The E2E target will be http://127.0.0.1:18082 on a newly named disposable M2 project/database, guarded before writes. No existing demo volume or rows may be cleared. Native implementer is informed; no port-guard edit by main.

### 2026-10-16 — Native dispatch and unchanged-backend regression

- Reused the sole native implementer /root/remediation_review for the approved source allowlist in the new worktree. No extra implementer/reviewer was spawned. Behavioral RED/GREEN and all source checks are required before main review; native may not change this ledger or stage/commit.
- Main ran python -m pytest -q with the verified Python environment and an internally constructed URL only after checking exact disposable container sw-phase1-backend-checkpoint-20261015-test, database sw_phase1_checkpoint_test and loopback 127.0.0.1:55439. Result: 462 passed, zero skipped, two dependency deprecation warnings, 76.62 seconds. Credentials were not printed. No concurrent PostgreSQL truncating suite ran.
- Main ran python -m ruff check app tests alembic: exit 0, all checks passed. Backend code and contracts remain unchanged; these results alone do not verify management UI/browser ACs.
- Prepared separate Compose project sw-m2-core-ui-20261016 with a new e2e_postgres_data volume and isolated smart_warehouse_e2e database, no host API/DB ports. Configuration validated; backend build, migrations/bootstrap completed and API/DB health is healthy. No .env was read. Existing demo project/port18081 and its volume are untouched. No management browser flow has been executed yet.

### 2026-10-17 — Resume after native usage-limit interruption

- Human requested continuation. Revalidated the same canonical IN_PROGRESS task and isolated source worktree at unchanged d8b3fa82b4b77cba5a3faed49738bf5ebe5c46d6. Partial implementation is preserved; no task restart, baseline change or new milestone. Main-checkout tracked/index state remains unchanged and the approved stable-output/excluded LegacyProductsPage fingerprints still match.
- The prior native turn ended with an account usage-limit error before its implementation/test report. Do not infer native RED/GREEN or completed UI from the partial files. Resumed the same /root/remediation_review implementer; main still owns independent review and this ledger. No additional agent or correction round was started.
- Existing active-sidebar host regression client/tests/ui-shell-remediation.test.js uses exact per-role link matrices. Updating those matrices and management breadcrumbs, while preserving accessibility/logout assertions and all old destinations, falls under the approved active router/AppShell integration-test boundary; no unrelated harness rewrite is authorized.
- git diff --check in the implementation worktree returned exit 0 at resume. This is whitespace-only evidence, not successful M2 behavior/build verification. Docker Linux engine was unavailable; a non-destructive docker desktop start was issued. Runtime/E2E verification remains pending until engine health and exact isolated targets are guarded again. No demo/volume reset, stage/commit/push or merge.

### 2026-10-17 — Isolated runtime restored and targeted transport checks

- Docker Desktop started successfully without resetting data. Main checked the existing M2 DB/API container project labels and absence of host port bindings, then started only sw-m2-core-ui-20261016-db-1 and sw-m2-core-ui-20261016-api-1. Both report healthy. No test web/E2E run is claimed yet.
- Main independently ran npx.cmd vitest run src/shared/api/createManagementApiClient.test.ts src/app/ManagementProvider.test.tsx src/shared/lib/permissions.test.ts in the source worktree: exit 0, three files / sixteen tests passed, 2.57 seconds. This covers the implemented adapter/session/permission boundary as tested, not finished management pages or native test-first evidence. Native continues remaining UI/test work; task stays IN_PROGRESS.

### 2026-10-17 — Interim build findings and fresh disposable PostgreSQL target

- Main interim npm.cmd run build with VITE_API_BASE_URL=/api/v1 failed in the WIP test code: CategoriesPage.test.tsx fixture parent_id inferred as null-only and unsupported ByRoleOptions.exact, plus unknown caught-error accesses in createManagementApiClient.test.ts. Sent exact diagnostics to the native implementer; no TypeScript suppression, dependency change or main code fix. This is implementation feedback while IN_PROGRESS, not a completed independent-review correction round. Browser preview remains pending a passing build.
- The prior guarded PostgreSQL container could not restart because Windows refused its 127.0.0.1:55439 port binding. No reset, port/firewall change or deletion was attempted. A bind probe confirmed 127.0.0.1:18543 available. Created a new task-labeled disposable container sw-m2-core-ui-20261017-test with database sw_m2_core_test, then guarded its exact name, task label, running state and loopback binding before constructing the test URL internally. Password is random, local-only and not printed.
- Applied only the existing migrations to this fresh test database and started the sequential full backend suite. No backend/migration source changed. Ruff rerun returned exit 0 / all checks passed. Full pytest result is pending actual completion, not inferred from the previous 462-pass run.

### 2026-10-17 — Approved scope amendment: existing E2E navigation matrices

- Main read-only inspection found that client/e2e/auth-client.spec.ts asserts exact old sidebar link counts (admin six, warehouse four, client three). Approved M2 adds five/three/one links respectively; retaining the old exact expectations would fail the required full E2E regression despite intended navigation.
- Approver: human user, explicit answer `Duyệt cập nhật test menu E2E` to the question naming this file and the preserved security assertions. Add only this narrow navigation-expectation update to the allowlist. Do not remove/skips tests or weaken login, /auth/me, token, logout, 401/403, backend authorization or forbidden-route assertions. Goal/AC/verification requirements remain unchanged. Main notified native after approval.

### 2026-10-17 — Fresh backend GREEN and intermediate browser evidence

- Sequential fresh-database verification completed: existing migrations applied; python -m pytest -q returned 462 passed, zero skipped, two dependency deprecation warnings in 99.73 seconds on guarded sw_m2_core_test / loopback18543. Ruff rerun passed. No backend source changed.
- Main interim build after native test-typing fixes returned exit 0, 263 modules; VITE_API_BASE_URL=/api/v1. It warns that the bundled JS is 580.70 kB /168.68 kB gzip. Record this size warning, do not suppress it or expand architecture/dependency scope. Final checks must rerun against finished source.
- Started task-labeled sw-m2-core-ui-20261016-preview-web serving only the worktree dist/config as read-only mounts. Before browser activity, main guarded loopback18082, exact task/project labels, common isolated M2 network, API/DB running state and smart_warehouse_e2e; readiness GET returned ready. Demo18081 is not targeted.
- Main actual browser inspection on18082: seeded admin authenticated through existing login; /users real roster/admin protections, /categories real hierarchy list, /suppliers real server search/empty result, /transactions real read-only empty state and /audit real empty state/invalid target ID all rendered Vietnamese shared UI. No business mutation was submitted from browser-control tools. A user-role dialog initially focused Hủy; Escape closed it and restored its original trigger.
- At1440x1024, DOM-backed measurements confirm sidebar248px and topbar72px, route-derived /users active state, Inter, app rgb247/249/251, sidebar rgb11/18/31, sidebar text rgb195/205/221 and white topbar. These correspond to the already-inspected Figma5:3 shell foundation; management screens follow the human-approved written interaction specification, not nonexistent dedicated frames. Source/runtime screenshot observations were performed, not inferred from build.
- Browser role checks: admin11 destinations; client4 (products/inventory/warehouses/categories), category read-only and direct /audit redirected to /products; warehouse7 (inventory/warehouses/inbound/outbound/categories/suppliers/transactions), supplier read-only. Logout returned /login outside the shell; anonymous direct /users returned /login; authenticated /users refresh restored the protected view. Endpoint-level auth/me and token assertions still require final automated evidence.
- Responsive observations:390x844 and390x600 show icon-only72px sidebar with accessible destination names, stacked management controls, internally scrollable tables and visible account/footer. At390x600 nav content512px scrolls within485.2px and footer bottom584px. At requested320px with classic15px scrollbar, baseline global body min-width320 produces a15px document overflow; this unchanged shared-foundation limitation is recorded, not claimed fixed or a new M2 regression. Final native review/tests and all mandatory states remain pending; task stays IN_PROGRESS.

### 2026-10-17 — Native handoff and IN_PROGRESS -> VERIFYING

- Sole native implementer reports source frozen for main independent review, with frontend/test/assets only. No backend/dependency/AuthProvider/doc/index/commit change. Main will validate exact file count/diff rather than rely on this report alone.
- Native reports behavioral RED for the pending-context-loss cases, then eighteen category/supplier cases GREEN covering create/update, plus RED/GREEN for audit prototype-safe translation. No missing-import/type setup failure is accepted as behavioral RED. Further historical RED details, if unavailable after the usage interruption, must be labeled unavailable rather than invented.
- Native final gate report:213 Vitest tests/26 files plus90 host passed, typecheck/build and standalone E2E/config TypeScript passed, diff-check passed; build263 modules with580.90kB/168.72kB gzip warning. Real E2E12/12 passed in20.5s on18082 after build, eight preserved scenarios plus four new management UI scenarios with no network mock. Native noted one earlier simultaneous test/build/E2E run timed out StockPage; sequential rerun passed without timeout/assertion weakening. Main will rerun final frontend/integration gates sequentially.
- Main interim independent test:all already returned213/26 +90 host, zero failures/skips; typecheck passed. Read-only transport comparison confirms the central request body unchanged except export, and git diff confirms backend/tests/alembic/packages/App.tsx/active and legacy AuthProviders unchanged. This does not replace the final whole-diff/per-AC review.
- Enter VERIFYING now. No further source implementation is allowed without recording VERIFYING -> IN_PROGRESS first. Main owns final verification, browser/design evidence and independent review; no additional reviewer/implementer or next task is started.

### 2026-10-17 — Final verification GREEN and VERIFYING -> REVIEWING

- Main independently reran frozen source sequentially: npm.cmd run test:all =>213 tests/26 Vitest files plus90 host, zero failures/skips; npm.cmd run typecheck =>exit0; build with VITE_API_BASE_URL=/api/v1 =>exit0,263 modules,580.90kB JS /168.72kB gzip warning retained. Exact four-file bridge/provider/routes/permissions command =>37 passed. Standalone TypeScript for all five E2E/helper/config files using --ignoreConfig/--noEmit/module esnext/moduleResolution bundler/target es2022/skipLibCheck =>exit0.
- Guarded real integration after restoring API: targeted npm.cmd run e2e -- e2e/management-ui.spec.ts =>4/4 passed in10.1s; full npm.cmd run e2e =>12/12 passed in21.0s, no network mocks or skipped scenarios. Existing login/hydration/token cleanup/logout/role-change403/product/warehouse/stock flows remain covered alongside four new management UI scenarios. The exact project/database/network/loopback18082 guard was checked before writes. Only disposable fixture records were changed; user/audit/movement history remains retained.
- Main actual failure/recovery check, warehouse /suppliers: guarded and temporarily stopped only the isolated M2 API; clicked Tải lại, observed Vietnamese safe failure with Thử lại after the proxy connection timeout (not an immediate10-second response), navigation/session retained. Restarted the exact same API, readiness returned ready, Thử lại restored the real supplier table. No source, database volume or demo data changed. Account/cache/role and delayed401 remain separately covered by the named integration tests.
- Native clarified retained actual RED evidence: adapter6 failed on legacy transport behavior (204/null, raw/English fields, central401/stale flag), then6 passed; provider valid RED3 failed/2 passed for cache/old-promise isolation using old query-only provider (not falsely called delayed401 logout evidence), then combined provider/adapter/current-auth/API34 passed; routes9 failed/11 passed due absent authorized routes, then routes/permissions25 passed. Initial provider selector/timing setup failures were corrected before the behavioral RED; not counted as evidence. Native pending-context and audit inherited-key RED/GREEN are also recorded. No historical replay or missing-import failure is presented as test-first evidence.
- Exact inventory:46 changed/new frontend/test/SVG files in the source worktree. Sorted relative-path + SHA256 manifest digest before and after final gates is unchanged: B82C11FA573F5FED6E4C8D6CBB5EC2481D730477A3F5BC7B925225993CC69855. HEAD remains d8b3fa82b4b77cba5a3faed49738bf5ebe5c46d6; index empty; diff-check exit0. Backend/package/AuthProvider/App.tsx preservation checks remain clean.
- Enter REVIEWING for main independent whole-diff/per-AC review now. No source edits are permitted without REVIEWING -> IN_PROGRESS. The initial implementation feedback was resolved before the frozen handoff; no post-handoff correction round has been used. No extra agent, commit/push or next milestone.

### 2026-10-17 — Main independent review and REVIEWING -> DONE

- Main reviewed the entire46-file modified/new source/test/asset set and each AC, including the session adapter/provider, unchanged central transport body, exact role/API parity, route group and existing flows, sanitized field/error/audit output, parent lookup/paging, pending/confirmation/draft boundaries, local SVGs and scoped shared presentation. Existing security assertions remain; only approved navigation expectations/selectors/comments were aligned. No mandatory in-scope finding remains. Initial pending-context loss, audit inherited-key rendering and test-typing issues were corrected and covered before the frozen final verification; no post-handoff correction round was needed (zero of maximum three).
- Main also applied the relevant label/semantic-control/focus/confirmation/content-handling checks from Web Interface Guidelines (https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md) to the approved scope. This is not a claim of complete WCAG certification or every optional guideline enhancement; new architecture, global skip-link work, URL-filter persistence and unrelated foundation changes were not silently added.
- All46 tracked/new files passed direct whitespace/conflict-marker checks, not only git diff --check. Source manifest remains B82C11FA573F5FED6E4C8D6CBB5EC2481D730477A3F5BC7B925225993CC69855. Main checkout tracked/index state, stable M1 fingerprints and excluded LegacyProductsPage hash remain unchanged. Only this canonical task ledger is updated outside the implementation worktree.

| AC | Verified evidence and boundary |
| --- | --- |
| AC-1 | Exact M1 DONE/APPROVED, human interaction/plan/worktree approvals and approved amendments, baseline fingerprints and successful Figma5:3 context/screenshot before source implementation. |
| AC-2 | Twenty active-route cases across anonymous/admin/warehouse/client plus permission tests, real three-role E2E and main browser navigation/direct-URL/refresh checks. Five destinations and Vietnamese breadcrumbs/active links; existing auth layout unchanged. |
| AC-3 | Adapter/provider/current-auth/API regressions and retained native behavioral RED/GREEN; current401 cleanup, same-token stale401 safety,403 retention, account/role cache/error isolation. Existing real invalid-token/refresh/role-change403 E2E and logout assertions passed. No second auth provider or persisted token-bearing query keys. |
| AC-4 | Users tests and real users/audit UI E2E cover supported client creation, managed role/status confirmation/cancel/pending and resulting audit; backend462 tests preserve authorization/admin protections. Sanitized409/422 fields, password success reset and query-key/audit exclusion have explicit checks. |
| AC-5 | Category/supplier behavioral tests cover all-page parents beyond100, own-ID exclusion, lookup failure/retry, draft retention during create/update failure, disabled context switches, server paging/search and last-page recovery. Real UI CRUD/hierarchy/in-use deletion and supplier search/edit/delete E2E passed. Large lookup boundaries are component/API evidence, not falsely claimed as a101-record manual browser exercise. |
| AC-6 | Read-only history/audit tests, exact API filter/query names, invalid ID/date/range rejection, page reset, lookup detail/retry and safe allowlisted/unknown/prototype facts; real linked movements/filter/audit E2E. No unsupported detail links or fake business data. |
| AC-7 | Main actual1440x1024 shell/reference measurements,390x844/390x600 controls/table/nav checks, all five admin destinations and three role-visible shells; modal cancel/Escape/focus restoration, real empty/search/validation and actual API-down/error/retry recovery. Loading/error/forbidden/unit cases and coarse-pointer shared CSS inspected. Vietnamese application labels/errors/accessibility names; business names from real API are not translated/fabricated. Baseline320px limitation is explicitly recorded below. |
| AC-8 | Retained native behavioral RED/GREEN, final main37 targeted,213 Vitest +90 host, typecheck/build/E2E TypeScript, guarded real4 targeted +12 full E2E, fresh disposable backend462 and Ruff, direct diff/whitespace/manifest checks. No skipped mandatory check or unsupported browser claim. |
| AC-9 | Main independent whole-diff/spec-quality review, preserved exclusions and frozen manifest, zero post-handoff correction rounds, no backend/dependency/architecture/milestone or unauthorized Git publication. |

- Nonblocking notes: JS bundle580.90kB/168.72kB gzip exceeds Vite's default warning threshold; no agreed task performance budget failed, and no warning was hidden. client/src/shared/styles/base.css:22 has the unchanged min-width320px which, at a320px browser viewport with a classic15px scrollbar, causes15px horizontal overflow. It is a preexisting foundation limitation outside this source allowlist, not a claim of universal mobile compliance. Reviewed390px layouts and table/nav scroll behavior meet this task's inspected responsive evidence. No global/base-style fix or new task is authorized by this note.
- All nine mandatory M2 ACs now have the evidence specified above. Mark REVIEWING -> DONE / main review APPROVED. This completes M2 only, not all project milestones or full accessibility/research readiness. No stage, commit, push, merge, deployment or automatic M3 start. Task-specific worktree/runtime/test records are retained for human review.

### 2026-10-17 — Separately approved local source checkpoints

- Human replied `duyet` to the explicit question approving local M2 commits only, keeping the isolated worktree without merge or push. This grants Git checkpoint authority, not another implementation milestone or a new review. DONE / APPROVED and the frozen implementation baseline remain unchanged.
- Before staging, main revalidated the exact 46-file reviewed manifest B82C11FA573F5FED6E4C8D6CBB5EC2481D730477A3F5BC7B925225993CC69855, empty index, unchanged backend/dependency/auth/App.tsx boundaries and exclusions. A bounded high-confidence private-key/provider-key/JWT/credential-bearing-database-URL pattern check found no match in those 46 files; this is not a claim of a universal secret audit. No secret values were logged by that check. Existing synthetic test fixtures are not production credentials.
- Fresh pre-commit verification: npm.cmd run test:all returned 213 Vitest tests /26 files and 90 host tests, zero failures/skips; npm.cmd run typecheck and VITE_API_BASE_URL=/api/v1 npm.cmd run build exited0 (263 modules, unchanged 580.90kB /168.72kB gzip warning). Standalone E2E/config TypeScript check exited0. Backend source is unchanged; the prior 462-test/Ruff evidence is retained, not represented as a new backend run.
- Guarded the exact running M2 containers/project/network, smart_warehouse_e2e database and loopback18082; API/DB have no host bindings. An initial diagnostic used the incorrect /api/v1/ready URL and received404; readiness was then checked at the actual /api/v1/health/ready endpoint with terminating error handling and required status=ready before any E2E run. Full E2E on18082 returned12/12 passed in23.7s, no skipped scenario or network mock. Demo18081 was not targeted.
- Inspected git status, unstaged diff, staged diff and exact staged path list before each local commit. Created sequential logical checkpoints in the retained managed worktree: e1ccbb935167e05bb350b450cdaab651e2b6e749, `feat: add session-isolated management UI foundation` (10 files); cd5d6025f15df682cd9a5bacd2c4841c76ac1833, `feat: connect Vietnamese management pages to protected app shell` (31 files); f72d7f1b4d0d058f31f0fce7901f202c4c4fbce6, `test: cover management UI and role navigation with real APIs` (5 files). No source edits were made during checkpointing.
- Final committed46-file inventory and disk-content manifest match the frozen reviewed source; aggregate git diff --check passed. Implementation worktree HEAD=f72d7f1b4d0d058f31f0fce7901f202c4c4fbce6, detached as managed by the app, working tree/index clean. No branch creation, merge, push, PR, history rewrite or worktree cleanup. Generated reports/dist remain ignored and uncommitted.
- This sole canonical task ledger stays in the main checkout and is not copied into the implementation worktree or included in the three source commits. Existing untracked M1/spec/plan/personal/unknown files at the main checkout remain local, untouched and uncommitted. Do not report the main checkout as clean or these dependency documents as committed. Their publication/integration is a separate decision.

### 2026-10-17 — Separately approved canonical documentation checkpoint

- Human replied `duyet` to the explicit proposal to review and commit only the related M2 documentation at the main checkout, without merging or pushing. The sole selected file is docs/tasks/complete-core-management-ui.md. This is a documentation checkpoint after DONE, not a new implementation/review, baseline amendment, state transition or approval of another milestone.
- Read the complete ledger and reconciled its current summary with the three existing source commits. Revalidated the clean implementation worktree at f72d7f1b4d0d058f31f0fce7901f202c4c4fbce6 and unchanged46-file reviewed source manifest. Main checkout starts at d8b3fa82b4b77cba5a3faed49738bf5ebe5c46d6 on feat/figma-ui-v2, with empty index/tracked diff; it does not contain the M2 implementation commits. Commit this ledger only on that current branch, without copying it into the implementation worktree or integrating source.
- Confirmed the explicit M1 dependency remains DONE/APPROVED and the approved stable plan/spec fingerprints still match. Those dependency documents remain untracked at the main checkout and are not part of this checkpoint; do not claim a self-contained published roadmap or change their status/history. Other untracked files remain excluded and untouched.
- Documentation review corrects stale present-tense summary statements about source HEAD and the absence of source commits. Preserve the entire existing Progress Log and frozen baseline. Prior browser/Figma/runtime/test observations remain dated evidence, not checks newly executed for this documentation commit. DONE/APPROVED and all nine AC conclusions are unchanged; the disclosed bundle and320px limitations remain.
- This docs-only checkpoint uses required-heading/AC-count/commit-reference, baseline/history preservation, stable-reference fingerprint, secret-pattern, direct whitespace/conflict and staged-scope checks. No source, backend, package, generated report, credential or personal file is edited/staged. Tests/build/browser are not rerun for this documentation-only change; the existing source verification is retained without claiming fresh execution. Inspect git status, git diff, git diff --staged and the exact one-file staged list before committing; report the resulting commit ID in the handoff, not as a self-referential value inside this file.
- Main documentation gate returned exit0: all required headings, nine checked ACs, ten checked steps, three valid local commit objects/references, unchanged frozen baseline and complete preexisting progress history, unchanged M1/plan/spec fingerprints and other untracked-file inventory, no whitespace/conflict marker or bounded high-confidence secret-pattern match. Source worktree remains clean at the reviewed commit/manifest. This verifies the documentation checkpoint, not a new browser/Figma/runtime execution or a new AC approval.

## Verification Evidence

- Creation-time documentation checks: PASS, exit 0, as recorded above. This verifies task preparation and preservation only, not the nine implementation ACs.
- Final main source verification:37 targeted tests;213 Vitest/26 files +90 host; typecheck/build and standalone E2E/config TypeScript; guarded targeted4/4 and full12/12 real E2E; fresh disposable backend462 plus Ruff; diff/direct46-file whitespace checks and unchanged source manifest. Commands, target identity and native RED/GREEN are recorded in the append-only log above.
- Browser/design verification is separately recorded with exact role/route/state/viewport and Figma shell-versus-written-screen-design distinction. It is not inferred from tests/build. Source checkpoints and the separate documentation checkpoint authority are recorded above; no remote publication or source merge is authorized/performed. Prior M1/unknown files are preserved. Two nonblocking limitations remain explicitly documented, not silently called fixed.

## Review Result

APPROVED by main independent review on2026-10-17. All nine M2 ACs verified against actual code/test/browser/design evidence; no mandatory in-scope finding or blocker remains. Human written interaction/plan and two scope amendments are separately recorded. Nonblocking bundle warning and unchanged320px foundation limitation remain disclosed; no full-WCAG or complete-project claim.

## Completion Evidence

DONE / APPROVED for M2 only. Started2026-10-16 after explicit approval, completed2026-10-17 after canonical READY -> IN_PROGRESS -> VERIFYING -> REVIEWING -> DONE and all nine ACs. The46-file implementation is committed locally as e1ccbb935167e05bb350b450cdaab651e2b6e749, cd5d6025f15df682cd9a5bacd2c4841c76ac1833 and f72d7f1b4d0d058f31f0fce7901f202c4c4fbce6 in the retained managed worktree C:/Users/TQUOCTOAN/.codex/worktrees/m2-core-management-ui/smart-warehouse. Its detached HEAD is f72d7f1b4d0d058f31f0fce7901f202c4c4fbce6, working tree/index clean at the documentation-checkpoint preflight, and reviewed source manifest unchanged. This sole task ledger stays at the main checkout on feat/figma-ui-v2 for the separately approved documentation-only commit; that checkout has not received the implementation commits. M1/plan/spec and unrelated untracked files remain outside this checkpoint. No source merge, push, PR, deploy, history rewrite, cleanup or other milestone is authorized/performed. Preserve the separate checkpoints and do not start another task automatically.
