# migration-seed-regression — Migration and Seed Regression

## Metadata

- Status: DONE
- Phase: Post-implementation regression repair
- Plan: User-approved follow-up after frontend Phases 1 through 8
- Depends on: docs/tasks/phase-8-authentication.md
- Created: 2026-10-09
- Started: 2026-10-09
- Completed: 2026-10-09

## Goal

Review and repair the two existing backend test failures so Alembic upgrades the database URL configured by its caller and the idempotent seed test can run against that upgraded database.

## Context

`tests/test_migration.py::test_initial_revision_upgrades_an_empty_database` and `tests/test_seed.py::test_seed_is_idempotent_and_preserves_existing_user_credentials` have failed consistently. Earlier Phase 6 through 8 verification identified a likely interaction in `alembic/env.py` where application settings override the Alembic config URL supplied by each test.

## In Scope

- Root-cause review, focused tests, and the smallest backend configuration correction necessary for these two tests.
- Preserving environment-based runtime database configuration and the existing migration and seed contracts.

## Out of Scope

- Frontend behavior, API contract changes, migration schema redesign, destructive database operations, production configuration changes, package changes, unrelated test cleanup, commits, pushes, and pull requests.

## Acceptance Criteria

- [x] AC-1 — An Alembic `Config` URL explicitly supplied by a caller is used for that migration run.
- [x] AC-2 — The initial migration creates the expected schema in a caller-provided empty SQLite database.
- [x] AC-3 — Seed idempotency runs against that migrated database and preserves an existing user password hash.
- [x] AC-4 — The full backend suite passes without introducing frontend or API regressions.

## Verification Commands

### Focused

- `.venv\\Scripts\\python.exe -m pytest tests\\test_migration.py tests\\test_seed.py -q`

### Regression

- `.venv\\Scripts\\python.exe -m pytest -q`
- `npm.cmd run build`

### Static and Diff

- `git diff --check`

## Progress Log

### 2026-10-09 — Created

- Created at the user's request after Phase 8 reached DONE. Dependency is complete. Awaiting root-cause review and baseline confirmation before `READY -> IN_PROGRESS`.

### 2026-10-09 — READY -> IN_PROGRESS

- Root cause confirmed by reproducing both focused failures. `alembic/env.py` replaces a non-empty `sqlalchemy.url` supplied through an Alembic `Config` with `get_settings().database_url`; therefore the migration succeeds against a different database and the caller-provided SQLite database remains empty. Baseline frozen: preserve caller-supplied URLs and only fall back to application settings when Alembic has no URL.

### 2026-10-09 — IN_PROGRESS -> VERIFYING

- Applied the smallest configuration correction in `alembic/env.py`: a caller-supplied non-empty URL is preserved, while the existing application-settings URL remains the fallback for normal migration execution.

### 2026-10-09 — VERIFYING -> REVIEWING

- Focused migration/seed tests and the complete backend suite passed. Frontend production build, TypeScript, and diff validation also passed.

### 2026-10-09 — REVIEWING -> DONE

- Review passed. The change is restricted to Alembic configuration precedence and does not alter migration schema content, seed behavior, API contracts, frontend behavior, or runtime settings validation.

### 2026-10-09 — Post-completion audit reconciliation

- `Started` is set from the existing dated `READY -> IN_PROGRESS` entry; no date was inferred.
- AC-1 through AC-3 are verified by the recorded focused migration/seed run and the fresh clean-worktree full suite that includes both tests.
- AC-4 is verified by the fresh clean-worktree result of 54 backend tests passing and a successful frontend production build.
- The checklist and review-result enum were reconciled to existing evidence; no new review is claimed.

## Verification Evidence

- Root-cause review: reproduced both failures and traced them to `alembic/env.py` overwriting the caller-provided `Config` URL.
- `.venv\\Scripts\\python.exe -m pytest tests\\test_migration.py tests\\test_seed.py -q`: 2 passed with existing Starlette, asyncio, and pytest-cache warnings.
- `.venv\\Scripts\\python.exe -m pytest -q`: 54 passed with the same existing warnings.
- `npm.cmd run build`, `npx.cmd tsc --noEmit`, and `git diff --check`: passed.

## Review Result

- Result: APPROVED
- Findings: none; the existing review confirmed caller URL precedence and the application-settings fallback.

## Completion Evidence

- AC-1 through AC-4 satisfied with the verification evidence above.
