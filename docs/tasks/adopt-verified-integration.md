# adopt-verified-integration — Adopt the verified backend/Figma integration locally

## Metadata

- Status: REVIEWING
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

### 2026-10-16 — Preservation checkpoints and expected merge conflict

- Created local documentation checkpoint `32ece07` for this task/plan, then separate `b46455ada3e7188bf078645896c726a3812b7453` (`docs: preserve pre-adoption Phase 1 planning draft`). The preserved plan blob is exactly `a01e78aecfc230e2d31d98b1f1624b8d3e31453b`. Before each checkpoint, main inspected status, staged/unstaged scope, exact blob/allowlist, Markdown fences, diff checks and bounded secret signatures; no unknown file entered either checkpoint.
- Normal `git merge --no-commit --no-ff 2abdabe` started in the approved target. It produced only the expected conflict in the historical plan. Native is authorized solely to resolve that file to the approved integration blob `4e4ed99cd50872e42fdcfab8f27d8091386b2587`; no runtime correction or other task edit is authorized. MERGE_HEAD remains `2abdabe` until verification/review and commit.
- Native read-only preflight confirmed `tsconfig.app.json` includes all `src`, host-test preparation copies all `src`, and Docker build copies its context. Therefore compiling the dirty target directly would ingest the unrelated untracked `client/src/pages/LegacyProductsPage.tsx`. Its contents were not read, moved, modified or deleted; no build has yet consumed it.
- Ruling: honor the approved prohibition on unknown build inputs by running backend verification in the adopted target and frontend gates in the existing clean integration checkout, only after exact tracked frontend/runtime/config/lockfile equivalence with the adopted index is proved. Repeat fresh gates and E2E against that identical tracked runtime, not old results; all new evidence is recorded only here. This is a verification workspace choice, not a source/config change or baseline relaxation. Cost if wrong: a direct build of the user's dirty checkout might differ because of excluded personal files, so it must remain explicitly NOT VERIFIED and never be claimed PASS. Do not alter tsconfig, .gitignore or Docker context to hide the unknown file.

### 2026-10-16 — Expected resolution completed; IN_PROGRESS -> VERIFYING

- Native resolved only the approved historical plan using apply_patch. Main independently verified the original checkpoint blob `a01e78a` and current incoming blob `4e4ed99cd50872e42fdcfab8f27d8091386b2587`; `git diff --check` passes. No runtime source or other historical document was manually changed. Main marks this sole conflict resolved in the index; merge commit remains pending verification/review.
- Main proved all tracked adopted backend/frontend/tests/configuration/lockfile paths equal clean integration HEAD `2abdabe`, whose verification checkout has no tracked/untracked changes. Fresh frontend clean install/tests/build/types/audit started there; these are new adoption verification runs, not reuse of old test counts. Untracked LegacyProductsPage original SHA256 is `039331FB2ED71FDC0FF955E23209E9ABE7E6D03F9E9BA7A591C6C9913393A86A` (content not read); it must remain unchanged and excluded.
- Docker Linux engine is currently unavailable (named pipe not found). Attempted supported `docker desktop start` without resets or data cleanup; restoration is pending. PostgreSQL/production E2E remain NOT VERIFIED for this adoption until the exact disposable targets are reachable. Do not substitute prior integration results or mock responses.

### 2026-10-16 — Fresh frontend gates and Docker port blocker

- Main fresh clean tracked-runtime verification completed: `npm.cmd ci --ignore-scripts --no-audit --no-fund`, Vitest 156 tests / 22 files plus 90 Node-host tests, production build 90 modules, application and standalone E2E/config TypeScript, and npm audit zero vulnerabilities: all PASS. Verification ran in the clean integration checkout after tracked runtime equivalence, not the dirty checkout containing the unknown LegacyProductsPage. A direct dirty-target frontend build remains NOT VERIFIED.
- Main target backend without PostgreSQL: 142 passed; Ruff PASS. Two existing dependency deprecations plus a local OneDrive pytest-cache warning occurred. No cache was deleted; the full PostgreSQL rerun disables only pytest's cache provider to avoid this local cache-write warning.
- User confirmed Docker running; server 29.7.2 is reachable. Independently inspected the exact owned checkpoint test DB and isolated production project/container/volume identities, then restarted only those verification containers. Checkpoint DB on loopback 55439 is ready; production API is healthy. No migration, reset, deletion or write to development data occurred. Full 459-test backend rerun is in progress.
- Production web cannot restart: Docker reports Windows socket access denied on host 58081. Read-only `netsh interface ipv4/ipv6 show excludedportrange protocol=tcp` confirms reserved range 58049–58148 covers both allowed E2E ports 58080/58081; no existing listener was found. A temporary bind/release probe on loopback 18081 succeeds. This is an environment blocker, not a code-test failure. No firewall, reservation, registry or network service change was attempted.
- Requested an explicit bounded scope amendment: add only loopback 18081 to E2E guard and use that port for the same isolated web runtime, with focused guard checks and fresh real E2E. Approval is pending; no test-config edit or fallback web recreation has occurred. Mandatory runtime evidence remains NOT VERIFIED until this blocker is resolved.

### 2026-10-16 — Approved scope amendment; VERIFYING -> IN_PROGRESS

- Approver: human user, explicit reply `Duyệt dùng cổng 18081 cho E2E`, 2026-10-16, to the bounded port/guard proposal. Reason: Windows reserved ports prevent binding both originally allowed E2E ports; loopback 18081 was successfully probed. This is an environment-driven test-only amendment, not permission to change system network policy or application behavior.
- Additional allowed file: `client/playwright.config.ts`, solely adding loopback port `18081` to its existing explicit allowlist, retaining HTTP-only, loopback-only, no-credential and existing port restrictions. Use the same owned isolated web image/network/API/database at port 18081. No API/frontend runtime, framework, package, firewall, reserved-range, registry, unknown file or Docker data deletion is approved.
- Additional verification: native must demonstrate the new target fails the existing guard before the patch and is accepted afterward via Playwright test discovery; confirm non-loopback, HTTPS, credential-bearing and unrelated-port targets remain rejected. Main independently reviews the one-line diff, standalone E2E TypeScript and real eight-scenario E2E at `http://127.0.0.1:18081`. Runtime equivalence excludes only this explicitly approved test-config delta. Remaining frozen baseline is unchanged.
- Main full target backend rerun finished: 459 passed, two existing dependency deprecations, 78.26 seconds, with cache provider disabled; Ruff PASS. Staged path/conflict-marker/secret signature checks pass: 200 non-deleted staged files, zero signature findings, values suppressed. Unknown LegacyProductsPage SHA256 remains unchanged.

### 2026-10-16 — Approved E2E guard amendment complete; IN_PROGRESS -> VERIFYING

- Native demonstrated RED: the original guard rejects loopback 18081. Added only `'18081'` to its port allowlist; GREEN discovery finds eight scenarios / three files. Four invalid target classes remain rejected (non-loopback HTTP, HTTPS, credential-bearing URL, unrelated 18082); both old ports and localhost:18081 still discover eight scenarios. Main independently reviewed the exact one-line diff; no application or dependency change.
- Started new task-owned `sw-phase1-figma-adoption-20261016-web`, bound only to `127.0.0.1:18081`, using the existing isolated project's network and existing tagged production web image. Kept the original stopped 58081 web container and all volumes/data intact. API is healthy; proxied readiness and `/products` deep-link serving both return 200. Runtime user remains non-root 101.
- Two verification diagnostics were resolved without code edits: Docker's old container leaf image ID is not a runnable image reference after restart, so the existing named local image was used with `--pull=never`. An initial asset comparison against the default local build differed because Docker explicitly builds with `VITE_API_BASE_URL=/api/v1`, whereas the local default targets localhost:8000. A fresh clean build with Docker's exact `/api/v1` environment produced the same JS filename and SHA256 contents: HTML, JS, CSS and Inter font all four match the running image. This proves the tested production artifacts, rather than assuming image-tag equivalence. No environment file was read/changed or frontend API behavior patched.
- Runtime/configuration paths remain identical to the verified integration except the explicitly approved test-only port guard. Fresh actual E2E and E2E/config TypeScript now run from the adopted target, loading only their explicit test/config modules, not the unknown untracked application source. Trace/video/screenshots remain off; no development data is used.

### 2026-10-16 — Fresh real E2E passed; VERIFYING -> REVIEWING

- Main executed the adopted checkout's actual Playwright suite with `E2E_BASE_URL=http://127.0.0.1:18081`: eight passed, zero skipped, 11.3 seconds. Its isolated production API/database and web were live, with real UI/API writes and no mock success responses. Explicit E2E/config TypeScript passed. No unknown application source was compiled by this explicit test-module run.
- Main independently repeated test discovery for the approved new loopback port (eight tests / three files), then four negative guard classes: external host, HTTPS, credential URL, unrelated 18082. All results matched their expected exits; invalid URL details were suppressed. Root clean locked dependency install completed without lifecycle scripts; package manifest/lockfile are unchanged.
- Main enters independent REVIEWING: verify exact approved three-file delta versus source integration (this task, its stable plan and the one-line test guard), original draft recovery/current-plan blob, unchanged Figma/runtime/API/configuration, unknown-file exclusions and source ancestry. Required findings must return to IN_PROGRESS before implementation; no further runtime changes are proposed.

## Verification Evidence

- Source preservation: original draft checkpoint `b46455a` contains exactly blob `a01e78aecfc230e2d31d98b1f1624b8d3e31453b`; resolved current historical-plan blob is `4e4ed99cd50872e42fdcfab8f27d8091386b2587`. Expected sole merge conflict is resolved, with no runtime resolution edits.
- Main target backend: full PostgreSQL-backed `python -m pytest -q --tb=line --show-capture=no -p no:cacheprovider`, guarded checkpoint database on loopback 55439, **459 passed / zero skipped or failed**, two dependency deprecation warnings, 78.26 seconds. `python -m ruff check app tests alembic`: PASS. Earlier non-PostgreSQL-only run: 142 passed, with two existing deprecations plus local pytest-cache warning; no cache was deleted.
- Main frontend after proving tracked runtime equivalence to clean integration HEAD: locked clean install; `npm.cmd run test:all` **156 Vitest tests / 22 files + 90 Node-host tests**, zero failures/skips; build 90 modules; application TypeScript; standalone E2E/config TypeScript; npm audit **zero vulnerabilities**, all PASS. Runs use the clean tracked-source checkout to exclude unknown local source, not copied prior results. Direct dirty-target application frontend build is explicitly **NOT VERIFIED**.
- Main additional production-proxy build with Docker's `VITE_API_BASE_URL=/api/v1`: PASS; SHA256 of generated HTML/JS/CSS/Inter font all four matches running task-owned production web on loopback 18081. Readiness and deep-link HTTP 200; web user 101. No app code, framework, package, environment file, system network policy or development database change.
- Main real adopted-checkout E2E at `http://127.0.0.1:18081`: **8 passed / zero skipped, 11.3 seconds**. Scenarios cover real login/me/refresh/logout/401, three roles/navigation/route guards, live role-change 403 session retention, product/warehouse CRUD and conflicts, inbound/outbound/409 stock atomicity/history/dashboard; API-only capabilities are explicitly identified by existing tests. E2E/config TypeScript PASS; no credential capture, fake business data or development-origin writes.
- Main independent guard verification: accepted loopback 18081 discovers eight tests; non-loopback/HTTPS/credential-bearing/unapproved-port targets all reject. Native recorded prepatch RED/postpatch GREEN and compatibility of original ports. Staged/unstaged diff checks, conflict-marker checks, exact staged scope and bounded secret scan pass; final ancestry checks await actual merge commit.

## Review Result

- Result: APPROVED (main independent review, pending final exact staged checks and actual local merge-ancestry proof)
- Spec compliance and quality: preservation policy matches explicit user approval; exact incoming plan is retained while its predecessor is recoverable from a separate checkpoint. Runtime/API/Figma files match verified integration; the only code/config delta is the explicitly approved one-line E2E port addition, covered by RED/GREEN, negative guards, TypeScript and actual E2E.
- No unresolved required finding. Direct dirty-target frontend build remains NOT VERIFIED by design to exclude unrelated source; clean tracked-runtime gates and artifact equivalence are the stated evidence, never represented as a dirty-target build. Existing operational documentation still lists the original E2E ports; the approved additional port is documented in this task, with no unauthorized expansion to historical documentation. Scope limitations of the dependency remain unchanged.

## Completion Evidence

- Not completed. Task/plan and original draft checkpoints exist; approved target merge is resolved but not committed while mandatory verification is pending. No push or development data change occurred. Owned disposable verification services were restarted; no Docker data was reset or removed.
