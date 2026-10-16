# fix-compose-seed-ci — Isolate Compose bootstrap credential tests across platforms

## Metadata

- Status: VERIFYING
- Plan: embedded single-milestone plan in this file, identifier `fix-compose-seed-ci`
- Specification: user-approved CI-only repair brief, 2026-10-16; required non-empty bootstrap credentials in `docker-compose.yml` and `docs/operations/phase-1-runbook.md`
- Depends on: docs/tasks/adopt-verified-integration.md
- Created: 2026-10-16
- Started: 2026-10-16
- Completed: not completed

## Goal

Correct the Compose/seed test-isolation defect responsible for the failed backend GitHub Actions job without weakening fail-closed credential checks or changing production behavior. Prepare an independently reviewed, verified uncommitted patch; GitHub confirmation requires a separately authorized publication and fresh workflow run.

## Context

- User explicitly approved creation/execution of this unique proposed path by replying `duyet`, after the proposal to use one native implementer and main independent review with no automatic commit/push. This is the creation exception for the previously nonexistent path, not permission to start another task.
- Baseline target: `feat/figma-ui-v2`, HEAD `98e2cbdd48af69fe2d41f2b8da0c1a5a675ee3d4`, already published. Tracked/index state is clean; unrelated untracked editor/report/spec/testing files and LegacyProductsPage remain excluded/untouched.
- Dependency is DONE/APPROVED; its old local 459/156+90/8 verification counts are provenance, not proof that remote CI passed. Do not edit or reopen that task or other historical records.
- GitHub Quality run `38872221924` on baseline HEAD: frontend successful; backend 448 passed/11 failed; E2E skipped because it depends on backend. Failure family: `tests/test_seed.py::test_compose_config_fails_closed_for_missing_or_blank_bootstrap_credentials`.
- Observed code: `compose_config_command` removes all six SEED_* variables. A parameterized negative test changes only its selected missing/empty variable but expects Docker's error to name it. Multiple absent variables let Compose report a different one. Preserve the strict nonzero exit and expected-variable assertion; repair input isolation rather than adding real CI credentials, accepting arbitrary errors, skipping tests or changing Compose security.

## In Scope

- Read the selected dependency, stable required-credential contract, failed workflow/logs and current test helper; reproduce the failure and verify root cause.
- Modify only `tests/test_seed.py`: complete deterministic test-only baseline credentials, exactly one selected missing/blank credential per negative case, and focused regressions preserving host-environment isolation and full-baseline success. Prefer minimal changes and real Compose execution over elaborate mocks.
- Use exactly one existing native implementer for test/code changes. Main owns this sole ledger and independent spec/quality review, with at most three fix/test/review rounds.
- Run focused RED/GREEN, repeated real Compose cases, full Windows backend/PostgreSQL regression and Ruff, and Linux/CI-like Python 3.12 Compose verification where feasible. All PostgreSQL writes must target the existing explicitly identified disposable `_test` database/container only.
- Task-specific generated Docker verification contexts/images/containers may be created under an already ignored cache and from tracked source only, without mounting project secrets/unknown files or the Docker daemon socket. Preserve existing development/runtime data and services.
- Keep missing/blank credentials fail-closed in the unchanged production Compose file. No production/API/auth/RBAC/frontend change or new feature.
- Record local results, full diff/review, exact exclusions and the actual remote CI status here. No automatic stage, commit, push, PR, workflow rerun/dispatch, deploy or history modification.

## Out of Scope

- Modifying app/, frontend, production Compose/bootstrap, package dependencies, GitHub workflow behavior or existing historical task/plan/spec files.
- Bypassing assertion coverage, dropping negative cases, marking failures skipped/xfail, leaking credential/environment values, reading `.env` or legacy shared tasks under docs/plans/.
- Unknown file edits/moves/deletions, Docker volume reset/removal, production/dev DB writes, system configuration changes or automatic cleanup of other worktrees/images.
- Claiming the published CI is green based on local results or the old frontend/adoption task. Publication still needs new user authorization.

## Acceptance Criteria

- [x] AC-1 — Failed remote run/HEAD and test fixture root cause are recorded with a reproducible RED result; distinguish test setup failure from actual bootstrap security behavior.
- [x] AC-2 — Each of six missing and six empty credential cases starts with the other five deterministic non-empty dummy values, independent of ambient host credentials; real Compose still fails nonzero and names the selected invalid variable.
- [x] AC-3 — Complete baseline succeeds; missing/blank coverage and strict expected-variable assertions remain intact. Focused regression catches reintroducing the all-missing baseline or using ambient credential values. Production Compose/runtime contracts remain unchanged.
- [x] AC-4 — Native RED/GREEN and main independent focused/repeated Compose verification, full backend/PostgreSQL suite and Ruff pass with actual counts; relevant Linux/CI-equivalent checks are recorded, unavailable checks explicitly NOT VERIFIED.
- [x] AC-5 — Main independently reviews the entire scoped diff and fixes required findings within at most three rounds; no unrelated file, security bypass or dependency change is introduced.
- [ ] AC-6 — Actual new GitHub Quality result for the patched commit is confirmed after separately approved publication. Until then this criterion is NOT VERIFIED, remote CI remains the baseline failure, and the task must not be marked DONE.
- [x] AC-7 — Report exact changed files, local verification and pending remote evidence. Preserve baseline HEAD/index, personal files and existing services/data; no stage/commit/push without additional explicit authorization.

## Embedded Implementation Plan

Single executable milestone `fix-compose-seed-ci`; no separate workstream task identifiers or progress ledger.

1. Verify exact baseline/worktree and dependency DONE/APPROVED; read stable contract and CI evidence. Record READY -> IN_PROGRESS and freeze Goal, Context, In Scope, Out of Scope, Acceptance Criteria and Verification Commands.
2. Native reproduces the negative test's current multi-missing ambiguity and adds a focused fixture-isolation regression before implementation. Verify RED is an assertion failure caused by the incorrect baseline, not a missing dependency or unavailable Docker.
3. Native makes the smallest test-only isolation correction. Retain all twelve real negative cases and strict checks, and run GREEN plus complete-baseline and hostile-ambient-environment regressions. Do not change real Compose/seed code.
4. Main reviews the diff and runs fresh focused/repeated checks, full backend against the guarded disposable PostgreSQL target and Ruff. Run Linux/Python 3.12 Compose checks from a tracked-only verification context if available. Record actual tooling/version/count evidence, not assumed CI equivalence.
5. Enter VERIFYING once implementation is frozen. Resolve genuine failures with the canonical backward transition before edits; reuse only the same native agent, maximum three review rounds. Preserve unknown files and do not stage/commit/push.
6. When local repair/review gates pass, present diff and evidence for publication approval. AC-6 remains unchecked and task VERIFYING until a patched commit's real Quality workflow is green. Do not rerun the old failing commit and claim it tests an unpublished patch.
7. After any future authorized publication, verify actual workflow, then independent REVIEWING -> DONE only when all mandatory evidence exists. Record all history only in this file.

## Verification Commands

- Git preflight/final: `git status --short`; `git diff`; `git diff --staged`; `git rev-parse HEAD`; exact changed-file allowlist; `git diff --check`. No Git mutations in current approval scope.
- Read-only remote evidence: `gh run view 38872221924 --repo tonazario08/smart-warehouse --json jobs,conclusion,url`; redact/filter failure logs so credential values are not printed. Future run IDs must be associated with a separately approved patched commit.
- Focused: existing verified Python virtualenv, `python -m pytest -q tests/test_seed.py --tb=line --show-capture=no -p no:cacheprovider`; focused RED/GREEN/regression selectors recorded before use. Repeat real Compose negative/full-baseline cases across fresh processes at least three times, not merely mock the CLI.
- Full backend: verify `sw-phase1-backend-checkpoint-20261015-test`, database `sw_phase1_checkpoint_test`, loopback 55439 before setting TEST_DATABASE_URL without printing its value; `python -m pytest -q --tb=line --show-capture=no -p no:cacheprovider`; `python -m ruff check app tests alembic`.
- Linux: disposable diagnostic image/context from tracked baseline only with Python 3.12 and real Docker Compose CLI, no daemon socket required for config validation. Compare baseline test behavior versus patched test-file bind/snapshot; run focused tests repeatedly and full backend against the same verified disposable DB sequentially, never concurrently with another destructive PostgreSQL suite. Record exact commands/image/tool versions/results in Progress Log before assertions.
- Frontend is not modified. If smoke build is used, run from an existing clean source-equivalent checkout rather than ingest unknown LegacyProductsPage; explicitly distinguish that evidence from a dirty-target build. No frontend redesign/browser writes required for this test-only patch.

## Progress Log

### 2026-10-16 — Unique task creation authorized

- Human approved the exact proposed path and CI-only/native-implementation scope. Created only this new file. Existing tracked source, index/HEAD, remote and unknown files remain unchanged at preflight.
- Single-milestone inline plan is proportionate to the bounded test-only correction; this selected file is the sole new authority/state/evidence ledger. No unrelated feature approval is inferred.

### 2026-10-16 — READY -> IN_PROGRESS

- Read AGENTS.md, selected task/embedded plan, declared dependency DONE/APPROVED evidence and stable operations/Compose required-credential contract. The explicit user approval covers the small CI-only repair; no new feature/design decision is missing. Freeze Goal, Context, In Scope, Out of Scope, Acceptance Criteria and Verification Commands now.
- Git baseline is still published `98e2cbd` on `feat/figma-ui-v2`; index has no staged changes and no existing tracked edit. Docker's explicitly owned disposable checkpoint DB and isolated production stack are running. Unknown untracked files remain outside scope; do not read their content.
- Ruling: use the existing approved feature checkout for the one-file test-only patch; no main/master implementation or additional worktree is needed. Only the native implementer edits tests/test_seed.py, while main manages this ledger and independent review. Cost if wrong: any source drift requires a safe stop rather than overwriting other changes.
- Ruling: user/repository single-native-agent and sole-task-ledger rules override skill defaults for extra agents/ledgers/automatic commits or cleanup. Use exactly the existing native implementer and main independent review; no parallel PostgreSQL writers. Cost if wrong: fewer review seats, compensated by direct cross-platform fixture/security verification.

| Internal boundaries checked | Shared interface | Preflight result |
| --- | --- | --- |
| Fixture setup / real Compose negative cases | Returned subprocess environment | All other required credentials must be set before removing exactly one target; keep strict error assertion. |
| RED regression / minimal correction | Test helper and test-only baseline values | Add focused fixture-isolation coverage, not a test of Docker's internal map ordering or permissive error output. |
| Windows / Linux verification | Tracked source, tool versions and disposable DB | No source secrets/unknown mounts; full DB suites sequentially to prevent truncate races. |
| Local repair / remote CI confirmation | Uncommitted patch versus published HEAD | AC-6 deliberately remains unverified until separately authorized publication and actual patched workflow. |

### 2026-10-16 — Root cause reproduced on Linux; local implementation complete

- Main independently built ignored diagnostic image `sw-ci-seed-verification:20261016` from a git archive of tracked baseline `98e2cbd`, Python 3.12-slim plus the real Docker/Compose binaries from docker:28-cli. Actual tools: Linux, Python 3.12.15, Compose v2.40.3. Windows Compose is v5.5.0. No project `.env`, unknown source or daemon socket was mounted. The diagnostic image's inherited production dockerignore intentionally excludes tests/client, so verification mounts only the tracked archive's tests/client directories read-only; patched verification additionally mounts only the approved tests/test_seed.py read-only.
- Main baseline Linux reproduction (unpatched tracked test file): `python -m pytest -q tests/test_seed.py -k compose_config --tb=no -p no:cacheprovider` returned exit 1, **10 failed / 3 passed / 31 deselected**, one dependency warning. GitHub's same failure family had 11 failed, not asserted as a fixed failure count: which variable Compose reports varies when all are absent. This reproduces the defect with actual CLI rather than weakening its diagnostics.
- Native RED regression for complete/ambient-independent helper baseline: three assertion failures before the fix. A deliberate `setdefault` mutation was also caught (two failed / one passed), proving empty/ambient host values must not be inherited. Native final minimal correction sets all six test-only dummy values by assignment; full-baseline test uses the helper directly. Twelve missing/empty negative cases and both strict exit/name assertions remain unchanged.
- Native focused seed suite: 47 passed; three separate real Compose processes: each 16 passed / 31 deselected, no skipped cases; Ruff and diff checks pass. These are native evidence, not yet main full-suite or remote confirmation. Only tests/test_seed.py changed (23 additions / two deletions); no workflow/production/runtime/frontend/dependency edit.

### 2026-10-16 — IN_PROGRESS -> VERIFYING

- Native implementation is frozen. Main reviewed the exact patch and its hostile-ambient regression against the stable all-six-credential contract; no preliminary required finding. Main now runs independent Windows and Linux checks, with PostgreSQL suites sequentially. Baseline HEAD/index and excluded personal files remain untouched. No stage/commit/push is authorized.

### 2026-10-16 — Independent Windows and repeated Linux gates

- Main's fresh Windows full backend run used the existing verified Python virtualenv and guarded checkpoint PostgreSQL container/database on loopback 55439: `python -m pytest -q --tb=line --show-capture=no -p no:cacheprovider` returned **462 passed, two dependency deprecation warnings**, exit 0. Subsequent `python -m ruff check app tests alembic` returned **All checks passed**. This includes actual PostgreSQL integration tests; no test was skipped.
- Main independently ran three fresh Linux Compose processes with the tracked-only baseline tests/client read-only mounts plus the single patched test-file mount: `python -m pytest -q tests/test_seed.py -k compose --tb=line --show-capture=no -p no:cacheprovider`. All three returned **16 passed / 31 deselected / one dependency warning**, exit 0, zero skipped. These exercise all twelve strict missing/empty cases, the three ambient-baseline regressions and complete-baseline success with real Compose v2.40.3.
- After the Windows process exited, main started the full Linux suite with the same tracked-only mounts, `--network container:sw-phase1-backend-checkpoint-20261015-test` and internally forwarded TEST_DATABASE_URL naming only `sw_phase1_checkpoint_test` at namespace loopback 5432. The container identity, DB name and published loopback 55439 were checked before use. Command: `python -m pytest -q --tb=line --show-capture=no -p no:cacheprovider`; then `python -m ruff check app tests alembic`. Results are pending at this entry; do not infer success from the focused run.
- Main reviewed the entire 23-addition/two-deletion test diff: the only helper change overwrites all six test-only baseline values; negative tests still remove/blank exactly one and require both nonzero exit and its name; positive coverage now directly exercises the helper baseline. No production security assertion, workflow or dependency changed. No required local review finding so far.
- Fresh read-only GitHub query still reports Quality 38872221924 failure at published `98e2cbd` (backend failed, frontend succeeded, E2E skipped). No patched commit/run exists. HEAD/index and the excluded LegacyProductsPage hash remain unchanged; task-specific generated contexts remain ignored, not staged.

## Verification Evidence

- Main Windows full backend/PostgreSQL: 462 passed, two dependency warnings, exit 0; Ruff passed.
- Main Linux/Python 3.12.15 full backend/PostgreSQL: 462 passed, one dependency warning, exit 0 in 117.14 seconds; Ruff passed. Same approved test-only patch over tracked baseline; no developer secrets/unknown source mounted. This confirms Linux behavior, not the exact future hosted runner/package snapshot.
- Main Linux Compose v2.40.3: unpatched RED 10 failed / three passed / 31 deselected; three patched GREEN processes each 16 passed / 31 deselected, no skips. Native Windows Compose v5.5.0: focused 47 passed and three separate Compose processes each 16 passed / 31 deselected; native regression RED and setdefault mutation failure recorded above.
- `git diff --check`: passed. Only tracked implementation change is tests/test_seed.py, 23 additions/two deletions. This new task file is the only new in-scope file; no staging was performed.
- Remote baseline failure observed: Quality [38872221924](https://github.com/tonazario08/smart-warehouse/actions/runs/38872221924) at `98e2cbdd48af69fe2d41f2b8da0c1a5a675ee3d4`, backend 448 passed/11 failed; frontend success; E2E skipped. Patched GitHub backend/frontend/E2E result: **NOT VERIFIED**. Frontend was not modified or locally rebuilt for this test-only patch; the baseline frontend job is not evidence for a new patched remote run. Browser/Figma verification is outside this CI-only task.

## Review Result

- Local patch review: **PASS**, main independent spec/quality review, round 1 of maximum 3; no required findings or further implementation correction. Reviewed the entire test diff and this task ledger against the approved bounded CI repair.
- The root cause is fixture setup, not relaxed bootstrap security. All twelve strict real-Compose negative cases remain; the exact six-value baseline regression rejects absent, empty and ambient credentials. The unchanged production Compose, seed/auth/API/RBAC/frontend/workflow/dependencies retain their existing contracts.
- Final task approval: **PENDING**, because AC-6 is NOT VERIFIED. No REVIEWING/DONE transition is claimed while the mandatory new remote Quality evidence is missing.

## Completion Evidence

- Not completed; status remains **VERIFYING**. AC-1 through AC-5 and AC-7 have local evidence above. AC-6 requires a real patched GitHub Quality run, including its backend/frontend/E2E outcomes.
- Exact in-scope handoff: modified tests/test_seed.py and new docs/tasks/fix-compose-seed-ci.md. HEAD remains `98e2cbd`, index empty. Personal/unrelated untracked files remain excluded and untouched. Existing checkpoint DB and isolated application services remain running; no volumes/data were reset or removed. Only task-owned ephemeral diagnostic containers used `--rm`; ignored archive/context/image remain available.
- Required human decision: authorize a logical local commit and push of only these two reviewed files to existing `origin/feat/figma-ui-v2`, then read/monitor the resulting new Quality run. No merge to main, PR, deployment or history rewrite is proposed. Without that new publication authority, stop here and do not stage/commit/push.

## Progress Log Continuation

### 2026-10-16 — Local verification/review complete; publication gate pending

- The sequential full Linux PostgreSQL suite completed: **462 passed / one dependency warning**, exit 0; Linux Ruff passed. Windows full suite already passed with the same test count and two dependency warnings. Dependency warnings are deprecations, not failures; no dependency upgrade is included in this task.
- Main independent review completed in the first round with no required finding. Verified preserved strict missing/empty checks, deterministic/host-independent baseline, positive baseline coverage, exact production-change exclusions and task evidence. No second implementation round needed.
- Checked AC-1 through AC-5 and AC-7 using actual local evidence. AC-6 deliberately remains unchecked; baseline remote run is still failed and no patched run was dispatched. Keep VERIFYING rather than claiming DONE/APPROVED for the entire task. Present the one-file implementation diff, task ledger and actual results to the human before any Git mutation.

### 2026-10-16 — Publication authorization amendment

- Approver: human user, replying `duyet` to the explicit proposal to commit only tests/test_seed.py and this task, push to existing origin/feat/figma-ui-v2, and verify the resulting new GitHub Quality run. Reason: AC-6 cannot be verified from an unpublished patch. This narrow amendment supersedes the initial no-stage/commit/push restriction for those exact files and that branch only; no application/scope/AC relaxation, merge, PR, deployment, workflow rerun of old source or history rewrite is authorized.
- Main rechecked baseline HEAD/remote branch at `98e2cbd`, clean index, unchanged one-file implementation diff and dependency DONE. Run fresh full Linux backend/PostgreSQL and Ruff verification before staging, then inspect the exact staged allowlist/content. The finishing-a-development-branch integration choice has already been made by the user: push the existing branch only, without its default PR/cleanup steps.
- Following actual patched CI success, main may record the prescribed VERIFYING -> REVIEWING -> DONE evidence in this same ledger. Publishing a later documentation-only completion checkpoint will require separate approval if outside the two-file checkpoint approved here; do not silently create a publication loop.

### 2026-10-16 — Fresh pre-publication verification

- Main reran the complete Linux/Python 3.12 suite against the guarded disposable PostgreSQL DB with the reviewed one-file patch: **462 passed / one dependency warning**, exit 0 in 98.21 seconds. Subsequent Ruff returned **All checks passed**. Production/app/frontend files remain unchanged; frontend build/tests will be freshly checked by the new Quality workflow, not inferred from the old run.
- Pre-stage review inspected git status, full unstaged implementation diff, empty staged diff, exact branch/remote and remote feature HEAD. Only tests/test_seed.py and this task are authorized for staging/publication. Missing/blank assertions and all twelve real-Compose cases remain unchanged. No real credential or secret value is added; all credential-like strings in the implementation diff are explicit test-only dummy values.
