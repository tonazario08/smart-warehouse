# File-per-Task Workflow Design

**Status:** Approved  
**Date:** 2026-09-19  
**Approved:** 2026-09-19

## 1. Purpose

Replace the mutable `docs/plans/current-task.md` routing model with one Markdown file per task.
Each task file is the authoritative record for its own requirements, state transitions,
verification evidence, review result, and completion status.

This change prevents unrelated tasks from overwriting one shared task document and makes task
history directly traceable to the work it describes.

## 2. Core Rules

1. Every executable task has exactly one authoritative Markdown file.
2. Task files live under `docs/tasks/<phase>/`.
3. A user must identify the task file path explicitly when requesting implementation.
4. The agent must not infer an active task by scanning status values or plan order.
5. If the request does not identify a task file, the agent asks for the path and does not modify
   project files.
6. Every state transition and all task-specific evidence are written only to that task file.
7. Dependencies use explicit task file paths and are validated without scanning task directories.
8. The referenced approved plan and stable specifications are validated before implementation.
9. Only one task may be executed at a time unless a later rule explicitly defines coordinated
   multi-task execution.
10. A task may enter `IN_PROGRESS` only when every task file declared in its `Depends on`
    metadata has reached `DONE`.

## 3. Directory and Naming Convention

Task files use:

```text
docs/tasks/<phase>/<task-id>-<slug>.md
```

Examples:

```text
docs/tasks/phase-1/1.7-authentication-rbac.md
docs/tasks/phase-2/2.1-location-management.md
docs/tasks/process/P-001-file-per-task-workflow.md
```

Requirements:

- `<phase>` is a stable grouping such as `phase-1`, `phase-2`, or `process`.
- `<task-id>` matches the approved implementation plan identifier.
- `<slug>` is lowercase kebab-case and describes the task outcome.
- Once a task enters `IN_PROGRESS`, its file path is stable. Renaming or moving it is prohibited
  unless the user explicitly approves the migration. An approved rename updates dependency
  paths, implementation plans, documentation links, repository rules, and scripts or automation
  that reference the old path. The rename and affected references are appended to the task's
  `Progress Log`.

This repository uses **Model A: one milestone equals one executable task**. Phase 2 milestone
`2.1 Location Management`, for example, is represented by exactly one executable task file:

```text
docs/tasks/phase-2/2.1-location-management.md
```

Schema/migration, backend, API/RBAC, frontend, and E2E work are internal workstreams within that
task; they do not receive identifiers such as `2.1.1` or separate executable task files. The
repository must not mix Model A with milestone-subtask identifiers.

The repository provides `docs/tasks/task-template.md` as the canonical template. The template is
not an executable task and has no workflow status.

## 4. Required Task File Structure

Each executable task file contains these sections:

```markdown
# <Task ID> — <Task title>

## Metadata

- Status: READY
- Phase: <phase>
- Plan: <path to approved implementation plan>
- Depends on: none
- Created: YYYY-MM-DD
- Started: not started
- Completed: not completed

## Goal

## Context

## In Scope

## Out of Scope

## Acceptance Criteria

- [ ] AC-1 — <verifiable outcome>
- [ ] AC-2 — <verifiable outcome>

## Verification Commands

### Focused

### Regression

### Static and Diff

## Progress Log

## Verification Evidence

### Focused

### Regression

### Static and Diff

## Review Result

- Result: PENDING
- Findings: not reviewed

## Completion Evidence
```

The task file must be sufficiently specific to execute without consulting a mutable central task
record. It may reference stable specifications, plans, rules, and API contracts instead of
duplicating them.

Acceptance criteria use stable identifiers and Markdown checkboxes. Each criterion begins as
`- [ ] AC-n — ...` and changes to `- [x] AC-n — ...` only after recorded verification proves the
criterion. Completion evidence summarizes the checklist but does not replace it.

`Created` is immutable. `Started` is set once, when the task first moves from `READY` to
`IN_PROGRESS`. `Completed` is set only when the task moves from `REVIEWING` to `DONE`.

Dependencies are either `none` or explicit repository-relative task paths:

```markdown
- Depends on:
  - docs/tasks/phase-2/2.1-location-management.md
  - docs/tasks/phase-2/2.2-transfer.md
```

Task IDs alone are not valid dependency references.

## 5. Task Selection and Routing

An implementation request from the user or an approved calling workflow must include one exact
repository-relative task path, for example:

```text
Thực hiện docs/tasks/phase-2/2.1-location-management.md
```

The agent then:

1. validates that the path stays under `docs/tasks/`;
2. verifies that the file exists and is not the template;
3. reads `AGENTS.md` and exactly the selected task file;
4. determines whether the selected task is starting or resuming from its recorded status;
5. reads only dependency task files explicitly listed in `Depends on` and verifies that each is
   `DONE`;
6. verifies that the referenced implementation plan exists, contains the task identifier, and
   defines scope consistent with the task file;
7. reads only the stable rules and specifications referenced by the selected task or its approved
   plan;
8. checks scope, acceptance-criteria checklist, and verification commands;
9. follows the state-specific routing rules below and executes only the selected task.

If the path is missing, ambiguous, outside `docs/tasks/`, points to multiple files, or names a
nonexistent file, the agent stops before implementation and requests one exact task path.

The agent does not choose the first `READY` task, the only `IN_PROGRESS` task, or the next task in
an implementation plan. Explicit selection is always required.

The agent must not determine the active task by searching status values, scanning task numbers,
selecting the first unfinished task, inferring plan order, or using file modification time.

Selection behavior depends on the selected task's recorded state:

- `READY`: after dependency, plan, specification, and baseline validation, start new
  implementation and record `READY -> IN_PROGRESS`.
- `IN_PROGRESS`: continue only that task's implementation from its existing baseline and
  append-only history. Do not recreate the baseline, reset timestamps, or rewrite prior progress.
- `VERIFYING`: continue only the declared verification workflow. Implementation changes require
  recording `VERIFYING -> IN_PROGRESS` first.
- `REVIEWING`: continue only independent review. Required changes record
  `REVIEWING -> IN_PROGRESS` before implementation resumes.
- `DONE`: report existing completion evidence and do not execute the task again unless the user
  makes a separate explicit request defining the new work.

A task cannot enter `IN_PROGRESS` while a dependency is not `DONE`, the approved plan is absent,
the task identifier is missing from that plan, or a plan/task scope conflict remains unresolved.
The task stays `READY`, and the blocking evidence is appended to its progress log.

Process tasks may omit a phase implementation plan only when an approved specification explicitly
identifies the task as repository-process work and the task metadata uses that specification as
its plan authority.

## 6. State Machine

The allowed execution path remains:

```text
READY -> IN_PROGRESS -> VERIFYING -> REVIEWING -> DONE
```

The only allowed backward transitions are:

```text
VERIFYING -> IN_PROGRESS
REVIEWING -> IN_PROGRESS
```

Transitions that skip required gates are prohibited, including:

```text
READY -> VERIFYING
READY -> DONE
IN_PROGRESS -> DONE
VERIFYING -> DONE
```

Rules:

- `READY`: dependencies, plan authority, scope, and execution baseline are checked. Missing
  prerequisites keep the task at `READY`; they do not authorize assumptions or implementation.
- `IN_PROGRESS`: implementation is limited to the selected file's scope.
- `VERIFYING`: focused tests run before relevant regression and static/diff checks.
- `REVIEWING`: review is independent from implementation and does not modify code.
- `DONE`: implementation, acceptance criteria, verification, approved review, and diff scope all
  pass.
- A status cannot be skipped.
- A transition is recorded in the selected task's progress log with date and reason.
- Without sufficient evidence, the result is `NOT VERIFIED`, not `DONE`.

## 7. Task Specification Baseline and Amendments

Before implementation starts, these task sections form the execution baseline:

- `Goal`
- `Context`
- `In Scope`
- `Out of Scope`
- `Acceptance Criteria`
- `Verification Commands`

After the task enters `IN_PROGRESS`, baseline sections must not be silently rewritten to match
the implementation. A required scope or acceptance-criteria change must:

1. receive explicit user approval;
2. be appended as a scope amendment in `Progress Log`;
3. update the affected baseline sections;
4. record the reason, approver, and date.

Acceptance criteria must never be weakened solely to make incomplete work pass verification.

## 8. Append-Only Progress Log

`Progress Log` becomes append-only when the task first enters `IN_PROGRESS`. Existing entries
must not be deleted, reordered, or silently rewritten. Incorrect historical information is
corrected through a new entry that references the earlier entry.

Every state transition is recorded with date, old state, new state, reason, and supporting facts.
For example:

```markdown
### 2026-09-19 — READY -> IN_PROGRESS

- Dependencies verified.
- Approved plan verified.
- Implementation started.

### 2026-09-19 — IN_PROGRESS -> VERIFYING

- In-scope implementation completed.
- No mandatory implementation TODO remains.
- Verification started.
```

Blocking prerequisites found while a task is still `READY` are also appended without changing the
official status.

## 9. Verification Entry, Evidence, and Failure Handling

### 9.1 Entry conditions

A task may move from `IN_PROGRESS` to `VERIFYING` only when:

- all work required by `In Scope` is implemented;
- every acceptance criterion has corresponding implementation;
- no known TODO remains for a mandatory requirement;
- the implementation diff is ready for verification.

Verification is not a substitute for unfinished implementation.

### 9.2 Evidence contract

Verification evidence records each actual command and its observed result. `Tests PASS` without a
command and result is insufficient. The minimum structure is:

```markdown
## Verification Evidence

### Focused

Command:

`pytest tests/locations -q`

Result:

`18 passed`

### Regression

Command:

`pytest -q`

Result:

`126 passed, 2 deselected`

### Static and Diff

Command:

`git diff --check`

Result:

`PASS`
```

Where relevant, evidence also records test, failure, skip, and deselection counts; environment;
database type; migration revision/state; and important warnings. Full terminal output is included
only when needed to explain a failure or support a disputed result.

### 9.3 Failure handling

If any mandatory verification command fails, the task moves `VERIFYING -> IN_PROGRESS`. The
failed command and result are appended to `Verification Evidence`, and the transition and reason
are appended to `Progress Log`. A new verification attempt begins only after the implementation
is corrected. A task cannot enter `REVIEWING` while any mandatory gate is failing.

## 10. Review Entry and Result Contract

### 10.1 Entry conditions

A task may move from `VERIFYING` to `REVIEWING` only when focused, relevant regression, static,
diff, migration when applicable, and every task-specific mandatory verification command pass.

### 10.2 Result values

`Review Result` uses only:

```text
PENDING
APPROVED
CHANGES_REQUIRED
```

The default is:

```markdown
## Review Result

- Result: PENDING
- Findings: not reviewed
```

A successful review records `Result: APPROVED` and either `Findings: none` or resolved findings.
Required changes record `Result: CHANGES_REQUIRED` and a concrete findings list. The task then
moves `REVIEWING -> IN_PROGRESS`; it cannot move to `DONE` until a later independent review is
`APPROVED`.

Independent review evaluates the implementation diff against the task's frozen execution
baseline, acceptance-criteria checklist, and recorded verification evidence. The review turn must
not modify implementation code, silently change scope, or edit acceptance criteria to make the
task pass. A scope amendment follows Section 7; an implementation finding produces
`CHANGES_REQUIRED` and returns the task to `IN_PROGRESS`.

## 11. Completion Evidence

A task moves from `REVIEWING` to `DONE` only when `Completion Evidence` confirms every required
gate. The minimum structure is:

```markdown
## Completion Evidence

- Final status: DONE
- Acceptance criteria: all satisfied
- Focused verification: PASS
- Regression verification: PASS
- Static and diff verification: PASS
- Review: APPROVED
- Commit: <commit hash>
- Completed: YYYY-MM-DD
```

When the approved task scope explicitly does not require a commit, use:

```markdown
- Commit: not required by task scope
```

Implementation tasks normally record the final local commit hash, but a commit is created only
when the user has authorized it under repository Git rules. The metadata `Completed` value and
completion-evidence date must match the successful `REVIEWING -> DONE` transition.

## 12. Evidence Ownership

The selected task file owns:

- current status;
- transition history;
- commands executed and their results;
- acceptance-criteria checklist;
- review verdict and findings;
- completion summary;
- commit identifier when a commit is explicitly authorized and created.

`PROGRESS.md`, release notes, and shared verification logs may summarize completed tasks, but they
are never authoritative for task selection or status. A summary must link back to the task file.

## 13. Legacy `current-task.md`

`docs/plans/current-task.md` is legacy after this workflow is adopted.

- It is not read for routing.
- It is not updated during task execution.
- It is not used to select the next task.
- This workflow change does not edit or delete it.
- It may be archived or removed only through a separately selected task with explicit user
  approval.

Existing historical references to `current-task.md` in past plans or reports remain historical
evidence and do not need bulk rewriting. Active instructions in `AGENTS.md`,
`docs/workflow/task-workflow.md`, and implementation rules must use the selected task file model.

## 14. Rule and Documentation Changes

Implementing this design changes only workflow documentation and task scaffolding:

- update `AGENTS.md` to require an explicit task file path and route by its status;
- update `docs/workflow/task-workflow.md` to read and update the selected task file;
- update `docs/rules/implementation-rules.md` to require the selected task file before coding;
- update `docs/rules/review-rules.md` so review uses the selected task file;
- add `docs/tasks/task-template.md`;
- add `docs/tasks/process/P-001-file-per-task-workflow.md` to execute and record this workflow
  migration.

`docs/plans/current-task.md` is outside the write scope.

## 15. Error Handling

The workflow fails closed:

- Missing task path: ask the user for one exact path.
- Missing task file: report the missing path; do not create an inferred task.
- Invalid task structure: retain `READY`, append the blocking evidence, and list missing sections.
- Unmet dependency: retain `READY` and append the dependency evidence.
- Multiple task paths: ask the user to select one unless the request explicitly concerns a
  non-execution comparison or review.
- Task already `DONE`: report its completion evidence; do not rerun or begin another task without
  an explicit request.
- Task in `IN_PROGRESS`: resume only the selected task against its existing baseline and
  append-only progress log; do not recreate metadata, reset `Started`, or discard prior evidence.
- Task in `VERIFYING` or `REVIEWING`: resume only that state; do not restart implementation unless
  verification or review returns it to `IN_PROGRESS`.

## 16. Single-Task Execution

Only one executable task may be in active implementation at one time. The default workflow does
not support parallel execution of multiple task files.

Coordinated multi-task execution may be introduced only by a separate approved rule that defines
ownership, shared-file coordination, dependency handling, conflict resolution, verification
responsibilities, and completion ordering. Until then, execution is strictly single-task.

## 17. Workflow-Migration Verification

The workflow migration is verified by documentation checks rather than application tests:

1. Search active rule files and confirm they no longer route through
   `docs/plans/current-task.md`.
2. Confirm every active rule names the explicitly selected task file as the source of truth.
3. Confirm the task template contains all required sections and allowed states.
4. Confirm the process task file follows the template and records its own transitions.
5. Confirm `docs/plans/current-task.md` has no diff.
6. Run `git diff --check` on all workflow files.
7. Review the documentation diff for contradictions, ambiguous selection behavior, and unrelated
   changes.

## 18. Acceptance Criteria

The workflow change is complete when:

- a task cannot begin without one explicit `docs/tasks/...md` path;
- all active workflow rules use that selected file for routing and state updates;
- each task file contains scope, acceptance criteria, verification, review, and completion
  evidence;
- no active rule instructs the agent to update `current-task.md`;
- `current-task.md` remains unchanged;
- the canonical template and process-migration task exist;
- documentation verification and independent review pass;
- no commit or remote action occurs without explicit authorization.

## 19. Workflow Summary

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

## 20. Approval Gate

This specification may move from `Draft` to `Approved` only when:

- the official state machine and prohibited transitions are explicit;
- dependency, approved-plan, and stable-spec validation are explicit;
- metadata fields and timestamp semantics are finalized;
- baseline sections and approved scope-amendment rules are defined;
- progress history and verification attempts preserve append-only evidence;
- verification and review entry conditions are complete;
- review and completion evidence contracts are complete;
- Model A is consistently applied to milestone and task identifiers;
- explicit task-file selection and stable-path rules are mandatory;
- single-task execution is the default;
- the canonical task template matches this specification;
- the workflow specification passes self-review and receives explicit user approval.
