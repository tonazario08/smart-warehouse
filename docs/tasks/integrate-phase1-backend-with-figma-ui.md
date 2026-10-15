# integrate-phase1-backend-with-figma-ui — Preserve and integrate Phase 1 backend with approved Figma frontend

## Metadata

- Status: IN_PROGRESS
- Phase: Phase 1 integration and history reconciliation, not Phase 2 business implementation
- Plan: docs/superpowers/plans/2026-10-15-integrate-phase1-backend-with-figma-ui.md
- Specification: user-approved integration brief in this conversation, 2026-10-15; docs/superpowers/specs/2026-09-04-phase-1-production-ready-design.md for backend behavior
- Depends on: docs/tasks/ui-figma-remediation.md
- Created: 2026-10-15
- Started: 2026-10-15
- Completed: not completed

## Goal

Reconcile the existing Phase 1 production backend history and verified pending corrections with the delivered Figma frontend, preserving original commit ancestry and both dirty source worktrees, and produce independently verified local integration checkpoints without publishing.

## Context

- User explicitly approved creation and execution of this exact integration task, including logical local commits, an isolated integration branch, frontend compatibility work and verification. No push or history rewriting is authorized.
- Frontend source: branch `feat/figma-ui-v2`, HEAD `3404b6b`, at `C:/Users/TQUOCTOAN/OneDrive/Documents/ChatGPT/smart-warehouse`. Approved Figma remediation is verified but uncommitted. Other dirty documents, local configuration, personal documents and unknown files must be preserved and excluded.
- Backend source: detached worktree `C:/Users/TQUOCTOAN/.codex/worktrees/phase1-completion/smart-warehouse`, HEAD `3446ae3`. It contains 72 commits absent from the frontend HEAD, plus uncommitted seed, migration, selector and documentation corrections. Its historical task `docs/tasks/phase-1/P1-C01-phase-1-corrective.md` is IN_PROGRESS and is provenance only, not a second executable task for this operation. Do not change its history/state or claim its ACs newly verified.
- Common ancestor: `d6c786322935b1805f865458e5051daa9ce0d247`; frontend has seven commits absent from backend HEAD. Backend history already contains JWT settings and public-registration security corrections missing from the running frontend branch.
- Integration must reconcile authenticated catalogue reads, structured errors, paginated warehouse/stock/history responses, current database-role authorization and strict validation. The old frontend in the backend worktree is not the approved visual source of truth.

## In Scope

- Inventory and preserve both source worktrees; review, verify and commit only known related frontend work before integration.
- Preserve backend original commit IDs using a local reference and a merge ancestry; do not replace existing history with copied/re-authored commits.
- Review and snapshot existing backend dirty corrections into isolated work; verify before any logical checkpoint. Correct confirmed integration-related defects with focused RED/GREEN evidence.
- Resolve merge conflicts on an isolated branch while preserving backend services, repositories, migrations, security, audit, tests/runtime contracts and the approved Figma frontend presentation. Adapt the current frontend API/types/auth/context/tests to those real backend contracts; retain `smart-warehouse-token` and supported login/logout/invalid-session behavior.
- Preserve already implemented Phase 1 functionality and real API integration. No mocks in application runtime, new UI framework or package-manager change. Use Vietnamese visible text and English identifiers.
- Run focused, full backend/frontend, PostgreSQL migration/security/concurrency, runtime and real browser verification required by the integrated changes. Use disposable data/services; never migrate, seed, register privileged users in, or clean up the current development database.
- Record all new integration history, state/evidence and review only in this task. Existing task documents may travel unchanged in checkpoints/merges as historical records.
- Make verified local commits grouped by functionality, and integrate into `feat/figma-ui-v2` only when safe. If unrelated dirty files would be overwritten, preserve them and obtain the user's decision instead of stashing, committing or discarding them silently.

## Out of Scope

- Phase 2 warehouse operations, new UI redesign or unrelated feature work.
- Secret/credential changes, printing token/password/key values, committing `.env`, personal `.docx`, local-only configuration, generated reports, caches, build output, dependencies or environments.
- Rewriting/amending/backdating old commits, destructive Git, remote pushes, pull requests, deployment or source-worktree removal.
- Automatically replacing Figma pages with the old backend worktree frontend, or changing the backend authorization/API to accommodate obsolete frontend assumptions.
- Updating historical completion claims outside this selected task or reading legacy shared-task files under `docs/plans/`.

## Acceptance Criteria

- [ ] AC-1 — Source HEADs, dirty-file ownership/exclusions and approved related changes are recorded; original dirty work is preserved and logical checkpoints contain no unknown/local/secret/generated files.
- [ ] AC-2 — Original frontend and backend commit ancestry is retained; integrated history contains both verified sources without rebase, amend, backdating or push.
- [ ] AC-3 — Verified seed/migration corrections are retained; disposable PostgreSQL migration/seed checks and applicable integrity/concurrency tests pass, with no writes to the current development database.
- [ ] AC-4 — Integrated auth uses configured JWT settings and expiry/required claims, prevents anonymous administrator creation, enforces current database RBAC, and preserves frontend token hydration/logout/401 cleanup.
- [ ] AC-5 — Figma shell/pages remain the visible frontend; real catalogue/directory/warehouse/stock/movement/history contracts, pagination beyond 100 and structured Vietnamese error handling work without mock runtime data.
- [ ] AC-6 — Integrated focused tests, full backend/frontend tests, type checking/build, relevant PostgreSQL/runtime/browser verification and diff checks pass; unavailable verification remains explicitly NOT VERIFIED and prevents completion where mandatory.
- [ ] AC-7 — Independent review resolves required findings; verification counts, commit hashes/ancestry, changed files, preserved exclusions, remaining limitations and actual target-branch merge status are reported. No publication or destructive operation occurs.

## Verification Commands

### Focused

- Existing frontend source baseline: compile/run all `client/tests/*.test.js` using the corrected host recipe in the completed UI remediation dependency; `npm.cmd run build`; `npx.cmd tsc --noEmit`.
- Backend source/snapshot: `.venv/Scripts/python.exe -m pytest -q tests/test_seed.py tests/test_migrations.py` plus relevant auth, master-data and inventory tests available in that checkout; test commands must report missing runtime/dependencies rather than silently skip required tests.
- Integrated frontend: focused tests for auth generation/token cleanup, authenticated catalogue access, structured error parsing/Vietnamese rendering, paginated directory/stock/movement reads, mutation payload preservation and failures. Demonstrate RED/GREEN for new compatibility behavior.
- Git ancestry: `git merge-base --is-ancestor <frontend-checkpoint> <integration-head>` and `git merge-base --is-ancestor 3446ae3 <integration-head>`.

### Regression

- Backend: `.venv/Scripts/python.exe -m pytest -q`; `.venv/Scripts/python.exe -m ruff check app tests alembic`.
- Frontend: `npm.cmd run build`; `npx.cmd tsc --noEmit`; integrated test command covering retained Figma tests and applicable backend-branch frontend tests, explicitly recorded before execution.
- Disposable PostgreSQL: relevant `tests/postgres/` suite, including auth/RBAC, migrations, seed and inventory concurrency; fail closed to a dedicated test database/project and stop on unsafe target settings.
- Runtime/browser: use an isolated API and frontend origin/database to verify actual login, protected refresh, logout/401 cleanup, role visibility, product lookup/CRUD, movement success/409 and resulting stock, preserving approved Figma layout. Docker/Compose health and migration ordering when changed by integration; do not reuse current development data for writes.

### Static and Diff

- Before every commit: `git status`, `git diff`, `git diff --staged`; inspect exact staged allowlist and verify secret scan without printing secret values.
- `git diff --check`; source worktree status/hash comparison; no unexpected staged files or generated data.

## Progress Log

### 2026-10-15 — Task creation authorized

- User approved the proposed integration scope and this exact task path. This is the explicit creation exception for a previously nonexistent task; no source implementation, merge or commit has started.
- The selected task is the only active integration authority. The backend's historical IN_PROGRESS task is a source artifact, not authorization to execute a second task.

### 2026-10-15 — READY -> IN_PROGRESS

- Read the canonical workflow/rules, selected task, approved integration plan, backend stable specification and the declared UI remediation dependency. Dependency is DONE with APPROVED review and eight recorded ACs. The approved conversational integration scope authorizes this single milestone; no historical task is reopened.
- Frozen Goal, Context, In Scope, Out of Scope, Acceptance Criteria and Verification Commands. Plan self-review checked checkpoint ownership, backend/frontend API shape changes, source preservation and independent verification gates.

| Internal workstreams | Shared boundary | Preflight decision |
| --- | --- | --- |
| Frontend checkpoint / integration | Current pages, shared UI/assets/tests | Verify and preserve Figma first; no legacy frontend replacement. |
| Backend snapshot / merge | Seed, migration, tests, runbook | Copy/review pending corrections; preserve dirty source checkout exactly. |
| Backend merge / frontend compatibility | Auth, roles, paginated collections, error envelope | Backend behavior is authoritative; adapt the retained client and tests. |
| Verification / target merge | Runtime config, migrations, Docker, unrelated dirty docs | Isolated writes only; unavailable gates remain NOT VERIFIED; no overwrite/stash of unknown files. |
| Single milestone baseline | Plan versus task versus old Phase 1 spec | New user-approved Figma integration governs presentation; old production spec governs backend contracts, not a forced UI rewrite. |

- Ruling: use the selected task as the sole execution ledger and reuse exactly one native implementer with main-agent independent review, following the user's established execution preference. Do not create parallel executable tasks/reviewer agents or delete worktrees automatically. Cost if wrong: fewer independent review seats; compensate with direct source, regression and browser verification by the main agent.
- Ruling: preserve unrelated source changes in place; if they block final target checkout merge, leave a verified integration branch and ask for the precise disposition. Cost if wrong: final adoption may need an additional user decision, but no unreviewed work is lost.

### 2026-10-15 — Verified source checkpoints and isolated workspace

- Committed only this task and its new approved plan as `5ff2691` (`docs: define backend and Figma UI integration gates`). Committed the reviewed 47-file Figma implementation/assets/tests and unchanged historical completion record separately as `1cba4cb` (`feat(ui): align Figma screens and shared controls`). Fresh verification before these checkpoints: current source frontend 90/90, production build 89 modules, TypeScript PASS; current source backend 54 passed/3 existing warnings; diff checks PASS. These results do not validate future integration.
- Main agent and the sole native agent reviewed the UI allowlist. Credential/private-key/JWT pattern scan of candidate text found zero matches; the licensed Inter binary SHA256 remains `693B77D4F32EE9B8BFC995589B5FAD5E99ADF2832738661F5402F9978429A8E3`. All ten new SVGs are local, valid and free of scripts/remote hrefs. Only exact allowlists were staged; `.env`, generated files and unknown changes were excluded.
- Original frontend checkout now has only the pre-existing unrelated production-plan edit and unselected untracked files. Its production-plan working content hash remains Git blob `a01e78aecfc230e2d31d98b1f1624b8d3e31453b`. No unknown file was staged, stashed, discarded or deleted.
- Preserved backend HEAD with local reference `codex/phase1-backend-history` at `3446ae380e4b7b45b1fcd544e9f52c270b2d40ba`. Its twelve dirty files remain untouched in the original detached checkout. Native preflight mapped all twelve to the recorded seed-role collision, migration preflight, >100 selectors and runbook corrections; no unknown purpose was found in that set.
- Backend-source focused `.venv/Scripts/python.exe -m pytest -q tests/test_seed.py tests/test_migrations.py` passed: 46 tests, 2 existing dependency warnings. An earlier background invocation's completion output became unavailable, so only the fresh completed 46-test run is counted. This is unit/source evidence, not PostgreSQL or integrated evidence.
- Created managed integration worktree `C:/Users/TQUOCTOAN/.codex/worktrees/phase1-backend-figma-integration/smart-warehouse` from `1cba4cb` and branch `codex/integrate-phase1-backend-figma`. This copy is now the authoritative selected task record; the original source record remains its committed snapshot. Both source checkouts are preserved.
- Docker was initially unavailable. The supported CLI start was attempted without resetting data; user then confirmed Docker Running and `docker info` returned server `29.7.2`. Required PostgreSQL/runtime gates can now be attempted, but none has passed yet for the integration.
- Native preflight identified remaining backend gaps despite its historical corrections: decoder does not require lifecycle claims; movement quantity/reference lack DB-compatible upper bounds. They require focused RED/GREEN coverage in isolated integration work. No source worktree has been edited to address them.

### 2026-10-15 — Backend correction isolation and merge preflight

- Created a second task-owned managed worktree at `C:/Users/TQUOCTOAN/.codex/worktrees/phase1-backend-checkpoint/smart-warehouse`, branch `codex/phase1-backend-corrections`, from original backend `3446ae3`. Copies of this selected task, its plan and declared UI dependency are read-only execution-authority snapshots there; do not stage them as backend implementation. Only this primary integration copy receives new task history.
- The sole native implementer is assigned to preserve the twelve known source patches in that isolated checkout, test seed/migration/selector groups, and reproduce/fix required JWT claims and movement DB-bound validation with RED/GREEN tests. Original worktree remains read-only. No backend commit or actual merge has yet been made.
- Read the existing backend API contract and real schemas: authenticated catalogue; page envelope on warehouse/stock/history; separate inbound/outbound reads include reference/note/creator ID/time; transactions include IDs/time but no human-readable actor label. Preserve actual facts and avoid claiming all Figma fields unavailable after integration.
- A non-working-tree `git merge-tree --write-tree --name-only` preview (no branch/index/source changes) found 18 conflict paths: `.env.example`, `alembic/env.py`, `app/core/config.py`, `app/core/errors.py`, `app/main.py`, `client/package-lock.json`, `client/package.json`, `client/src/App.tsx`, `client/src/api.ts`, `client/src/app/router.tsx`, `client/src/styles.css`, `client/src/types.ts`, workflow design/process documents and four core test files. The generated preview tree is diagnostic only, not a verified integration commit.
- Preflight ruling: retain the current execution workflow/process documents when resolving duplicate historical process records, keeping both originals recoverable in parent ancestry. Preserve the new integration task record and historical backend task state; do not synthesize new completion approvals. Cost if wrong: historical policy wording remains available only through the backend parent, rather than producing a misleading combined current document.
- PostgreSQL/Docker test ownership is delegated to the native implementer for a uniquely named disposable project/database ending `_test` on an unused localhost port. No shared development database is permitted as a test target.

### 2026-10-15 — Independently verified backend checkpoints

- Native implementer copied exactly twelve original pending files without modifying either source; main SHA256 comparison confirmed twelve matches. New required-claim and movement-bound changes have separate RED/GREEN evidence: native observed six unit, five PostgreSQL API and one concurrent-overflow failure before implementation, then passing targeted regressions.
- Main independently ran the complete backend suite in the checkpoint checkout with `TEST_DATABASE_URL` restricted to container `sw-phase1-backend-checkpoint-20261015-test`, database `sw_phase1_checkpoint_test`, loopback port `55439`: 459 passed, zero skipped/failed, two dependency deprecation warnings. Also ran SQLite-only regression (142 passed), Ruff (PASS), retained backend frontend Vitest (117 passed / 19 files), build (216 modules) and TypeScript (PASS). Native separately verified migration 0001 -> 0002 on that disposable database. These are checkpoint evidence, not integrated/browser evidence.
- Created six reviewed local checkpoints on `codex/phase1-backend-corrections`: `0da69fe` seed identity/role conflicts; `0cdd573` migration collision preflight; `a4a2685` mandatory JWT claims; `84f361b` input bounds/atomic stock overflow; `88f312a` complete legacy selector lookups; `77e5c4d` isolated E2E prerequisites. Every staged group was inspected against its exact allowlist; no task authority snapshot, environment file, generated output or unknown file entered those commits.
- Main scanned 511 distinct candidate text blobs reachable from frontend checkpoint/backend history but not `origin/main` for private-key, JWT-literal and common provider-token signatures: zero matches. This bounded pattern scan is not a guarantee against every possible secret; values were not printed.
- Integration ruling: runtime remains the approved Figma router/shell. Preserve old feature modules and their meaningful unit tests using an explicitly test-only legacy router; those tests must never be reported as proof of the active Figma router/provider. Add separate tests against the actual Figma routes/auth/API. Historical backend-only management screens are not newly exposed or visually redesigned in this compatibility task; their backend endpoints remain retained. Cost if wrong: those historical screens require a separately approved Figma integration rather than becoming an unapproved second runtime shell.

### 2026-10-15 — Merge started; target adoption deferred by user

- Started a non-committing merge of `codex/phase1-backend-corrections` (`77e5c4d`) into the isolated integration branch. Eighteen preflight conflict paths were reproduced. Native implementer owns code resolutions and compatibility/tests; main retained the current workflow spec/process records without new historical completion edits. Merge remains uncommitted until relevant verification and independent review.
- Read-only target overlap check found the pre-existing tracked production-plan edit would overlap incoming history; its blob still equals `a01e78aecfc230e2d31d98b1f1624b8d3e31453b`. No incoming-path overlap was found among untracked root files.
- User explicitly chose **keep the integration branch separate; do not merge into the main checkout**. This narrows the approved adoption step, not the frozen implementation/verification baseline. Final handoff must report the isolated branch and NOT claim `feat/figma-ui-v2` has adopted it. Do not inspect, stage, stash or overwrite the unrelated plan edit.

### 2026-10-15 — Integrated backend and disposable runtime verification

- Main independently ran the merged-tree backend suite against the dedicated checkpoint test database: 459 passed, no failures/skips, two dependency deprecations; Ruff PASS. `app/`, `alembic/`, `tests/` and `pyproject.toml` are identical to verified backend checkpoint `77e5c4d` after conflict resolution. Active frontend compatibility remains in progress.
- Retrieved Figma `get_design_context` with screenshot for approved node `5:3`. Current shared layout/tokens/assets have no diff from approved UI checkpoint `1cba4cb`; retain local assets and plain CSS. Actual integrated browser comparison remains pending.
- Validated a unique Compose project `sw-phase1-figma-integration-20261015-e2e` before creating it: project-owned E2E volume, no published DB/API ports, web port `58081` unused, API depends on successful migration and bootstrap. Only this disposable project's DB/runtime resources were created; no existing project was reset or removed.
- Production backend/migration/bootstrap image builds passed. Fresh disposable runtime migration completed at `20260904_0002`, bootstrap exited 0, API became healthy, `/health/live` returned alive and `/health/ready` returned ready. A repeat of that project's bootstrap exited 0 and preserved the user count at three. Image inspection confirmed runtime UID 10001 and absence of `.env`, tests, pytest and Git source metadata.
- Main real HTTP smoke inside the production API container verified anonymous catalogue/me 401, rejected registration with `role=admin` 422, login/me for all three seeded roles, paginated catalogue/category/warehouse/stock envelopes, admin/warehouse transaction reads, client transaction 403, and non-admin dashboard 403. Only statuses/contract assertions were logged; no token/password values. This is a bounded API matrix, not browser or complete endpoint coverage.
- Web image, active frontend suites, integrated browser/E2E and final independent review are still NOT VERIFIED. No source database migration or privileged registration occurred.

### 2026-10-15 — Active frontend independently verified; browser/E2E in progress

- Native demonstrated RED/GREEN for authenticated catalogue reads, paginated collections, structured errors, auth lifecycle races, protected return route/history and stale mutation 401. Main independently reran `npm.cmd run test:all`: Vitest 156/156 across 22 files (117 preserved legacy-capability tests, 39 tests for the active Figma API/provider/routes), plus all 90 Node-host tests with zero failures/skips/cancellations. Build PASS (90 modules), `npx.cmd tsc --noEmit` PASS, diff checks PASS. Runtime entry, Figma router/styles/layout/tokens/assets remain unchanged from `1cba4cb`; retained legacy frontend is not the active UI.
- Production web image built from clean `npm ci` and served successfully at `http://127.0.0.1:58081`; protected deep links and the proxied readiness endpoint return 200. Native is porting obsolete English-shell E2E assertions to active Vietnamese Figma flows, using real API checks for preserved backend-only capabilities; E2E is not yet complete.
- Main browser verification on that isolated origin observed unauthenticated `/products` redirect to `/login`, real admin login returning to `/products`, authenticated dashboard reload preserving the visible account, and real catalogue/warehouse data. Figma node `5:3` comparison: 1440px viewport, sidebar 248px, topbar 72px, Inter, all 13 observed dashboard static images loaded at their intended 22px/20px/8px sizes. At 390px, document width 375px (within viewport), accessible 56px sidebar navigation targets and no broken images. Local evidence under `client/node_modules/.tmp/integration-browser/` is generated/excluded from commits. These checks do not imply untested routes or full pixel-perfect equivalence.
- Build revealed existing transitive `source-map-js@1.2.1` High advisory GHSA-68fv-2mgg-jv7q. Both source lockfiles already contain 1.2.1; official advisory identifies patch 1.2.2. Proposed a narrowly scoped lockfile update and full re-verification; user asked for the proposal and explicit amendment approval is pending. Do not run broad audit fixes or change baseline without approval.

### 2026-10-15 — Approved scope amendment: one transitive security patch

- Reason: production web build exposed pre-existing High advisory GHSA-68fv-2mgg-jv7q in transitive `source-map-js@1.2.1`. Both input lockfiles contain the affected version; official advisory and existing semver ranges permit patch `1.2.2`.
- Approver: human user, explicit reply **Duyệt cập nhật bản vá và kiểm thử lại**, 2026-10-15, after receiving the exact bounded proposal. This amendment authorizes only the `source-map-js` 1.2.1 -> 1.2.2 lockfile update and required verification; no direct dependency/framework/package-manager changes, force audit fix or unrelated upgrades.
- Additional verification: inspect lockfile diff for only that dependency's version/resolution/integrity metadata; clean `npm.cmd ci`, `npm.cmd audit --json`, full `npm.cmd run test:all`, TypeScript/build and production web image rebuild, then repeat relevant runtime/E2E. Existing Goal/Context/Scope/AC baseline remains otherwise frozen; security verification must be reported accurately before completion.

### 2026-10-15 — IN_PROGRESS -> VERIFYING

- Native completed compatibility, active E2E port and the approved single-dependency patch; runtime implementation is now frozen for final verification. Main independently reviewed facade/auth/consumer diffs, the unchanged Figma runtime entry/layout, test-only legacy imports, all four ported E2E modules and config, host-test fixture changes, and the lockfile delta. No required code finding remains at this checkpoint; final independent review has not yet been recorded.
- Native real E2E: eight passed, zero skipped, on the pre-security-rebuild production web. Two exploratory test failures were selector/return-route assumptions fixed only in tests. This result is not counted as final evidence for the patched image. Real API-only versus UI coverage is explicit in E2E test names/comments; no unsupported management UI was added. Browser trace/video/screenshots are disabled to avoid persisting authentication payloads.
- Main browser also verified actual logout and unauthenticated protected redirect, keyboard access to UserMenu, warehouse navigation exactly inventory/warehouses/inbound/outbound, and client navigation exactly products/inventory/warehouses with no product create/edit controls. Temporary viewport override was reset. A pointer-action error during viewport restoration was recovered with a fresh DOM snapshot and semantic keyboard interaction; it was not counted as an application failure.
- Main confirmed the security patch changes only three lockfile metadata lines (version/resolved/integrity) relative to backend input `77e5c4d`. Native post-patch clean install/audit, 156+90 frontend tests, build/TypeScript and standalone E2E/config type check passed. Main fresh full backend, clean frontend/audit, production-image rebuild and final E2E are now running independently.

### 2026-10-15 — VERIFYING -> REVIEWING; review round 1 -> IN_PROGRESS

- Main final post-security-patch verification completed: clean frontend install, npm audit zero vulnerabilities, Vitest 156/22 plus Node-host 90 with zero skips/failures, build 90 modules, app TypeScript and standalone E2E/config TypeScript PASS. Rebuilt production web from the patched lockfile (Docker clean install also reports zero vulnerabilities); reran real production E2E independently: eight passed, zero skipped, 11.5 seconds. Fresh full backend against disposable PostgreSQL: 459 passed, two dependency deprecations; Ruff PASS. Web runtime user is 101 (non-root).
- Entered independent REVIEWING. Review round 1 found no remaining required runtime/code defect, but found an Important documentation mismatch inherited from the backend parent: README/runbook frontend command runs only Vitest rather than the complete retained suites; architecture describes old feature-router/TanStack runtime and three old E2E paths, although active Figma entry and eight current E2E paths are verified. README's completion-evidence pointer is historical rather than this task's integration authority. API documentation should state newly enforced required JWT claims and movement DB bounds/overflow contract.
- Root cause is preserved historical operational/architecture documentation not yet reconciled with the retained Figma runtime, not a failed application gate. Required correction returns REVIEWING -> IN_PROGRESS before edits. Native is limited to README, architecture/API contract and runbook accuracy; do not edit PROGRESS or any historical task/state/plan. Preserve historical approval claims as provenance, not new completion evidence. No runtime or baseline expansion is authorized by this correction.

### 2026-10-16 — Documentation correction verified; IN_PROGRESS -> VERIFYING

- The sole native implementer corrected only README, the architecture document, API contract and operations runbook. Main independently reviewed their complete diffs against the actual entry points, auth/API implementation, package scripts, E2E configuration and eight scenario declarations. These corrections do not change runtime behavior, the frozen baseline, historical task states or historical completion records.
- Documentation now distinguishes the active Figma UI from retained test-only legacy modules and backend-only capabilities, identifies the complete frontend test command, and describes required JWT claims, movement bounds/atomic overflow, migration/seed safety and guarded isolated E2E accurately. Markdown fences and `git diff --check` pass. Runtime/code is unchanged since the final independently completed gates recorded above.

### 2026-10-16 — VERIFYING -> REVIEWING; independent review round 2

- Main rechecked the round-1 documentation finding and reviewed the integration resolution against both parents. No required finding remains. Backend runtime/migrations/tests match `77e5c4d`; approved Figma entry, router, layout, styles and assets match `1cba4cb`. API/provider/consumer compatibility, active versus legacy test coverage, real E2E boundaries and the single-package lockfile amendment were reviewed separately.
- Pre-commit review is APPROVED, subject to exact staging/exclusion/secret checks and the resulting merge-ancestry proof. AC-2 remains unverified until an actual two-parent local merge commit exists. The target frontend checkout must remain unchanged, as explicitly requested by the user. This review does not approve a push or completion of historical tasks.

### 2026-10-16 — Final independent rerun and exact staging

- Main reran the complete integrated backend suite against the guarded disposable checkpoint database: 459 passed, two existing dependency deprecations, 82.68 seconds; Ruff PASS. Main frontend rerun: Vitest 156/22, Node-host 90, build 90 modules, application TypeScript and npm audit zero vulnerabilities, all PASS. Main real production E2E rerun: eight passed, zero skipped, 10.7 seconds; standalone E2E/config TypeScript PASS. No runtime source changed between these reruns and staging.
- Exact allowlist covers backend-parent incoming paths plus reviewed Figma compatibility/tests and this task ledger. All 18 index conflicts are resolved; unchanged Figma entry/router/styles and current workflow records do not enter the resulting changed-file set. Staged diff contains 202 changed paths, 16,631 insertions and 1,591 deletions before this log addition, including inherited backend history rather than 202 newly authored changes.
- Staged-path exclusion and conflict-marker checks pass. Bounded private-key/JWT/provider-token signature scan of all 200 non-deleted staged text files found zero matches, with values suppressed. Environment-example assignments are empty or explicit placeholders. An initial scanner false positive came from a whitespace matcher crossing an empty password line into the following configuration key; a horizontal-whitespace-only matcher confirmed the empty value without printing it. Markdown fences and staged/unstaged diff checks pass.
- The first exact `git add` attempt safely stopped on two already-staged backend deletions absent from both index and working files. The corrected explicit allowlist includes only existing/indexed paths and retains those already-staged deletions; no source file was deleted by this staging step. No unexpected path was staged. Review remains APPROVED; the next checkpoint is a normal two-parent local merge, not history rewriting or adoption into the original checkout.

## Verification Evidence

### Focused

- Backend corrective RED/GREEN evidence: six unit cases, five PostgreSQL API cases and one concurrent overflow case failed before the JWT/input/atomic-overflow fixes, then passed. Seed/migration source checks: 46 passed. Main independently verified the corrected isolated backend before its six logical commits.
- Active Figma API/provider/router regressions cover authenticated catalogue calls, complete pagination, structured localized errors, protected return destinations, hydration/logout/current 401 and stale-session races. Actual page-mutation regressions ensure an old 401 cannot clear a newer session. Legacy test results are not substituted for active-router evidence.

### Regression

- Main full integrated backend: `python -m pytest -q --tb=line --show-capture=no`, using the backend source virtualenv and dedicated `sw_phase1_checkpoint_test` PostgreSQL on loopback 55439: **459 passed, zero skipped/failed**, two dependency deprecation warnings. `python -m ruff check app tests alembic`: PASS. Tests include actual PostgreSQL migrations, seed, constraints, current-role RBAC, transactions and concurrent inventory behavior. No development database was used.
- Main post-patch frontend clean `npm.cmd ci --ignore-scripts --no-audit --no-fund`: PASS; `npm.cmd audit --json`: **zero vulnerabilities**. `npm.cmd run test:all`: **156 Vitest tests / 22 files plus 90 Node-host tests**, zero failures/skips. `npm.cmd run build`: PASS, 90 modules; `npx.cmd tsc --noEmit`: PASS. Standalone E2E/config type checking with bundler resolution and ES2022: PASS.
- Production API/migration/bootstrap and patched web image builds: PASS. Isolated Compose project `sw-phase1-figma-integration-20261015-e2e` uses its own volume and web origin `http://127.0.0.1:58081`, with no published DB/API ports. Migration head 0002, repeat bootstrap three users -> three, API readiness and deep-link serving pass. Runtime image users are non-root; backend image excludes source tests, environments and Git metadata.
- Main final `E2E_BASE_URL=http://127.0.0.1:58081 npm.cmd run e2e`: **eight passed, zero skipped**, 11.5 seconds after patched production rebuild. Real UI covers login/refresh through `/auth/me`, logout/token cleanup, invalid 401, role-aware navigation/guards, current-role 403/session retention, product CRUD/conflicts, warehouse create/read/edit, inbound/outbound/409 atomic rejection, stock/history and dashboard changes. Explicit real API steps cover backend-only registration/client restriction, user/audit and directory mutations, plus warehouse deletion. No mock application data or success-response interception.
- Main manual browser and Figma node 5:3 comparison: real isolated login/logout/protected reload and all three role menus; desktop 1440px with sidebar 248px, topbar 72px and Inter; 13 observed static images loaded; 390px mobile check has no horizontal document overflow or broken images. Screenshots are local ignored artifacts. This bounded comparison does not certify every screen as pixel-perfect. No unsupported management UI or password-recovery backend was invented.

### Static and Diff

- Repeated `git diff --check`: PASS. Backend runtime/test equivalence and Figma runtime/layout preservation checks: no unexpected diff. Approved security amendment changes only source-map-js version/resolution/integrity metadata from 1.2.1 to 1.2.2 relative to backend lockfile; no other dependency upgrade.
- Bounded secret scan of 511 distinct local-history text blobs found zero private-key/JWT-literal/common provider-token signature matches. Complementary inspection of two environment-history blobs found zero non-placeholder credential candidates; only counts/paths, never credential values, were logged. Pattern-based scans are not a guarantee against every possible secret. Final staged-path/content scan and ancestry checks are required before completion.
- Source frontend HEAD remains `1cba4cb`; its unrelated production-plan working blob remains `a01e78aecfc230e2d31d98b1f1624b8d3e31453b`. Twelve original dirty backend files were hash-compared with their preserved snapshots. Unknown files, `.env`, personal `.docx`, local configuration, generated artifacts and dependencies remain excluded. No push, destructive Git or source-worktree cleanup occurred.

## Review Result

- Result: APPROVED (main-agent independent review round 2; final staging/ancestry checks pending)
- Round 1 required finding: inherited operational/architecture/API documentation did not accurately describe the integrated runtime and complete verification command. Corrected by the sole native implementer; independently reviewed and resolved in round 2.
- No unresolved required code/runtime finding. Scope limitations remain explicit: historical backend-only management features have no newly approved Figma UI; password recovery is unavailable; visual verification is bounded, not a full pixel-perfect audit.

## Completion Evidence

- Not completed.
