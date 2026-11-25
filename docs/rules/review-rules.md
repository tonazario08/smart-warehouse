# Review Rules

Review is independent from implementation and applies only to the explicitly selected executable task under `docs/tasks/`. Do not infer selection by scanning status or task directories. Review state uses the selected task's append-only evidence and the official `READY -> IN_PROGRESS -> VERIFYING -> REVIEWING -> DONE` lifecycle; required changes return `REVIEWING -> IN_PROGRESS`.

## Review entry and comparison

Enter review only after recorded focused, relevant regression, static/diff, migration when applicable, and task-specific mandatory verification evidence pass. Compare:

1. The implementation diff.
2. The frozen task baseline.
3. The AC checklist.
4. Recorded `Verification Evidence`.
5. Architecture, authorization, transaction, scope, and regression rules relevant to the task.

Also inspect requirement coverage, business rules, database behavior, tests, and unnecessary changes where applicable.

## Result contract

`Review Result` is one of `PENDING`, `APPROVED`, or `CHANGES_REQUIRED`. A new task starts as `PENDING`. `APPROVED` records `Findings: none` or resolved findings. `CHANGES_REQUIRED` lists concrete findings, appends review evidence to the selected task, and records `REVIEWING -> IN_PROGRESS` before any implementation resumes.

## Prohibited review behavior

- Do not modify implementation code during review.
- Do not change scope or acceptance criteria during review.
- Do not add unrelated requirements or recommend large unrelated refactors.
- Do not treat passing tests as the only evidence of correctness.
- Do not modify task history or evidence outside the selected task file.

For each required finding, provide concrete evidence. A task reaches `DONE` only after `APPROVED`, satisfied ACs, recorded verification evidence, and scoped-diff review.
