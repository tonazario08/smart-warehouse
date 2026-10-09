# phase-1-ui-foundation — Shared UI Foundation

## Metadata

- Status: DONE
- Phase: 1
- Plan: User-approved Phase 1 implementation brief in this conversation, 2026-10-06
- Depends on: none
- Created: 2026-10-06
- Started: 2026-10-06
- Completed: 2026-10-06

## Goal

Establish the approved Figma design tokens, global base styles, reusable presentational UI primitives, formatters, and frontend permission helpers without changing the current application flow.

## Context

The current React, TypeScript, and Vite frontend uses a single global stylesheet and has no shared UI foundation. The approved Figma system defines Inter typography, a light content surface, a dark sidebar palette, and the specified semantic colors. This task is limited to foundational code that later phases can consume.

## In Scope

- Create the shared styles, UI primitives, formatters, and permission helpers listed in the approved brief.
- Update `client/src/styles.css` only to load the shared token and base styles.
- Preserve the existing React, TypeScript, Vite, CSS, API, login, product, and token-storage behavior.
- Use Vietnamese for all visible default UI text and English for code identifiers.

## Out of Scope

- Routing, page layouts, App Shell, and any redesign of `client/src/App.tsx`.
- Authentication-flow refactoring or any change to `smart-warehouse-token` behavior.
- Backend code, FastAPI contracts, `client/src/api.ts`, or dependencies.
- Product, inventory, warehouse, inbound, outbound, dashboard, and authentication screen implementation.

## Acceptance Criteria

- [x] AC-1 — Shared CSS tokens preserve every Figma color and Inter typography specified in the approved brief.
- [x] AC-2 — Global base styles load from `client/src/styles.css` and provide accessible, neutral HTML defaults without changing application behavior.
- [x] AC-3 — Button, Input, Select, Badge, DataTable, PageHeader, EmptyState, FeedbackMessage, and ConfirmDialog are reusable, typed, presentational components with Vietnamese default visible text where applicable.
- [x] AC-4 — Shared formatters safely render Vietnamese number, date, and quantity values without page-specific business logic.
- [x] AC-5 — Permission helpers map the existing `admin`, `warehouse`, and `client` roles to frontend visibility permissions without becoming an authorization boundary.
- [x] AC-6 — `npm.cmd run build` and `npx tsc --noEmit` pass with no errors introduced by this task.

## Verification Commands

### Focused

- `npm.cmd run build`
- `npx tsc --noEmit`

### Regression

- `npm.cmd run build`

### Static and Diff

- `git diff --check`
- `git diff -- client/src/styles.css client/src/shared docs/tasks/phase-1-ui-foundation.md`

## Progress Log

### 2026-10-06 — READY -> IN_PROGRESS

- Dependencies: none.
- User-approved implementation brief verified in the active conversation.
- Goal, context, in-scope items, out-of-scope items, acceptance criteria, and verification commands are frozen.
- Existing `client/src/styles.css`, `Heading`, `ProductTable`, and `ProductManager` were inspected before implementation.
- Implementation started without modifying `App.tsx`, `api.ts`, backend code, routes, dependencies, or authentication behavior.

### 2026-10-06 — IN_PROGRESS -> VERIFYING

- Added the thirteen approved shared files and loaded shared token and base CSS from `client/src/styles.css`.
- `App.tsx`, `api.ts`, `types.ts`, backend code, routes, package files, and `smart-warehouse-token` behavior remain unchanged.
- `npm.cmd run build` passed.
- `npx tsc --noEmit` passed.
- Implementation is ready for static diff verification and independent review.

### 2026-10-06 — VERIFYING -> REVIEWING

- User confirmed that Phase 1 passed verification.

### 2026-10-06 — REVIEWING -> DONE

- User approved Phase 1 completion and authorized Phase 2 to begin.

## Verification Evidence

### Focused

Command: `npm.cmd run build`

Result: PASS. TypeScript project build and Vite production build completed with exit code 0.

Command: `npx tsc --noEmit`

Result: PASS. TypeScript completed with exit code 0.

### Regression

Command: `npm.cmd run build`

Result: PASS. The production build completed with exit code 0.

### Static and Diff

Command: `git diff --check`

Result: PASS. Exit code 0.

Command: verify the thirteen approved shared files and all required Figma color literals in `tokens.css`.

Result: PASS. All thirteen files exist and every required token is present.

Scoped status: `client/src/styles.css` modified; `client/src/shared/` and this task file are untracked. No other Phase 1 source files are modified.

## Review Result

- Result: APPROVED
- Findings: none reported by the approving reviewer

## Completion Evidence

- Final status: DONE
- Acceptance criteria: all satisfied
- Focused verification: PASS
- Regression verification: PASS
- Static and diff verification: PASS
- Review: APPROVED by user confirmation
- Commit: not requested
- Completed: 2026-10-06
