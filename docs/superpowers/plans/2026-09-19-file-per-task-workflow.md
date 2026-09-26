# File-per-Task Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace active `current-task.md` routing with an approved, explicit-path, file-per-task workflow and bootstrap its canonical template and migration task.

**Architecture:** Active repository instructions will route execution from one user-supplied `docs/tasks/...md` path. The selected task file owns status, immutable baseline, append-only history, verification evidence, review result, and completion evidence; shared progress documents are non-authoritative summaries. This migration is one repository-process executable task, `P-001`, and does not alter application code or the legacy `docs/plans/current-task.md` file.

**Tech Stack:** Markdown, PowerShell, ripgrep, and read-only Git verification.

**Spec:** `docs/superpowers/specs/2026-09-19-file-per-task-workflow-design.md`

## Global Constraints

- Model A is mandatory: one milestone equals one executable task.
- New implementation begins only from one explicit `docs/tasks/...md` path supplied by the user or approved calling workflow.
- Only explicit dependency task paths may be read for dependency validation.
- Official states are `READY -> IN_PROGRESS -> VERIFYING -> REVIEWING -> DONE`; only `VERIFYING -> IN_PROGRESS` and `REVIEWING -> IN_PROGRESS` are backward transitions.
- The selected task's baseline is immutable after `IN_PROGRESS` except through an explicitly approved, logged scope amendment.
- `Progress Log` is append-only after execution begins.
- Only one executable task may be in active implementation.
- `docs/plans/current-task.md` must not be modified, deleted, or used for active routing.
- No application source, application tests, migrations, dependencies, or remote Git state are in scope.
- No commit is created unless the user explicitly authorizes it under repository Git rules.

## File Map

| File | Action | Responsibility |
|---|---|---|
| `AGENTS.md` | Modify | Top-level task selection, state routing, dependency and Git rules |
| `docs/workflow/task-workflow.md` | Modify | Complete executable task lifecycle and evidence gates |
| `docs/rules/implementation-rules.md` | Modify | Pre-coding checks, frozen baseline, scope amendment, and task resume rules |
| `docs/rules/review-rules.md` | Modify | Independent review inputs, prohibited mutations, and result contract |
| `docs/tasks/task-template.md` | Create | Canonical non-executable task template |
| `docs/tasks/process/P-001-file-per-task-workflow.md` | Create | Authoritative executable task and evidence record for this migration |
| `docs/plans/current-task.md` | No change | Legacy file protected by before/after SHA-256 comparison |

---

### Task 1: P-001 — Adopt the File-per-Task Workflow

**Files:**
- Create: `docs/tasks/task-template.md`
- Create: `docs/tasks/process/P-001-file-per-task-workflow.md`
- Modify: `AGENTS.md`
- Modify: `docs/workflow/task-workflow.md`
- Modify: `docs/rules/implementation-rules.md`
- Modify: `docs/rules/review-rules.md`
- Verify unchanged: `docs/plans/current-task.md`

**Interfaces:**
- Consumes: approved specification `docs/superpowers/specs/2026-09-19-file-per-task-workflow-design.md` and this implementation plan.
- Produces: explicit task-path routing, canonical task template, process migration evidence, and a stable contract later Phase 1/Phase 2 task files can consume.

- [ ] **Step 1: Capture the protected legacy-file hash and inspect the exact initial diff**

Run:

```powershell
Get-FileHash -Algorithm SHA256 'docs/plans/current-task.md'
git status --short
git diff -- AGENTS.md docs/workflow/task-workflow.md docs/rules/implementation-rules.md docs/rules/review-rules.md
```

Expected:

- SHA-256 is exactly `636602A28EE8E1877EBCF450140BBAC8C14F66D9A14C7A01C0C7161EC36D43ED`.
- If the hash differs, stop: the protected legacy file changed after this plan was approved and
  the plan must be reviewed before execution.
- Existing unrelated changes remain untouched.
- The four active rule files can be distinguished from user-owned unrelated work before editing.

- [ ] **Step 2: Create the authoritative P-001 task file in `READY`**

Create `docs/tasks/process/P-001-file-per-task-workflow.md` with this execution baseline:

```markdown
# P-001 — Adopt the File-per-Task Workflow

## Metadata

- Status: READY
- Phase: process
- Plan: docs/superpowers/plans/2026-09-19-file-per-task-workflow.md
- Depends on: none
- Created: 2026-09-19
- Started: not started
- Completed: not completed

## Goal

Replace active shared-task routing with one explicit, authoritative Markdown file per executable task.

## Context

The approved workflow specification is `docs/superpowers/specs/2026-09-19-file-per-task-workflow-design.md`. This process task bootstraps the workflow and is exempt from a phase implementation plan because the approved specification identifies it as repository-process work.

## In Scope

- Update `AGENTS.md`.
- Update `docs/workflow/task-workflow.md`.
- Update `docs/rules/implementation-rules.md`.
- Update `docs/rules/review-rules.md`.
- Create `docs/tasks/task-template.md`.
- Record all P-001 state transitions and evidence in this file.

## Out of Scope

- Application source, tests, migrations, dependencies, and runtime behavior.
- Editing or deleting `docs/plans/current-task.md`.
- Creating Phase 1 or Phase 2 executable task files.
- Committing, pushing, or opening a pull request without explicit user authorization.

## Acceptance Criteria

- [ ] AC-1 — Active rules require one explicit `docs/tasks/...md` path before project modification.
- [ ] AC-2 — Active rules validate only explicit dependency paths and require every dependency to be `DONE`.
- [ ] AC-3 — Active rules implement state-aware start/resume behavior and the official state machine.
- [ ] AC-4 — Baseline, append-only progress, verification, review, and completion contracts match the approved specification.
- [ ] AC-5 — `docs/tasks/task-template.md` matches the canonical structure and is explicitly non-executable.
- [ ] AC-6 — Model A and single-task execution are explicit.
- [ ] AC-7 — `docs/plans/current-task.md` has the same SHA-256 value before and after migration.
- [ ] AC-8 — Documentation checks and independent review pass.

## Verification Commands

### Focused

Run the active-rule and template contract checks defined in Steps 10 and 11 of the implementation plan.

### Regression

Run the cross-document consistency checks defined in Step 12 of the implementation plan.

### Static and Diff

Run `git diff --check` and the protected-file SHA-256 comparison defined in Step 13 of the implementation plan.

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

- [ ] **Step 3: Validate the P-001 baseline before implementation**

Run:

```powershell
$taskPath = 'docs/tasks/process/P-001-file-per-task-workflow.md'
$content = Get-Content -Raw $taskPath
$required = @(
  '- Status: READY',
  '- Phase: process',
  '- Plan: docs/superpowers/plans/2026-09-19-file-per-task-workflow.md',
  '- Depends on: none',
  '- Created: 2026-09-19',
  '- Started: not started',
  '- Completed: not completed',
  '## Acceptance Criteria',
  '## Verification Commands',
  '## Progress Log',
  '## Verification Evidence',
  '## Review Result',
  '## Completion Evidence'
)
foreach ($value in $required) {
  if (-not $content.Contains($value)) { throw "Missing P-001 baseline value: $value" }
}
'P-001 READY baseline: PASS'
```

Expected: `P-001 READY baseline: PASS`.

- [ ] **Step 4: Transition P-001 from `READY` to `IN_PROGRESS`**

In `docs/tasks/process/P-001-file-per-task-workflow.md`:

- change `Status` to `IN_PROGRESS`;
- set `Started` to `2026-09-19`;
- keep `Created` unchanged and `Completed: not completed`;
- append this entry:

```markdown
### 2026-09-19 — READY -> IN_PROGRESS

- Dependencies: none.
- Approved repository-process specification verified.
- Implementation plan verified.
- Execution baseline frozen.
- Implementation started.
```

Do not rewrite the baseline after this transition unless an explicitly approved scope amendment is appended first.

- [ ] **Step 5: Create the canonical non-executable task template**

Create `docs/tasks/task-template.md` with:

```markdown
# <Task ID> — <Task title>

> Template only. This file is not executable, has no workflow status, and must never be selected as an implementation task.

## Metadata

- Status: READY
- Phase: <phase>
- Plan: <approved implementation plan path>
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

- [ ] **Step 6: Replace top-level routing in `AGENTS.md`**

Preserve the existing Git/GitHub safety rules. Replace active `current-task.md` routing with rules that state exactly:

- implementation requires one explicit task path under `docs/tasks/`;
- missing, ambiguous, template, or nonexistent paths block modification;
- only the selected task plus explicit dependencies and referenced stable plan/spec/rules may be read for routing;
- every dependency must be `DONE` before `READY -> IN_PROGRESS`;
- `READY` starts, `IN_PROGRESS` resumes implementation, `VERIFYING` resumes verification, `REVIEWING` resumes review, and `DONE` is not rerun without a separate explicit request;
- the only forward sequence is `READY -> IN_PROGRESS -> VERIFYING -> REVIEWING -> DONE`;
- verification or review failures return to `IN_PROGRESS`;
- task history and evidence are updated only in the selected task file;
- Model A and strict single-task execution apply;
- `docs/plans/current-task.md` is legacy and is neither read nor updated for routing.

- [ ] **Step 7: Rewrite `docs/workflow/task-workflow.md` to the approved lifecycle**

The workflow document must define:

1. explicit task selection and invalid-selection behavior;
2. metadata and timestamp semantics;
3. explicit-path dependency and approved-plan validation;
4. state-aware start/resume routing;
5. frozen baseline and approved scope-amendment procedure;
6. append-only progress history;
7. verification entry conditions, actual command/result evidence, and failure handling;
8. independent review entry conditions and `PENDING`/`APPROVED`/`CHANGES_REQUIRED` results;
9. completion evidence including commit hash or `not required by task scope`;
10. Model A, stable task paths, and single-task execution;
11. the final workflow diagram from the approved specification.

The document must not instruct agents to read, update, or select work through `docs/plans/current-task.md`.

- [ ] **Step 8: Align `docs/rules/implementation-rules.md`**

Replace “read the current task” with exact selected-task behavior. Require, before coding:

- explicit path validation;
- status-aware start/resume;
- explicit dependency and plan/spec checks;
- reading `Goal`, `Context`, `In Scope`, `Out of Scope`, `Acceptance Criteria`, and `Verification Commands`;
- freezing that baseline at `IN_PROGRESS`;
- appending an approved scope amendment before changing baseline content;
- keeping changes within the selected task;
- recording the transition to `VERIFYING` only after all in-scope implementation is complete.

Retain existing minimal-change, no-unrelated-refactor, backward-compatibility, TDD, focused-test, regression, and diff rules.

- [ ] **Step 9: Align `docs/rules/review-rules.md`**

Require independent review to compare:

- the implementation diff;
- the frozen task baseline;
- the AC checklist;
- recorded verification evidence;
- architecture, authorization, transaction, scope, and regression rules relevant to the task.

State that review does not modify implementation code, scope, or acceptance criteria. Define `PENDING`, `APPROVED`, and `CHANGES_REQUIRED`; required findings append evidence and cause `REVIEWING -> IN_PROGRESS`.

- [ ] **Step 10: Transition P-001 from `IN_PROGRESS` to `VERIFYING`**

Before the transition, confirm every file in `In Scope` exists and has no unfinished mandatory requirement. Then:

- change P-001 `Status` to `VERIFYING`;
- append:

```markdown
### 2026-09-19 — IN_PROGRESS -> VERIFYING

- All in-scope workflow documentation is implemented.
- Canonical template is present.
- No mandatory implementation item remains unfinished.
- Documentation diff is ready for verification.
```

- [ ] **Step 11: Run focused active-rule and template verification**

Run:

```powershell
$active = @(
  'AGENTS.md',
  'docs/workflow/task-workflow.md',
  'docs/rules/implementation-rules.md',
  'docs/rules/review-rules.md'
)
$activeText = ($active | ForEach-Object { Get-Content -Raw $_ }) -join "`n"
$required = @(
  'docs/tasks/',
  'READY',
  'IN_PROGRESS',
  'VERIFYING',
  'REVIEWING',
  'DONE',
  'Depends on',
  'Progress Log',
  'Verification Evidence',
  'CHANGES_REQUIRED'
)
foreach ($value in $required) {
  if (-not $activeText.Contains($value)) { throw "Active workflow contract missing: $value" }
}
$legacyMatches = rg -n 'current-task\.md' @active
if ($LASTEXITCODE -eq 0) { $legacyMatches; throw 'Active rule still routes through current-task.md' }
if ($LASTEXITCODE -ne 1) { throw "rg failed with exit code $LASTEXITCODE" }

$template = Get-Content -Raw 'docs/tasks/task-template.md'
$templateRequired = @(
  'Template only. This file is not executable',
  '- Status: READY',
  '- Created: YYYY-MM-DD',
  '- Started: not started',
  '- Completed: not completed',
  '- [ ] AC-1',
  '### Focused',
  '### Regression',
  '### Static and Diff',
  '- Result: PENDING'
)
foreach ($value in $templateRequired) {
  if (-not $template.Contains($value)) { throw "Template contract missing: $value" }
}
'Focused workflow checks: PASS'
```

Expected: `Focused workflow checks: PASS` and no active `current-task.md` reference.

Record the exact command and observed result under P-001 `Verification Evidence / Focused`.

- [ ] **Step 12: Run cross-document regression verification**

Run:

```powershell
$spec = Get-Content -Raw 'docs/superpowers/specs/2026-09-19-file-per-task-workflow-design.md'
$task = Get-Content -Raw 'docs/tasks/process/P-001-file-per-task-workflow.md'
$template = Get-Content -Raw 'docs/tasks/task-template.md'
$shared = @(
  'READY -> IN_PROGRESS -> VERIFYING -> REVIEWING -> DONE',
  'AC-1',
  'Verification Evidence',
  'Review Result',
  'Completion Evidence'
)
foreach ($value in $shared) {
  if (-not $spec.Contains($value)) { throw "Spec missing shared contract: $value" }
  if (-not $task.Contains($value) -and $value -ne 'READY -> IN_PROGRESS -> VERIFYING -> REVIEWING -> DONE') {
    throw "P-001 missing shared contract: $value"
  }
  if (-not $template.Contains($value) -and $value -ne 'READY -> IN_PROGRESS -> VERIFYING -> REVIEWING -> DONE') {
    throw "Template missing shared contract: $value"
  }
}
if ($spec -notmatch 'Model A') { throw 'Approved spec does not declare Model A' }
'Cross-document workflow checks: PASS'
```

Expected: `Cross-document workflow checks: PASS`.

Record the exact command and observed result under P-001 `Verification Evidence / Regression`.

- [ ] **Step 13: Run static, diff, and protected-file verification**

Run:

```powershell
git diff --check

$finalHash = (Get-FileHash -Algorithm SHA256 'docs/plans/current-task.md').Hash
$initialHash = '636602A28EE8E1877EBCF450140BBAC8C14F66D9A14C7A01C0C7161EC36D43ED'
if ($finalHash -ne $initialHash) {
  throw "docs/plans/current-task.md changed: initial=$initialHash final=$finalHash"
}

git status --short
git diff -- AGENTS.md docs/workflow/task-workflow.md docs/rules/implementation-rules.md docs/rules/review-rules.md
'Static, diff, and protected-file checks: PASS'
```

Expected:

- `git diff --check` exits successfully.
- Initial and final SHA-256 values are identical.
- The scoped diff contains only approved workflow changes; unrelated user changes remain untouched.
- Final line: `Static, diff, and protected-file checks: PASS`.

Record the final command, both hashes, and result under P-001 `Verification Evidence / Static and Diff`.

- [ ] **Step 14: Mark verified acceptance criteria and enter `REVIEWING`**

After Steps 11–13 pass:

- change each proven P-001 criterion from `[ ]` to `[x]`;
- leave any unproven criterion unchecked and return to `IN_PROGRESS` instead of continuing;
- change `Status` to `REVIEWING` only when AC-1 through AC-8 are all checked;
- append:

```markdown
### 2026-09-19 — VERIFYING -> REVIEWING

- Focused workflow verification passed.
- Cross-document regression verification passed.
- Static, diff, and protected-file verification passed.
- AC-1 through AC-8 are verified.
- Independent review started.
```

- [ ] **Step 15: Perform independent documentation review without editing implementation files**

Review the scoped diff against:

- the frozen P-001 baseline;
- AC-1 through AC-8;
- all recorded verification evidence;
- the approved workflow specification;
- Model A and single-task rules;
- the prohibition on active `current-task.md` routing;
- the protected-file SHA-256 evidence;
- unrelated-change risk.

If findings require changes:

- set `Review Result` to `CHANGES_REQUIRED` with concrete findings;
- append `REVIEWING -> IN_PROGRESS` to `Progress Log`;
- do not modify files during the review turn.

If review passes, set:

```markdown
## Review Result

- Result: APPROVED
- Findings: none
```

- [ ] **Step 16: Record completion and transition P-001 to `DONE`**

After review is `APPROVED`:

- set `Status: DONE`;
- keep `Created` and `Started` unchanged;
- set `Completed: 2026-09-19`;
- append `REVIEWING -> DONE` to `Progress Log`;
- record:

```markdown
## Completion Evidence

- Final status: DONE
- Acceptance criteria: AC-1 through AC-8 satisfied
- Focused verification: PASS
- Regression verification: PASS
- Static and diff verification: PASS
- Review: APPROVED
- Commit: not required by task scope
- Completed: 2026-09-19
```

If the user explicitly authorizes a local commit before completion, first run the repository-required `git status`, `git diff`, and `git diff --staged` checks, create one scoped documentation commit, and replace `Commit: not required by task scope` with the resulting commit hash. Never push or create a pull request without a separate explicit request.
