# Implementation Rules

## Before Coding

Before any project modification, receive one explicit, existing, non-template task path under `docs/tasks/`. Missing, ambiguous, multiple, out-of-tree, or nonexistent paths block coding. Read only the selected task, explicit dependency paths, and stable plan/spec/rules they reference; never infer the active task by scanning files or status.

Use status-aware routing: `READY` validates prerequisites then starts; `IN_PROGRESS` resumes implementation; `VERIFYING` resumes verification only; `REVIEWING` resumes review only; `DONE` is reported rather than rerun without a separate explicit request. The only forward sequence is `READY -> IN_PROGRESS -> VERIFYING -> REVIEWING -> DONE`; verification or review failures return to `IN_PROGRESS`.

Before `READY -> IN_PROGRESS`, validate every explicit dependency is `DONE`, validate plan/spec authority and task identifier/scope consistency, and read `Goal`, `Context`, `In Scope`, `Out of Scope`, `Acceptance Criteria`, and `Verification Commands`. Freeze these baseline sections at `IN_PROGRESS`. Any change requires explicit approval and an append-only scope amendment in `Progress Log` before baseline content changes.

## During Implementation

- Change only the selected task's scope; record task history and evidence only in its task file.
- Make the smallest change that completes the requirement.
- Do not modify unrelated code, bulk rename, or format the repository.
- Preserve backward compatibility unless the approved plan explicitly requires a breaking change.
- Model A and strict single-task execution apply: one milestone is one executable task and only one task is actively implemented.

## TDD

If a task requires new behavior:

1. RED — create or identify a failing test.
2. GREEN — make the minimal implementation.
3. REFACTOR — only while tests still pass.

Do not weaken assertions to reach GREEN.

## Completion and verification handoff

Run focused checks, relevant regression, static/diff checks, inspect the diff, and compare all acceptance criteria. Record actual commands and observed results in `Verification Evidence`. Only after all in-scope implementation is complete, every mandatory item is addressed, and the diff is ready, append the `IN_PROGRESS -> VERIFYING` transition. A failed mandatory verification records evidence and transitions `VERIFYING -> IN_PROGRESS` before implementation resumes.
