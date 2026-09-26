# File-per-Task Execution Workflow

## 1. Task selection

Implementation begins only after the user or an approved calling workflow identifies exactly one repository-relative executable task path under `docs/tasks/`. Validate that the path stays under `docs/tasks/`, exists, and is not `docs/tasks/task-template.md`. Missing, ambiguous, multiple, out-of-tree, template, or nonexistent selections fail closed: request one exact path and do not modify project files.

Never scan task directories, status values, plan order, timestamps, or task numbers to infer work. Routing may read only the selected task, its explicitly declared dependency paths, and stable plans, specifications, and rules referenced by them. The legacy shared routing file under `docs/plans/` is not read, updated, or selected.

## 2. Metadata, dependencies, and plan authority

An executable task contains `Status`, `Phase`, `Plan`, `Depends on`, `Created`, `Started`, and `Completed` metadata plus the canonical task sections. `Created` is immutable; `Started` is set once on `READY -> IN_PROGRESS`; `Completed` is set only on `REVIEWING -> DONE` and must match completion evidence.

Dependencies are `none` or explicit repository-relative task paths. Read only those declared paths and require every one to be `DONE` before `READY -> IN_PROGRESS`. Validate that the approved plan exists, contains the task identifier, and has scope consistent with the task. Read stable specifications only when selected by the task or approved plan. A repository-process task may use an approved specification as plan authority only when that specification explicitly identifies it as repository-process work.

## 3. Start and resume routing

- `READY`: validate dependencies, plan/spec authority, task structure, scope, and baseline; then record `READY -> IN_PROGRESS`.
- `IN_PROGRESS`: resume only selected-task implementation; preserve metadata and append-only history.
- `VERIFYING`: resume declared verification only. Any implementation correction first records `VERIFYING -> IN_PROGRESS`.
- `REVIEWING`: resume independent review only. Required changes first record `REVIEWING -> IN_PROGRESS`.
- `DONE`: report existing evidence; do not rerun without a separate explicit request defining new work.

The official forward state machine is `READY -> IN_PROGRESS -> VERIFYING -> REVIEWING -> DONE`. The only backward transitions are `VERIFYING -> IN_PROGRESS` and `REVIEWING -> IN_PROGRESS`. Skipping gates is prohibited. Insufficient evidence is `NOT VERIFIED`, never `DONE`.

## 4. Frozen baseline and progress history

At `IN_PROGRESS`, freeze `Goal`, `Context`, `In Scope`, `Out of Scope`, `Acceptance Criteria`, and `Verification Commands`. Do not silently rewrite them to match implementation. A change needs explicit user approval followed by an append-only scope amendment in `Progress Log` that records date, approver, reason, and affected baseline content.

`Progress Log` is append-only from the first transition to `IN_PROGRESS`. Each transition records date, old and new state, reason, and supporting facts. Corrections are new entries that reference the prior entry; history is never deleted, reordered, or silently rewritten.

## 5. Verification

Move `IN_PROGRESS -> VERIFYING` only after every in-scope requirement is implemented, every acceptance criterion has implementation, no mandatory TODO remains, and the diff is ready. Run focused checks before relevant regression and static/diff checks. Under `Verification Evidence`, record every actual command and observed result; a bare PASS is insufficient. Include relevant counts, environment, migration state, or warnings when material.

A mandatory failure records the command and result, appends its reason to `Progress Log`, and moves `VERIFYING -> IN_PROGRESS`. No failing mandatory gate may enter `REVIEWING`.

## 6. Independent review

Enter `REVIEWING` only after focused, relevant regression, static/diff, migration when applicable, and all task-specific mandatory verification evidence pass. Review compares the implementation diff, frozen baseline, acceptance-criteria checklist, recorded verification evidence, architecture, authorization, transaction, scope, and regression rules relevant to the task. Review does not modify implementation code, scope, or acceptance criteria.

`Review Result` is exactly one of `PENDING`, `APPROVED`, or `CHANGES_REQUIRED`. `PENDING` is the default. `CHANGES_REQUIRED` includes concrete findings, appends evidence, and causes `REVIEWING -> IN_PROGRESS`. `APPROVED` records `Findings: none` or resolved findings.

## 7. Completion

Move `REVIEWING -> DONE` only after approved review, satisfied acceptance criteria, passed verification, and scoped diff review. `Completion Evidence` records final status, acceptance-criteria result, focused/regression/static-and-diff results, review, commit hash or `not required by task scope`, and completion date. A commit is created only with explicit user authorization.

## 8. Model and path stability

This repository uses Model A: one milestone equals one executable task. Internal schema, backend, API/RBAC, frontend, and E2E workstreams are not separately numbered executable tasks. Task paths are stable after `IN_PROGRESS`; any approved rename updates dependencies and references and is appended to `Progress Log`.

Strict single-task execution applies by default. Coordinated multi-task execution requires a separately approved rule that defines ownership, coordination, dependency handling, conflict resolution, verification responsibilities, and completion ordering.

## 9. Workflow diagram

```text
Explicit task file selected
        |
        v
Read selected task
        |
        v
Validate Status == READY
        |
        v
Validate explicit dependencies == DONE
        |
        v
Validate approved plan/spec and baseline
        |
        v
READY -> IN_PROGRESS
        |
        v
Implement In Scope
        |
        v
IN_PROGRESS -> VERIFYING
        |
        v
Run declared verification
        |
   +----+----+
   |         |
 FAIL       PASS
   |         |
   v         v
IN_PROGRESS REVIEWING
             |
        +----+----+
        |         |
 CHANGES_REQUIRED APPROVED
        |         |
        v         v
  IN_PROGRESS    DONE
```
