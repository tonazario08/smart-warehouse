# phase-2-app-shell-routing — App Shell, Routing, and Route Guards

## Metadata

- Status: DONE
- Phase: 2
- Plan: User-approved Phase 2 implementation brief in this conversation, 2026-10-06
- Depends on: docs/tasks/phase-1-ui-foundation.md
- Created: 2026-10-06
- Started: 2026-10-06
- Completed: 2026-10-07

## Goal

Implement the Figma-approved desktop application shell, React routes, authentication hydration, and route guards while preserving all backend contracts and existing login behavior.

## Context

The approved Figma source is file `IoHM7Md1WkS8nt1kH4jrO4`, node `5:3`. The existing application is a single component without routes or shared authentication state. Phase 1 is complete and provides the CSS token and permission helper foundation.

## In Scope

- React Router integration, auth hydration, logout, route guards, App Shell, Sidebar, Topbar, Breadcrumbs, UserMenu, Vietnamese route placeholders, and role-aware navigation.
- Routes explicitly specified by the approved brief.
- Local Figma icon assets required by the App Shell.

## Out of Scope

- Dashboard, Products, Inventory, Warehouses, Inbound, Outbound, or authentication page redesign.
- Backend changes, API contract changes, mock data, settings, support, and unsupported transaction pages.

## Acceptance Criteria

- [x] AC-1 — App Shell follows the approved desktop Figma node's sidebar, topbar, typography, palette, dimensions, and local icon assets.
- [x] AC-2 — All approved URLs resolve with protected-route redirection and isolated auth routes.
- [x] AC-3 — Existing login, `/auth/me` hydration, invalid-token cleanup, and logout behavior remain intact.
- [x] AC-4 — Navigation visibility follows the role matrix while backend authorization remains authoritative.
- [x] AC-5 — Build, TypeScript, diff verification, protected-route refresh hydration, logout, and role navigation checks pass.

## Verification Commands

### Focused

- `npm.cmd run build`
- `npx.cmd tsc --noEmit`

### Regression

- Verify login, `/auth/me` refresh hydration, protected redirect, and logout in the running application.

### Static and Diff

- `git diff --check`

## Progress Log

### 2026-10-06 — READY -> IN_PROGRESS

- Dependency `docs/tasks/phase-1-ui-foundation.md` is DONE by user-approved review.
- Figma App Shell node `5:3`, current frontend code, Phase 1 shared foundation, and role handling were inspected.
- Goal, context, scope, acceptance criteria, and verification commands are frozen.

### 2026-10-06 — IN_PROGRESS -> VERIFYING

- Added React Router, auth hydration provider, route guards, protected routes, App Shell, role-aware navigation, and temporary Vietnamese placeholders.
- Preserved `POST /auth/login`, `GET /auth/me`, `smart-warehouse-token`, logout cleanup, and backend RBAC as the authorization authority.
- `npm.cmd run build`, `npx.cmd tsc --noEmit`, and `git diff --check` passed.
- Runtime verification against a live API and Figma asset fidelity remain pending.

### 2026-10-06 — VERIFYING -> REVIEWING

- Phase 2 review started at user request.

### 2026-10-06 — REVIEWING -> IN_PROGRESS

- Review found that denied dashboard permission redirected non-admin users to the same denied route.
- Review also confirmed that App Shell icons were not yet local Figma SVG assets.
- In-scope corrections started.

### 2026-10-06 — IN_PROGRESS -> VERIFYING

- Corrected the denied-route fallback to a role-supported landing route: `/products` for client and `/inventory` for warehouse roles.
- Added local SVG assets exported from Figma node `5:3` for the supported Sidebar destinations and Topbar search and notification controls; no temporary Figma asset URLs are referenced at runtime.
- Corrected Sidebar visibility so the `warehouse` role no longer sees Products; the approved navigation matrix is applied in addition to the existing visibility permission helper.
- Re-ran the required static verification. Runtime authentication verification remains pending a live backend session.

### 2026-10-06 — VERIFYING

- Ran the isolated backend authentication regression suite. It verifies the login contract, `/auth/me` identity resolution, invalid-token rejection, expired-token rejection, and backend dashboard authorization.
- A disposable API and Vite runtime could not be started in this execution environment because background process creation is blocked, so browser-level verification remains pending.

### 2026-10-06 — VERIFYING

- Started an isolated localhost API using a disposable SQLite database and a temporary Vite instance; no project database or API contract was changed.
- At the Figma desktop reference viewport, verified login and the authenticated landing routes: admin to `/dashboard`, warehouse to `/inventory`, and client to `/products`.
- Verified protected-route redirect to `/login`, hydration after a refresh of `/products`, logout returning to `/login`, and deterministic fallback from an unknown URL to the appropriate authenticated landing route.
- Verified invalid-session cleanup by making only the temporary test user unavailable, refreshing the protected route, and observing redirect to `/login` after `/auth/me` was rejected.
- Verified Sidebar destinations for admin, warehouse, and client against the approved navigation matrix. The temporary browser tab and local servers were closed after verification.

### 2026-10-06 — VERIFYING -> REVIEWING

- Independent source and Figma node `5:3` review performed after runtime verification.
- Finding P1: `AuthProvider` calls `logout()` for every failed `/auth/me` request, including transient network errors and server failures. This clears `smart-warehouse-token` even though authentication has not been proven invalid, regressing the prior behavior and violating the token-cleanup constraint.
- Finding P2: the visible Logout button inside the Sidebar user profile is not present in the approved Figma App Shell and can crowd the fixed-width profile row. Logout must remain available, but its presentation needs to preserve the approved profile geometry.

### 2026-10-06 — REVIEWING -> IN_PROGRESS

- User approved the bounded correction design: only authentication failures may clear the token, and logout moves from the fixed Sidebar profile row into a user menu.
- Regression tests will be added before the implementation change where the existing frontend test tooling permits it.

### 2026-10-07 — IN_PROGRESS -> VERIFYING

- Added a frontend regression test proving `ApiError` retains its HTTP status. The test failed before the correction and passed after it.
- `AuthProvider` now clears `smart-warehouse-token` only when `/auth/me` returns 401. Network and server failures retain the token and surface the connection error.
- Replaced the visible Sidebar logout button with an accessible, closed-by-default profile menu. The closed profile row matches the Figma App Shell geometry; Logout remains available within the menu.
- Runtime verification on an isolated API/Vite instance confirmed: a temporary API outage retains the token and restores the session when the API returns; a 401 still redirects to Login and clears the session; the UserMenu opens and logout succeeds.

### 2026-10-07 — VERIFYING -> REVIEWING

- Re-reviewed the corrected authentication flow, UserMenu closed state, route structure, and local Figma asset usage. No Phase 2 finding remains.

### 2026-10-07 — REVIEWING -> DONE

- All acceptance criteria and verification commands have passing evidence. Phase 2 is complete.

## Verification Evidence

### Focused

`npm.cmd run build`: PASS, after the review corrections.

`npx.cmd tsc --noEmit`: PASS, after the review corrections.

### Regression

`.venv\\Scripts\\python.exe -m pytest tests\\test_auth.py -q`: PASS, 8 passed. This validates the backend authentication contract used by the frontend.

Browser integration against an isolated local API and Vite application: PASS. Verified login, protected-route redirect, authenticated refresh hydration, invalid-session cleanup, logout, role-aware Sidebar visibility, root landing behavior, and unknown-route fallback at the desktop reference viewport.

`npx.cmd tsc --ignoreConfig --target ES2022 --module commonjs --moduleResolution bundler --allowJs --checkJs false --outDir <temporary-dir> src\\api.ts tests\\api-error-status.test.js` followed by `node <temporary-dir>\\tests\\api-error-status.test.js`: PASS. The test was red before `ApiError` retained the HTTP status and green afterward.

Correction browser verification: PASS. A network failure retained the token and displayed the connection error; after restarting the isolated API, a page refresh restored the authenticated Dashboard. A 401 from an unavailable temporary user redirected to Login. The profile menu remained closed by default and Logout succeeded from its accessible menu item.

### Static and Diff

`git diff --check`: PASS, after the correction verification.

## Review Result

- Result: PASS.
- Findings: the dashboard fallback loop, missing local Figma icon assets, unconditional token cleanup on `/auth/me` failure, and Sidebar user-profile visual deviation were corrected and re-reviewed.

## Completion Evidence

Phase 2 completed on 2026-10-07. No backend endpoint or API contract changed. The only behavior refinement is that non-authentication `/auth/me` failures retain the existing token; verified 401 failures continue to clear it. The closed Sidebar profile row now matches Figma, while Logout is available from its menu.
