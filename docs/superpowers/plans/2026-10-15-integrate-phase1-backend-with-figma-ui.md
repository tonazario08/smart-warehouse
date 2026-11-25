# Phase 1 Backend and Figma UI Integration Implementation Plan

> For agentic workers: use subagent-driven-development with the user's single native implementer and main-agent independent review. Repository single-task rules override additional task IDs, separate ledgers and automatic cleanup. All new execution evidence belongs to `docs/tasks/integrate-phase1-backend-with-figma-ui.md`.

**Goal:** Integrate the existing Phase 1 backend lineage and verified pending corrections with the approved current Figma frontend without losing history or dirty source work.

**Architecture:** Preserve FastAPI service/repository ownership and contracts from backend source `3446ae3`; retain the current Figma React page/layout foundation and adapt its API boundary to authenticated, paginated, structured responses. Perform the merge and compatibility fixes in an isolated managed worktree; do not mutate the running development database.

**Tech Stack:** Existing Python/FastAPI/SQLAlchemy/PostgreSQL/Alembic and React/TypeScript/Vite/npm/plain CSS. No new UI framework or package manager.

**Spec:** User-approved integration brief, 2026-10-15; `docs/superpowers/specs/2026-09-04-phase-1-production-ready-design.md` for backend. Executable task identifier: `integrate-phase1-backend-with-figma-ui`.

## Global Constraints

- Exactly one executable task: `docs/tasks/integrate-phase1-backend-with-figma-ui.md`.
- Preserve original commits, author dates and source dirty files; local logical checkpoints only, no push/rebase/amend/reset/automatic stash.
- Backend remains the authorization and transaction authority. Frontend visibility never replaces it.
- Preserve `smart-warehouse-token`, real API data, Vietnamese visible text, approved Figma presentation, and the existing package manager.
- Never stage `.env`, secret values, `.docx`, local editor configuration, dependencies, environments, generated screenshots/reports/build output or unknown files.
- Use isolated test databases/services for write verification; no changes to the running development database.
- No Phase 2 business implementation, no automatic worktree deletion, and no silent task-state normalization outside the selected task.

## Review Focus

- Valid user refresh/login versus delayed 401/network errors: do not resurrect an old session or erase a valid session on a transport error.
- More than 100 referenced directory/products/stock/history rows: no hidden later-page choices, partial joins or truncated totals.
- Structured backend errors and validation fields: retain status/code and render useful Vietnamese messages without leaking raw server internals.
- Existing seeded users with conflicting identity/role, and legacy normalization collisions: fail before unsafe writes; migrations and repeated seed runs are verified on disposable PostgreSQL.
- Source-worktree drift or conflicts in unrelated documents: preserve exact originals and stop for a decision if the target merge would overwrite them.

## One milestone, sequential internal workstreams

### Preserve source checkpoints

Files: known UI remediation files in `client/src/pages/`, `client/src/shared/`, `client/tests/`, local licensed font/Figma assets and unchanged historical UI task record; the new integration task and this plan. Exclude `LegacyProductsPage.tsx`, unrelated existing plan edits, `.vscode`, personal documents and unselected untracked documentation.

- [ ] Record source HEADs/status and inspect the full scoped diff, including new assets/tests; scan only candidate text safely without printing secrets.
- [ ] Run baseline backend tests, full current frontend host suite, TypeScript/build and diff check. Do not claim these validate the backend source or future merge.
- [ ] Commit the verified Figma source checkpoint and separate integration-plan documentation checkpoint. Before each commit inspect status, unstaged/staged diff and exact staged file list.
- [ ] Preserve backend HEAD `3446ae3` with a local reference; do not alter the detached source checkout or any pending patch while establishing provenance.

### Verify backend pending corrections without losing them

Files: source dirty `app/seed.py`, `alembic/versions/20260904_0002_production_baseline.py`, focused seed/migration unit/PostgreSQL tests, `client/src/shared/api/collectAllPages.ts`, related old frontend selector files/tests and operations runbook. These are existing corrections, not automatically approved implementation evidence.

- [ ] Inspect each existing patch and assign a purpose against the declared final review findings. Unknown changes remain excluded and reported.
- [ ] Copy reviewed patches into isolated integration work without resetting/stashing the original; record exact hashes/ownership and verify the source worktree still contains its changes.
- [ ] Run focused regressions demonstrating seed collision/wrong-role rejection, migration preflight collision rejection and later-page collection behavior; correct only confirmed in-scope integration defects via the native implementer.
- [ ] Create separate verified seed/migration and selector compatibility checkpoints as justified by the actual retained diff. Historical backend frontend selectors may be reused at the API-helper level without replacing Figma pages.

### Merge lineage and adapt the retained Figma frontend

Files: merge conflicts in backend/core/runtime/test files, `client/src/api.ts`, `types.ts`, `app/AuthProvider.tsx`, router/guards only as necessary, current Figma pages/shared helpers and tests, package/test configuration only when required for retained tests.

- [ ] Create a managed isolated worktree/`codex/` integration branch from the frontend checkpoint and merge backend history with original ancestry retained. Resolve conflicts explicitly; never blanket-select one side over all files.
- [ ] Preserve backend schema/services/security/audit/runtime behavior. Keep current Figma presentation; do not silently activate an incompatible second UI/router or replace pages with the old backend frontend.
- [ ] Before compatibility implementation, add focused tests expecting authenticated catalogue calls, complete page collection, status/code/field error parsing and preserved login/logout/401 behavior; run them to observe the current mismatch.
- [ ] Implement the minimal boundary and consumer adaptations, reusing shared components and preserving mutation payloads/descriptions/IDs/status. Backend response shapes and RBAC are not weakened to match obsolete client assumptions.
- [ ] Run the covering tests, then full integrated backend/frontend, type/build and diff checks. Group further local commits by actual functionality, not by mixing all changes into a merge resolution dump.

### Verify the actual integrated tree and hand off

- [ ] Run the disposable PostgreSQL auth/RBAC, migration/seed, inventory atomicity/concurrency gates and full applicable tests. Record skips, unavailable Docker/database dependencies and failures as NOT VERIFIED, not PASS.
- [ ] Verify real isolated browser/API login, protected refresh, logout/invalid-token cleanup, role visibility, product reads/CRUD and movements/stock/rejection; compare retained Figma shell/pages at desktop and narrow widths. No mocks replace runtime data.
- [ ] Main agent independently reviews the full integration diff and every frozen AC. Required findings return the selected task to IN_PROGRESS before corrections; maximum three fix/test/review rounds unless user approves more.
- [ ] Verify both source ancestors in integrated HEAD and absence of secret/generated/unknown files in new commits. Report source hashes, local checkpoints, tests and preserved exclusions.
- [ ] Merge the verified integration into `feat/figma-ui-v2` only when it cannot overwrite unrelated dirty changes. Otherwise keep both source worktrees and the verified integration branch intact and request the exact necessary decision. Do not push or clean up worktrees automatically.
