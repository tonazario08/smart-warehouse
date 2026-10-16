# adopt-verified-integration — Adopt the verified backend/Figma integration locally

## Metadata

- Status: IN_PROGRESS
- Plan: docs/superpowers/plans/2026-10-16-adopt-verified-integration.md
- Specification: user-approved local-adoption brief in this conversation, 2026-10-16; declared dependency for retained runtime contracts and integration evidence
- Depends on: docs/tasks/integrate-phase1-backend-with-figma-ui.md
- Created: 2026-10-16
- Started: 2026-10-16
- Completed: not completed

## Goal

Adopt the verified integration commit into `feat/figma-ui-v2`, preserve the existing uncommitted historical-plan draft and all unknown/local files, then independently verify the adopted tree without publishing.

## Context

- User approved creation of this exact proposed task by replying `duyet` on 2026-10-16, the explicit creation exception for its nonexistent path. User then approved the detailed plan and exact preservation/resolution policy by replying `DUYEETJ` on 2026-10-16, before any mutation of existing files or Git checkpoints.
- Target checkout: `C:/Users/TQUOCTOAN/OneDrive/Documents/ChatGPT/smart-warehouse`, branch `feat/figma-ui-v2`, HEAD `1cba4cb001aea4b81b95e93d150672b38410e100`.
- Verified integration: branch `codex/integrate-phase1-backend-figma`, HEAD `2abdabeea5969deaf7611f7478621219499b2fc7`; implementation merge `663ce56bc8b31d5eb4942bfb2645655be8eea861`. Its task is DONE/APPROVED in the authoritative integration worktree at `C:/Users/TQUOCTOAN/.codex/worktrees/phase1-backend-figma-integration/smart-warehouse`. The target checkout currently contains the earlier task snapshot; do not reopen or edit that historical record.
- Target has one tracked dirty file, `docs/superpowers/plans/2026-09-04-phase-1-production-ready.md`, plus unrelated untracked editor/report/testing/spec files and `client/src/pages/LegacyProductsPage.tsx`. Do not read legacy shared tasks under `docs/plans/`, stage unknown files, or alter the development database/environment.
- Dirty plan Git blob: `a01e78aecfc230e2d31d98b1f1624b8d3e31453b`; incoming plan blob: `4e4ed99cd50872e42fdcfab8f27d8091386b2587`. They differ. The dirty draft changes legacy implementation instructions, including removing fixture/security/test details and combining old frontend workstreams; it is not new application code or a verified completion record. Its purpose is historical planning, not authority to change current tested runtime.

## In Scope

- Inspect the exact incoming adoption diff, dependency completion evidence, source ancestry and target ownership/exclusions.
- Preserve the dirty plan with a dedicated local documentation checkpoint only after the user approves the exact preservation policy; retain its bytes in ancestry rather than silently discarding, stashing or rewriting them.
- Approved policy: checkpoint the current draft separately; merge the verified integration with a normal local merge; retain the integration version of the historical plan as the current document, while the user's draft remains exactly recoverable from its dedicated commit. Approval is recorded before READY -> IN_PROGRESS and freezes this policy with the baseline.
- Limit conflict resolution to the historical-plan overlap and this task/plan if necessary. Unexpected runtime/API/package conflicts stop adoption and require review; do not broaden implementation automatically.
- Run relevant full backend/frontend, PostgreSQL, type/build/audit, isolated production E2E and Git/secret/preservation checks against the adopted runtime. Reuse only explicitly identified disposable verification resources; no writes to development data.
- Use exactly one existing native implementer for any necessary project file correction and main-agent independent review. Do not create parallel executable tasks or additional agents.
- Record all new state transitions/evidence/review/completion only here. Make scoped verified local checkpoints; do not push.

## Out of Scope

- New features/phases, architecture or Figma redesign, dependency upgrades, API/auth/RBAC changes, migration/seed of development data.
- Updating historical task completion states or other task ledgers; reading legacy `docs/plans/` shared-task files.
- Secret values, `.env`, `.docx`, unknown reports/config/spec files, generated artifacts, build output, caches, dependencies or local environments in commits.
- Rebase/amend/reset/discard, automatic stash, branch/worktree deletion, Docker volume removal, push, PR, deployment or other remote changes.

## Acceptance Criteria

- [ ] AC-1 — Explicit preservation policy is approved before mutation; the dirty plan's exact original blob is recoverable from its own local checkpoint. All unrelated source files remain untouched and excluded.
- [ ] AC-2 — Target `feat/figma-ui-v2` retains verified integration `2abdabe`, original frontend `1cba4cb` and backend `3446ae3`/`77e5c4d` ancestry without rewriting history. The current historical plan follows the approved resolution policy.
- [ ] AC-3 — Adopted runtime source/configuration/lockfile matches the independently verified integration, except any separately approved, tested correction. No legacy shell is activated and no unapproved functional change is introduced.
- [ ] AC-4 — Full backend/PostgreSQL tests and Ruff, frontend Vitest/host tests, application/E2E TypeScript, production build and dependency audit complete with actual counts/results; missing required evidence is NOT VERIFIED.
- [ ] AC-5 — Isolated runtime/browser evidence corresponds to the adopted runtime: real login/me/refresh/logout/invalid-token cleanup, role guards, product/warehouse flows and movement atomic rejection/stock/history. No development data writes or mock runtime data.
- [ ] AC-6 — Main independently reviews all adoption/resolution diffs and links every AC to evidence; required findings are fixed and verified within at most three rounds, or a blocker is reported without DONE.
- [ ] AC-7 — Exact local commit hashes/subjects, changed files, original draft recovery reference, test results, preserved exclusions and remaining limitations are reported. No forbidden/secret/generated files are committed and no push occurs.

## Verification Commands

- Preflight/preservation: `git status --short`; `git diff -- <historical-plan-path>`; `git hash-object <historical-plan-path>`; `git rev-parse <integration-head>:<historical-plan-path>`; inspect untracked path overlaps without reading unrelated content.
- Ancestry: `git merge-base --is-ancestor 2abdabe HEAD`, repeated for `1cba4cb`, `3446ae3` and `77e5c4d`; verify preserved draft with `git rev-parse <draft-checkpoint>:docs/superpowers/plans/2026-09-04-phase-1-production-ready.md` against the recorded original blob.
- Runtime equivalence: `git diff 2abdabe HEAD -- app alembic tests pyproject.toml client .github Dockerfile docker-compose.yml docker-compose.e2e.yml docker-compose.test.yml .env.example`; inspect any delta rather than ignore it.
- Backend: existing verified Python virtualenv, `python -m pytest -q --tb=line --show-capture=no` with TEST_DATABASE_URL restricted to the approved disposable `_test` database; `python -m ruff check app tests alembic`. Verify Docker identity/loopback port before running destructive test fixtures. No secret values in logs.
- Frontend from `client/`: `npm.cmd ci --ignore-scripts --no-audit --no-fund`; `npm.cmd run test:all`; `npm.cmd run build`; `npx.cmd tsc --noEmit`; `npm.cmd audit --json`.
- E2E/config TypeScript: `npx.cmd tsc --ignoreConfig --noEmit --module esnext --moduleResolution bundler --target es2022 --skipLibCheck e2e/helpers.ts e2e/auth-client.spec.ts e2e/admin-management.spec.ts e2e/inventory-flow.spec.ts playwright.config.ts`.
- Real isolated E2E: validate project `sw-phase1-figma-integration-20261015-e2e`, private DB/API ports, own disposable volume, healthy API and web origin `http://127.0.0.1:58081`; rebuild adopted sources or prove runtime source equivalence to the existing verified images, then set E2E_BASE_URL and run `npm.cmd run e2e`. Record fresh results, not copied counts. Runtime visual evidence remains bounded; unchanged Figma preservation is not a new pixel-perfect audit.
- Before every local commit: `git status`, `git diff`, `git diff --staged`, exact staged allowlist/exclusions, bounded secret scan with values suppressed, `git diff --check` and `git diff --staged --check`.

## Progress Log

### 2026-10-16 — Task creation approved; read-only preflight

- Created this unique approved task and its plan only. No application source, historical draft, index, branch or existing task has been changed by this new task. No commit or merge has begun.
- Read repository AGENTS.md, the dependency's authoritative completion record and its stable integration plan. Source integration is DONE/APPROVED; source/target hashes and differing plan blobs are recorded above. Unknown files are left untouched; no legacy shared-task content was read.
- The user approved the general adoption scope, but has not yet approved choosing the integration's plan text over the different dirty draft. Recommended separate draft checkpoint plus incoming current-plan resolution is presented for explicit approval. Stay READY; no frozen IN_PROGRESS baseline or fabricated start date.

### 2026-10-16 — Detailed policy approved; READY -> IN_PROGRESS

- Human user replied `DUYEETJ` to the explicit proposal to checkpoint the original draft and use the integration's plan as the current document. Read AGENTS.md, this task, its plan and the dependency's authoritative DONE/APPROVED record in the integration worktree. Freeze Goal, Context, In Scope, Out of Scope, Acceptance Criteria and Verification Commands now. No start date is inferred from old tasks.
- Target is still `feat/figma-ui-v2` at `1cba4cb`; source integration is still `2abdabe`; original dirty plan still has the recorded `a01e78a` blob. There are no staged changes. The existing native implementer is resumed for scoped preflight and any approved file resolution; main owns Git checkpoints, verification/review and this sole execution ledger. Do not create another agent or another executable task.
- Ruling: execute the explicitly approved adoption in the existing target checkout, not a new feature worktree. The integration is already isolated/verified; creating another adoption worktree would not complete the requested target adoption. Cost if wrong: dirty-target blockers require a safe stop; no unrelated file may be overwritten. Existing worktrees and ignored evidence are retained, not removed.
- Ruling: repository single-task/state authority and user single-native-agent preference override skill requests for another progress ledger, fresh implementers/reviewers and automatic workspace deletion. Main independent review covers spec compliance and quality; all execution history remains here. Cost if wrong: fewer independent review seats, compensated by runtime equivalence, exact Git/blob checks and fresh full verification.

| Internal boundaries checked | Shared files/interface | Preflight result |
| --- | --- | --- |
| Draft preservation / merge resolution | Historical plan original blob versus incoming blob | Dedicated original checkpoint must exist and match before native may select incoming text. |
| Merge / verification | Backend/frontend/configuration and source commit `2abdabe` | Require exact runtime equivalence; no new feature corrections by implication. |
| Verification / excluded local files | TypeScript include set and untracked LegacyProductsPage | Native read-only preflight must establish whether unknown local source contaminates the build; do not edit/move it. |
| Single adoption milestone | Approved scope, states, verification and Git publication | Internally consistent; local merge/checkpoints authorized, push and unrelated mutations forbidden. |

## Verification Evidence

- Read-only Git identity, dirty-plan diff/hash, target/source ancestry and path inventory inspected. No adoption test/build/browser verification has run for this new task. Dependency results are provenance, not fresh adoption evidence.

## Review Result

- Result: PENDING
- Pending user approval of the exact preservation/resolution policy and plan; no adoption implementation to review yet.

## Completion Evidence

- Not completed. No target merge, checkpoint, push or data change performed.
