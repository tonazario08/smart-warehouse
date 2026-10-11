# post-commit-audit-c0727c4 — Post-commit audit and task-state reconciliation

## Metadata

- Status: VERIFYING
- Phase: post-commit audit
- Plan: User-approved audit brief in this conversation, 2026-10-09
- Depends on: none
- Created: 2026-10-09
- Started: 2026-10-09
- Completed: not completed

## Goal

Audit the repository snapshot through commit `c0727c4` independently, remove uncommitted capture and secret-like configuration residue, and reconcile task status records with evidence without overstating browser or Figma verification.

## Context

Commit `c0727c4` contains the backend, frontend, workflow, and Phase 1–2 documentation commits. The primary working tree also contains uncommitted configuration, capture tooling, and Phase 3–8 plus migration task records that require evidence-aware review before any supplemental commit.

## In Scope

- Verify `c0727c4` in a separate clean worktree with the complete backend test suite and frontend production build.
- Scan every commit reachable from `c0727c4` but absent from remote refs for common secret forms without logging secret values.
- Restore a non-secret placeholder in `.env.example` while retaining legitimate documented configuration.
- Remove the Figma capture script from `client/index.html` after confirming it is capture-only.
- Normalize the existing Phase 2 review-result enum from `PASS` to `APPROVED` only if its recorded evidence already satisfies the workflow; this is not a new review.
- Reconcile Phase 3–8 and migration acceptance criteria one by one against recorded evidence and fresh verification. Leave browser or Figma criteria unchecked when the audit does not independently verify them.
- Correct task statuses that do not satisfy `DONE`, preserving historical entries and recording an explicit audit correction.
- Present verification results and the complete audit diff before staging or committing.

## Out of Scope

- New application behavior, backend endpoints, frontend features, dependency upgrades, or package-manager changes.
- Re-running browser or Figma visual verification.
- Deleting files of unclear purpose, modifying unrelated plans or reports, rewriting Git history, pushing, or creating a pull request.
- Staging or committing before explicit user review of the audit diff.

## Acceptance Criteria

- [x] AC-1 — A clean worktree at exactly `c0727c4` passes the full backend suite and frontend production build without using uncommitted project files.
- [x] AC-2 — Every commit reachable from `c0727c4` but absent from remote refs is scanned for common secret forms without printing candidate values, and `.env.example` contains a documented placeholder rather than a secret-like value.
- [x] AC-3 — The Figma capture script is confirmed to be capture-only and removed from the application HTML.
- [x] AC-4 — Phase 2 uses the allowed `APPROVED` review-result enum only on the strength of its existing recorded review evidence, with no fabricated new review.
- [ ] AC-5 — Phase 3–8 and migration criteria and statuses match specific recorded or freshly reproduced evidence; unverified browser or Figma claims remain incomplete, and no start date is guessed.
- [ ] AC-6 — The audit changes only approved files, passes static diff checks, remains unstaged, and is presented for user approval before any supplemental commit.

## Verification Commands

### Focused

- In the isolated `c0727c4` worktree: `.venv\\Scripts\\python.exe -m pytest -q` using the existing external test environment.
- In the isolated `c0727c4` worktree `client/`: `npm.cmd ci` followed by `npm.cmd run build`.
- Safe Git-tree secret scan over `git rev-list HEAD --not --remotes`, reporting only commit, path, and rule category.

### Regression

- Confirm the isolated worktree remains clean after tests and build.
- Confirm `.env.example` contains the approved placeholder and `client/index.html` has no Figma capture reference.
- Compare every affected task's status, AC checklist, review result, and completion evidence.

### Static and Diff

- `git diff --check`
- `git status --short`
- `git diff -- .env.example client/index.html docs/tasks/phase-2-app-shell-routing.md docs/tasks/phase-3-dashboard.md docs/tasks/phase-4-products.md docs/tasks/phase-5-inventory.md docs/tasks/phase-6-warehouses.md docs/tasks/phase-7-inbound-outbound.md docs/tasks/phase-8-authentication.md docs/tasks/migration-seed-regression.md docs/tasks/post-commit-audit-c0727c4.md`
- `git diff --staged --name-only`

## Progress Log

### 2026-10-09 — READY -> IN_PROGRESS

- Dependencies: none.
- The user-approved audit brief is the plan authority for this bounded reconciliation task.
- Goal, context, scope, acceptance criteria, and verification commands are frozen.
- The isolated `c0727c4` worktree was created and baseline verification evidence was collected before primary-working-tree edits.
- Implementation started without staging, committing, pushing, rewriting history, or deleting unclear files.

### 2026-10-09 — IN_PROGRESS -> VERIFYING

- Restored the JWT example placeholder while preserving the legitimate CORS example.
- Removed the capture-only Figma script reference.
- Normalized Phase 2 review metadata without creating a new review.
- Reconciled every Phase 3–8 and migration AC against recorded browser/Figma/API evidence, source inspection, and fresh clean-worktree test/build evidence.
- Corrected missing start dates only where an existing dated `READY -> IN_PROGRESS` entry supplied the exact date.
- No application source, dependency, Git history, unclear file, remote state, or out-of-scope document was changed by this audit.

### 2026-10-11 — VERIFYING -> IN_PROGRESS

- The independent read-only audit identified one reproduced application defect and two evidence gaps that invalidate the previous blanket completion statements.
- Return to IN_PROGRESS before correcting documentation. The frozen requirements and scope remain unchanged; only this selected audit task is updated.
- Preserve the historical Phase 2–8 and migration records, existing user changes, and all application source. No staging, commit, browser/Figma run, or secret-scan rerun is authorized by this correction.

### 2026-10-11 — IN_PROGRESS -> VERIFYING

- Corrected AC-5 to NOT VERIFIED and replaced the overstated regression conclusions with the distinction between historical checklist marks and available proof.
- Recorded the three findings from the preceding read-only audit below. Historical task records and application code remain unchanged; the proven pagination defect is not repaired by this documentation-only correction.
- AC-6 remains unchecked and the formal Review Result remains PENDING. This transition records readiness to verify the documentation correction, not audit completion or approval.

## Verification Evidence

### Focused

- Clean managed worktree: `C:\Users\TQUOCTOAN\.codex\worktrees\review-c0727c4\smart-warehouse` at `c0727c41a666dd174ef7b912a41a24bac763e1e3`, detached HEAD.
- Backend command: external existing test-environment Python invoked `-m pytest -q` with the worktree as current directory.
- Backend result: PASS, 54 tests passed with two existing dependency deprecation warnings.
- Frontend commands in the worktree `client/`: `npm.cmd ci`, then `npm.cmd run build`.
- Frontend result: PASS, TypeScript and Vite completed; 77 modules transformed.
- Dependency observation: `npm audit` reports one high-severity indirect finding in `source-map-js@1.2.1` through Vite/PostCSS. No dependency or lockfile change is in scope.
- Secret scan: eight commits returned by `git rev-list HEAD --not --remotes` were checked for committed environment files, private-key markers, common provider token shapes, JWTs, and sensitive assignments. Result: zero findings. Candidate values were never printed.

### Regression

- The isolated worktree remained clean after dependency installation, backend tests, and frontend build.
- `.env.example` now contains `JWT_SECRET_KEY=replace-with-a-long-random-secret`; the secret-like uncommitted value is absent.
- Repository search excluding dependency/build directories returns zero Figma capture references. The removed script had been the only reference and was not consumed by application code.
- Historical Phase 2 through Phase 8 and migration records currently mark all ACs checked, contain dated start metadata, and use `Result: APPROVED`. Those existing marks are not an independent audit conclusion: the pagination defect and the Phase 4 CRUD and Phase 4/6 create-render evidence gaps below leave audit AC-5 NOT VERIFIED. This correction does not change those historical task files or guess start dates.
- Recorded Figma inspection or approval and browser evidence cover specific routes and states only. Phase 4 records list/edit rendering but no create-render check or completed create/update/delete submissions; Phase 6 records list/detail/edit rendering but no create-render check. Source reuse of the shared forms and passing build/tests do not supply the missing browser/Figma proof. No new visual verification is claimed.

### Independent read-only findings recorded on 2026-10-11

- F-1 — P1, proven application defect at `c0727c4`: `client/src/pages/InventoryPage.tsx:33`, `client/src/pages/StockDetailPage.tsx:30`, `client/src/pages/WarehousesPage.tsx:31`, `client/src/pages/WarehouseDetailPage.tsx:33`, and `client/src/pages/DashboardPage.tsx:34` request only the first 100-product page through `api.products()`. `client/src/shared/lib/inventory.ts:25` drops stock rows whose product is absent, and `client/src/shared/lib/dashboard.ts:48` substitutes a zero reorder threshold for an absent product. The preceding read-only audit imported these helpers directly from the clean worktree and reproduced, in memory, product 101 yielding zero inventory rows with the first page versus one with the complete product list; the Dashboard returned backend low-stock count 1 but zero alert rows and a healthy status. Consequence: omitted stock/detail records, understated warehouse totals, and misleading Dashboard alerts when products span multiple pages. This is a code defect affecting Phase 3/5/6 evidence, not merely missing proof; repairing application behavior is outside this audit baseline.
- F-2 — P2, missing Phase 4 frontend CRUD proof: `docs/tasks/phase-4-products.md:49` requires authenticated list, create, edit, and delete verification against real API responses. Its recorded browser evidence at line 99 covers list/filter controls, the edit route and prefilled form, categories, and supplier empty state, but records no successful create, update submission, or delete. Source API calls and backend CRUD tests support the contracts without proving the frontend submission wiring. Consequence: the recorded Phase 4 AC-5 completion is not fully substantiated by its mandatory regression evidence. This does not establish that CRUD is broken; it establishes missing browser/API proof that this audit does not rerun.
- F-3 — P2, missing Phase 4/6 create visual proof: `docs/tasks/phase-4-products.md:85` and `docs/tasks/phase-6-warehouses.md:82` infer their create-route AC-1 coverage from source inspection of shared create/edit forms. Their browser evidence at lines 99 and 96 respectively records edit rendering but no `/products/new` or `/warehouses/new` rendering check. Consequence: sharing a component does not independently establish that create-mode defaults, titles, and layout satisfy the approved Figma structures, so this audit cannot certify those portions of the historical AC-1 marks. This is missing visual proof, not a demonstrated Figma mismatch; no browser/Figma rerun occurred.

### Static and Diff

- `git diff --check`: PASS.
- `git diff --staged --name-only`: empty; no file is staged.
- Scope check: audit edits are limited to `.env.example`, the removal that restores `client/index.html` to committed content, Phase 2–8 and migration task records, and this audit task.
- Existing unrelated modified and untracked files remain untouched.

## Review Result

- Result: PENDING
- Findings: the initial read-only findings F-1 through F-3 are recorded above; formal review is not completed, and no new approval is claimed.

## Completion Evidence
