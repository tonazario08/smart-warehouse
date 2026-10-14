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

## Verification Evidence

### Focused

- Pending fresh source checkpoint verification.

### Regression

- Pending integrated verification; old test counts do not prove the merged tree.

### Static and Diff

- Preflight found both source worktrees dirty and incompatible catalogue/list assumptions. No files were staged, no merge was attempted, and no remote operation occurred.

## Review Result

- Result: PENDING
- Findings: not reviewed as an integrated tree

## Completion Evidence

- Not completed.
