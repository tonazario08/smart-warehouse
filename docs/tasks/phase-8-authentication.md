# phase-8-authentication — Authentication

## Metadata

- Status: DONE
- Phase: 8
- Plan: User-approved Smart Warehouse frontend implementation phases in this conversation
- Depends on: docs/tasks/phase-7-inbound-outbound.md
- Created: 2026-10-07
- Started: 2026-10-07
- Completed: 2026-10-08

## Goal

Implement the approved Vietnamese login, forgot-password, reset-password, and authentication-error presentations while preserving the existing real authentication contracts, token lifecycle, route separation, and backend authority.

## Context

The approved visual source is Figma file `IoHM7Md1WkS8nt1kH4jrO4`, nodes `40:2` (Login), `40:39` (Forgot Password), `40:67` (Reset Password), and `40:103` (Error State). Phase 7 is a required completed dependency.

## In Scope

- The existing authentication routes' visual presentation, input validation and Vietnamese feedback states, using the current AuthProvider, API client, route guards, and shared Phase 1 UI primitives.
- Real login and token invalidation behavior already provided by `/auth/login`, `/auth/me`, and the `smart-warehouse-token` local-storage key.

## Out of Scope

- Backend auth endpoints, password-reset behavior not supported by an existing API, token storage semantics, RBAC authority, App Shell, application-page work, mock auth data, a UI framework, and package-manager changes.

## Acceptance Criteria

- [x] AC-1 — `/login`, `/forgot-password`, and `/reset-password` use their approved Figma structures outside AppShell.
- [x] AC-2 — Login preserves the existing real `/auth/login` flow, `smart-warehouse-token` behavior, auth hydration, and protected-route redirect semantics.
- [x] AC-3 — Password recovery and reset UI only call existing supported contracts; unsupported backend capability is explicit and never simulated.
- [x] AC-4 — All visible interface and feedback text is Vietnamese and shared primitives/styles are reused.
- [x] AC-5 — build, TypeScript, diff, relevant auth regressions, and available browser verification pass.

## Verification Commands

### Focused

- `npm.cmd run build`
- `npx.cmd tsc --noEmit`

### Regression

- Verify real login, authenticated redirect, token persistence, `/auth/me` hydration, invalid-token cleanup, and logout against the current backend.

### Static and Diff

- `git diff --check`

## Progress Log

### 2026-10-07 — Created

- Created after `docs/tasks/phase-7-inbound-outbound.md` reached DONE.
- Dependency is complete. Awaiting Figma/context inspection and user approval of the bounded Phase 8 design before the required `READY -> IN_PROGRESS` transition.

### 2026-10-07 — READY -> IN_PROGRESS

- The user approved the bounded Phase 8 design. Figma contexts and screenshots for nodes `40:2`, `40:39`, `40:67`, and `40:103` were inspected. The existing local warehouse SVG exactly matches the approved brand mark and will be reused; no temporary Figma asset URL will enter the codebase.

### 2026-10-08 — IN_PROGRESS -> VERIFYING

- Replaced public-route placeholders and the legacy login presentation with the shared Figma-aligned auth layout, real login error state, and explicit unsupported recovery/reset feedback. Existing login, token, hydration, logout, and route guard behavior remain delegated to AuthProvider and the current backend contracts.

### 2026-10-08 — VERIFYING -> REVIEWING

- Focused frontend tests, production build, TypeScript, diff validation, auth regression tests, complete backend suite, and isolated browser verification were run. Figma screenshots were used as the visual target.

### 2026-10-08 — REVIEWING -> DONE

- Review passed. The implementation is limited to public authentication UI, a pure Vietnamese auth-error formatter, route entries, scoped styles, and tests. No backend endpoint, API contract, token-storage key, RBAC authority, App Shell, or application-page behavior changed.

### 2026-10-09 — Post-completion audit reconciliation

- `Started` is set from the existing dated `READY -> IN_PROGRESS` entry; no date was inferred.
- AC-1 is verified by recorded Figma context/screenshot inspection and browser rendering of Login, Forgot Password, Reset Password, and the error state outside AppShell.
- AC-2 is verified by real invalid and successful login runs, `/auth/me` refresh hydration, protected redirects, logout, and auth backend tests.
- AC-3 is verified by browser/source evidence that recovery and reset produce explicit unsupported-server feedback without sending simulated requests.
- AC-4 is verified by the recorded browser review and source reuse of shared Button, FeedbackMessage, Input, and auth styles with Vietnamese copy.
- AC-5 is verified by the recorded focused auth test, browser run, auth backend regressions, TypeScript/build/diff checks, the later migration repair, and the clean `c0727c4` audit test/build run.
- The checklist and review-result enum were reconciled to existing evidence; no new browser or Figma review is claimed.

## Verification Evidence

- Focused auth-error test: first failed because the formatter did not exist, then passed with 2 tests covering 401 and unexpected failures.
- `npm.cmd run build`, `npx.cmd tsc --noEmit`, and `git diff --check`: passed after the final visual adjustments.
- `.venv\\Scripts\\python.exe -m pytest tests\\test_auth.py -q`: 8 passed with existing Starlette, asyncio, and pytest-cache warnings.
- Isolated browser verification: Login, Forgot Password, Reset Password, and the approved login-error state rendered outside AppShell. A real invalid login returned the Vietnamese 401 state. A real seeded-admin login redirected to `/dashboard`; reloading the protected route restored the session through `/auth/me`; logout returned to `/login`; and unauthenticated `/dashboard` redirected to `/login`.
- Password recovery and reset submissions explicitly state that the current server has no supported endpoint; no request is simulated or sent. The isolated FastAPI and Vite processes were stopped.
- Complete backend suite: 52 passed and 2 failed. `tests/test_migration.py::test_initial_revision_upgrades_an_empty_database` and `tests/test_seed.py::test_seed_is_idempotent_and_preserves_existing_user_credentials` retain their pre-existing Alembic configuration failure caused by `alembic/env.py` replacing the test-configured database URL. Phase 8 did not modify backend or migration files.

## Review Result

- Result: APPROVED
- Findings: none; the existing review retained only the documented unsupported recovery/reset backend capability.

Figma capability deviation retained intentionally:

- Figma supplies complete recovery and reset forms, while the current backend only exposes login, registration, and `/auth/me`. The matching forms are presented, validate locally, and state this limitation explicitly rather than pretending to email a link or change a password.

## Completion Evidence

- AC-1 through AC-5 satisfied with the verification evidence above.
