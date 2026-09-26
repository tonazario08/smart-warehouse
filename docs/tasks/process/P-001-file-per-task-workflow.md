# P-001 — Adopt the File-per-Task Workflow

## Metadata

- Status: DONE
- Phase: process
- Plan: docs/superpowers/plans/2026-09-19-file-per-task-workflow.md
- Depends on: none
- Created: 2026-09-19
- Started: 2026-09-19
- Completed: 2026-09-20

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

- [x] AC-1 — Active rules require one explicit `docs/tasks/...md` path before project modification.
- [x] AC-2 — Active rules validate only explicit dependency paths and require every dependency to be `DONE`.
- [x] AC-3 — Active rules implement state-aware start/resume behavior and the official state machine.
- [x] AC-4 — Baseline, append-only progress, verification, review, and completion contracts match the approved specification.
- [x] AC-5 — `docs/tasks/task-template.md` matches the canonical structure and is explicitly non-executable.
- [x] AC-6 — Model A and single-task execution are explicit.
- [x] AC-7 — `docs/plans/current-task.md` has the same SHA-256 value before and after migration.
- [x] AC-8 — Documentation checks and independent review pass.

## Verification Commands

### Focused

Run the active-rule and template contract checks defined in Steps 10 and 11 of the implementation plan.

### Regression

Run the cross-document consistency checks defined in Step 12 of the implementation plan.

### Static and Diff

Run `git diff --check` and the protected-file SHA-256 comparison defined in Step 13 of the implementation plan.

## Progress Log

### 2026-09-19 — READY -> IN_PROGRESS

- Dependencies: none.
- Approved repository-process specification verified.
- Implementation plan verified.
- Execution baseline frozen.
- Implementation started.

### 2026-09-19 — IN_PROGRESS -> VERIFYING

- All in-scope workflow documentation is implemented.
- Canonical template is present.
- No mandatory implementation item remains unfinished.
- Documentation diff is ready for verification.

### 2026-09-19 — VERIFYING -> REVIEWING

- Focused workflow verification passed.
- Cross-document regression verification passed.
- Static, diff, and protected-file verification passed.
- AC-1 through AC-7 are verified; AC-8 awaits the required independent review.
- Documentation self-review found no blocking issue.
- Independent review started.

### 2026-09-20 — REVIEWING -> IN_PROGRESS

- Independent review returned `CHANGES_REQUIRED`.
- `AGENTS.md` had removed required Git/GitHub safeguards from the pre-existing rules.
- Verification Evidence omitted PASS-emitting command lines and did not record scoped status/diff observations.
- Controller ruling recorded: AC-8 is the review exit gate, remains frozen and unchecked until independent review approves it, and does not block entry to `REVIEWING`.
- Fix implementation started.

### 2026-09-20 — IN_PROGRESS -> VERIFYING

- Restored the pre-existing Git/GitHub safeguards in `AGENTS.md` without removing file-per-task routing.
- Prepared complete command/result evidence with scoped status and diff observations.
- Fix diff is ready for documentation verification.

### 2026-09-20 — VERIFYING -> REVIEWING

- Post-fix focused workflow verification passed.
- Post-fix cross-document regression verification passed.
- Post-fix static, scoped-diff, and protected-file verification passed.
- AC-8 remains unchecked under the controller ruling because it is the independent-review exit gate.
- Independent re-review started.

### 2026-09-20 — REVIEWING -> DONE

- Independent re-review returned `APPROVED`.
- All acceptance criteria are verified, including AC-8.
- No blocking finding remains.
- Completion evidence is recorded below.

### 2026-09-20 — Post-completion evidence correction

- Final review found that the authoritative-field verification searched the entire task file and could self-match expected strings inside its own fenced command or evidence.
- Final review also found that Completion Evidence omitted the minimum canonical completion fields.
- The correction below adds section-aware verification evidence and the missing canonical completion fields without changing the frozen baseline, scope, or final status.

## Verification Evidence

### Focused

Command:

```powershell
$active = @('AGENTS.md', 'docs/workflow/task-workflow.md', 'docs/rules/implementation-rules.md', 'docs/rules/review-rules.md')
$activeText = ($active | ForEach-Object { Get-Content -Raw $_ }) -join "`n"
$required = @('docs/tasks/', 'READY', 'IN_PROGRESS', 'VERIFYING', 'REVIEWING', 'DONE', 'Depends on', 'Progress Log', 'Verification Evidence', 'CHANGES_REQUIRED')
foreach ($value in $required) { if (-not $activeText.Contains($value)) { throw "Active workflow contract missing: $value" } }
$legacyMatches = rg -n 'current-task\.md' @active
if ($LASTEXITCODE -eq 0) { $legacyMatches; throw 'Active rule still routes through current-task.md' }
if ($LASTEXITCODE -ne 1) { throw "rg failed with exit code $LASTEXITCODE" }
$template = Get-Content -Raw 'docs/tasks/task-template.md'
$templateRequired = @('Template only. This file is not executable', '- Status: READY', '- Created: YYYY-MM-DD', '- Started: not started', '- Completed: not completed', '- [ ] AC-1', '### Focused', '### Regression', '### Static and Diff', '- Result: PENDING')
foreach ($value in $templateRequired) { if (-not $template.Contains($value)) { throw "Template contract missing: $value" } }
```

Result:

`Focused workflow checks: PASS`

### Regression

Command:

```powershell
$spec = Get-Content -Raw 'docs/superpowers/specs/2026-09-19-file-per-task-workflow-design.md'
$task = Get-Content -Raw 'docs/tasks/process/P-001-file-per-task-workflow.md'
$template = Get-Content -Raw 'docs/tasks/task-template.md'
$shared = @('READY -> IN_PROGRESS -> VERIFYING -> REVIEWING -> DONE', 'AC-1', 'Verification Evidence', 'Review Result', 'Completion Evidence')
foreach ($value in $shared) {
  if (-not $spec.Contains($value)) { throw "Spec missing shared contract: $value" }
  if (-not $task.Contains($value) -and $value -ne 'READY -> IN_PROGRESS -> VERIFYING -> REVIEWING -> DONE') { throw "P-001 missing shared contract: $value" }
  if (-not $template.Contains($value) -and $value -ne 'READY -> IN_PROGRESS -> VERIFYING -> REVIEWING -> DONE') { throw "Template missing shared contract: $value" }
}
if ($spec -notmatch 'Model A') { throw 'Approved spec does not declare Model A' }
```

Result:

`Cross-document workflow checks: PASS`

### Static and Diff

Command:

```powershell
git diff --check
$finalHash = (Get-FileHash -Algorithm SHA256 'docs/plans/current-task.md').Hash
$initialHash = '636602A28EE8E1877EBCF450140BBAC8C14F66D9A14C7A01C0C7161EC36D43ED'
if ($finalHash -ne $initialHash) { throw "docs/plans/current-task.md changed: initial=$initialHash final=$finalHash" }
git status --short
git diff -- AGENTS.md docs/workflow/task-workflow.md docs/rules/implementation-rules.md docs/rules/review-rules.md
```

Initial SHA-256: `636602A28EE8E1877EBCF450140BBAC8C14F66D9A14C7A01C0C7161EC36D43ED`

Final SHA-256: `636602A28EE8E1877EBCF450140BBAC8C14F66D9A14C7A01C0C7161EC36D43ED`

Result:

`Static, diff, and protected-file checks: PASS`

### Fix round 1 post-fix rerun — 2026-09-20

Focused command:

```powershell
$active = @('AGENTS.md', 'docs/workflow/task-workflow.md', 'docs/rules/implementation-rules.md', 'docs/rules/review-rules.md')
$covered = $active + @('docs/tasks/task-template.md', 'docs/tasks/process/P-001-file-per-task-workflow.md')
foreach ($path in $covered) { if (-not (Test-Path $path)) { throw "Covered workflow file missing: $path" } }
$activeText = ($active | ForEach-Object { Get-Content -Raw $_ }) -join "`n"
$required = @('docs/tasks/', 'READY', 'IN_PROGRESS', 'VERIFYING', 'REVIEWING', 'DONE', 'Depends on', 'Progress Log', 'Verification Evidence', 'CHANGES_REQUIRED')
foreach ($value in $required) { if (-not $activeText.Contains($value)) { throw "Active workflow contract missing: $value" } }
$legacyMatches = rg -n 'current-task\.md' @active
if ($LASTEXITCODE -eq 0) { $legacyMatches; throw 'Active rule still routes through current-task.md' }
if ($LASTEXITCODE -ne 1) { throw "rg failed with exit code $LASTEXITCODE" }
$template = Get-Content -Raw 'docs/tasks/task-template.md'
$templateRequired = @('Template only. This file is not executable', '- Status: READY', '- Created: YYYY-MM-DD', '- Started: not started', '- Completed: not completed', '- [ ] AC-1', '### Focused', '### Regression', '### Static and Diff', '- Result: PENDING')
foreach ($value in $templateRequired) { if (-not $template.Contains($value)) { throw "Template contract missing: $value" } }
$task = Get-Content -Raw 'docs/tasks/process/P-001-file-per-task-workflow.md'
$taskRequired = @('- Status: VERIFYING', '- [ ] AC-8 — Documentation checks and independent review pass.', '### 2026-09-20 — REVIEWING -> IN_PROGRESS', '### 2026-09-20 — IN_PROGRESS -> VERIFYING', '- Result: CHANGES_REQUIRED')
foreach ($value in $taskRequired) { if (-not $task.Contains($value)) { throw "P-001 fix-state contract missing: $value" } }
'Focused workflow checks: PASS'
```

Observed output:

```text
Focused workflow checks: PASS
```

Regression command:

```powershell
$spec = Get-Content -Raw 'docs/superpowers/specs/2026-09-19-file-per-task-workflow-design.md'
$task = Get-Content -Raw 'docs/tasks/process/P-001-file-per-task-workflow.md'
$template = Get-Content -Raw 'docs/tasks/task-template.md'
$shared = @('READY -> IN_PROGRESS -> VERIFYING -> REVIEWING -> DONE', 'AC-1', 'Verification Evidence', 'Review Result', 'Completion Evidence')
foreach ($value in $shared) {
  if (-not $spec.Contains($value)) { throw "Spec missing shared contract: $value" }
  if (-not $task.Contains($value) -and $value -ne 'READY -> IN_PROGRESS -> VERIFYING -> REVIEWING -> DONE') { throw "P-001 missing shared contract: $value" }
  if (-not $template.Contains($value) -and $value -ne 'READY -> IN_PROGRESS -> VERIFYING -> REVIEWING -> DONE') { throw "Template missing shared contract: $value" }
}
if ($spec -notmatch 'Model A') { throw 'Approved spec does not declare Model A' }
'Cross-document workflow checks: PASS'
```

Observed output:

```text
Cross-document workflow checks: PASS
```

Static and scoped-diff command:

```powershell
git diff --check
if ($LASTEXITCODE -ne 0) { throw "git diff --check failed with exit code $LASTEXITCODE" }
$finalHash = (Get-FileHash -Algorithm SHA256 'docs/plans/current-task.md').Hash
$initialHash = '636602A28EE8E1877EBCF450140BBAC8C14F66D9A14C7A01C0C7161EC36D43ED'
if ($finalHash -ne $initialHash) { throw "docs/plans/current-task.md changed: initial=$initialHash final=$finalHash" }
$scoped = @('AGENTS.md', 'docs/workflow/task-workflow.md', 'docs/rules/implementation-rules.md', 'docs/rules/review-rules.md', 'docs/tasks/task-template.md', 'docs/tasks/process/P-001-file-per-task-workflow.md')
'Scoped status:'
git status --short -- $scoped
'Scoped tracked diff summary:'
git diff --stat -- $scoped
"Protected-file SHA-256: $finalHash"
'Static, diff, and protected-file checks: PASS'
```

Observed output:

```text
Scoped status:
 M AGENTS.md
?? docs/rules/implementation-rules.md
?? docs/rules/review-rules.md
?? docs/tasks/process/P-001-file-per-task-workflow.md
?? docs/tasks/task-template.md
?? docs/workflow/task-workflow.md
Scoped tracked diff summary:
 AGENTS.md | 54 ++++++++++++++++++++++++++++++++++++++++++++++++++++--
 1 file changed, 52 insertions(+), 2 deletions(-)
Protected-file SHA-256: 636602A28EE8E1877EBCF450140BBAC8C14F66D9A14C7A01C0C7161EC36D43ED
Static, diff, and protected-file checks: PASS
```

### Fix round 1 final rerun — 2026-09-20

Command:

```powershell
$covered = @('AGENTS.md', 'docs/workflow/task-workflow.md', 'docs/rules/implementation-rules.md', 'docs/rules/review-rules.md', 'docs/tasks/task-template.md', 'docs/tasks/process/P-001-file-per-task-workflow.md')
foreach ($path in $covered) { if (-not (Test-Path $path)) { throw "Covered workflow file missing: $path" } }
git diff --check
if ($LASTEXITCODE -ne 0) { throw "git diff --check failed with exit code $LASTEXITCODE" }
$finalHash = (Get-FileHash -Algorithm SHA256 'docs/plans/current-task.md').Hash
if ($finalHash -ne '636602A28EE8E1877EBCF450140BBAC8C14F66D9A14C7A01C0C7161EC36D43ED') { throw "Protected file changed: $finalHash" }
$active = @('AGENTS.md', 'docs/workflow/task-workflow.md', 'docs/rules/implementation-rules.md', 'docs/rules/review-rules.md')
rg -n 'current-task\.md' @active
if ($LASTEXITCODE -ne 1) { throw "Active legacy-routing search expected exit code 1, got $LASTEXITCODE" }
$task = Get-Content -Raw 'docs/tasks/process/P-001-file-per-task-workflow.md'
foreach ($value in @('- Status: REVIEWING', '- [ ] AC-8 — Documentation checks and independent review pass.', '- Result: PENDING', 'Fix round 1 post-fix rerun')) { if (-not $task.Contains($value)) { throw "Final handoff task contract missing: $value" } }
'Scoped status:'
git status --short -- $covered
'Scoped tracked diff summary:'
git diff --stat -- $covered
"Protected-file SHA-256: $finalHash"
'Final post-fix rerun: PASS'
```

Observed output:

```text
Scoped status:
 M AGENTS.md
?? docs/rules/implementation-rules.md
?? docs/rules/review-rules.md
?? docs/tasks/process/P-001-file-per-task-workflow.md
?? docs/tasks/task-template.md
?? docs/workflow/task-workflow.md
Scoped tracked diff summary:
 AGENTS.md | 54 ++++++++++++++++++++++++++++++++++++++++++++++++++++--
 1 file changed, 52 insertions(+), 2 deletions(-)
Protected-file SHA-256: 636602A28EE8E1877EBCF450140BBAC8C14F66D9A14C7A01C0C7161EC36D43ED
Final post-fix rerun: PASS
```

### Final-review evidence correction — 2026-09-20

Command:

```powershell
$path = 'docs/tasks/process/P-001-file-per-task-workflow.md'
$lines = @(Get-Content -LiteralPath $path)

function Get-HeadingIndex {
  param(
    [Parameter(Mandatory = $true)][string]$Heading,
    [Parameter(Mandatory = $true)][int]$StartAt
  )

  for ($index = $StartAt; $index -lt $lines.Count; $index++) {
    if ($lines[$index] -ceq $Heading) { return $index }
  }

  throw "Required heading missing or out of order: $Heading"
}

function Get-LinesBetween {
  param(
    [Parameter(Mandatory = $true)][int]$StartIndex,
    [Parameter(Mandatory = $true)][int]$EndIndex,
    [Parameter(Mandatory = $true)][string]$SectionName
  )

  if ($EndIndex -le ($StartIndex + 1)) { throw "Section is empty or headings are out of order: $SectionName" }
  $result = [System.Collections.Generic.List[string]]::new()
  for ($index = $StartIndex + 1; $index -lt $EndIndex; $index++) {
    [void]$result.Add($lines[$index])
  }
  return $result.ToArray()
}

function Assert-SingleExactField {
  param(
    [Parameter(Mandatory = $true)]$Block,
    [Parameter(Mandatory = $true)][string]$FieldPattern,
    [Parameter(Mandatory = $true)][string]$Expected,
    [Parameter(Mandatory = $true)][string]$SectionName
  )

  $fields = @($Block | Where-Object { $_ -cmatch $FieldPattern })
  if ($fields.Count -ne 1 -or $fields[0] -cne $Expected) {
    throw "$SectionName must contain exactly: $Expected"
  }
}

function Assert-SingleExactLine {
  param(
    [Parameter(Mandatory = $true)]$Block,
    [Parameter(Mandatory = $true)][string]$Expected,
    [Parameter(Mandatory = $true)][string]$SectionName
  )

  $matches = @($Block | Where-Object { $_ -ceq $Expected })
  if ($matches.Count -ne 1) { throw "$SectionName must contain exactly one line: $Expected" }
}

$metadataStart = Get-HeadingIndex -Heading '## Metadata' -StartAt 0
$goalStart = Get-HeadingIndex -Heading '## Goal' -StartAt ($metadataStart + 1)
$acceptanceStart = Get-HeadingIndex -Heading '## Acceptance Criteria' -StartAt ($goalStart + 1)
$verificationCommandsStart = Get-HeadingIndex -Heading '## Verification Commands' -StartAt ($acceptanceStart + 1)
$reviewStart = Get-HeadingIndex -Heading '## Review Result' -StartAt ($verificationCommandsStart + 1)
$completionStart = Get-HeadingIndex -Heading '## Completion Evidence' -StartAt ($reviewStart + 1)

$metadata = @(Get-LinesBetween -StartIndex $metadataStart -EndIndex $goalStart -SectionName 'Metadata')
$acceptance = @(Get-LinesBetween -StartIndex $acceptanceStart -EndIndex $verificationCommandsStart -SectionName 'Acceptance Criteria')
$review = @(Get-LinesBetween -StartIndex $reviewStart -EndIndex $completionStart -SectionName 'Review Result')
if ($completionStart -ge ($lines.Count - 1)) { throw 'Completion Evidence section is empty' }
$completion = [System.Collections.Generic.List[string]]::new()
for ($index = $completionStart + 1; $index -lt $lines.Count; $index++) {
  [void]$completion.Add($lines[$index])
}

Assert-SingleExactField -Block $metadata -FieldPattern '^- Status:' -Expected '- Status: DONE' -SectionName 'Metadata'
Assert-SingleExactField -Block $metadata -FieldPattern '^- Completed:' -Expected '- Completed: 2026-09-20' -SectionName 'Metadata'
Assert-SingleExactField -Block $acceptance -FieldPattern '^- \[[ xX]\] AC-8\b' -Expected '- [x] AC-8 — Documentation checks and independent review pass.' -SectionName 'Acceptance Criteria'
Assert-SingleExactField -Block $review -FieldPattern '^- Result:' -Expected '- Result: APPROVED' -SectionName 'Review Result'

$canonicalCompletionFields = @(
  '- Final status: DONE',
  '- Acceptance criteria: all satisfied',
  '- Focused verification: PASS',
  '- Regression verification: PASS',
  '- Static and diff verification: PASS',
  '- Review: APPROVED',
  '- Commit: not required by task scope',
  '- Completed: 2026-09-20'
)
foreach ($expected in $canonicalCompletionFields) {
  Assert-SingleExactLine -Block $completion -Expected $expected -SectionName 'Completion Evidence'
}

'Final authoritative-field verification: PASS'
```

Observed output:

```text
Final authoritative-field verification: PASS
```

## Review Result

- Result: APPROVED
- Findings: none; all previous findings are addressed

## Completion Evidence

- Final status: DONE
- Acceptance criteria: all satisfied
- Focused verification: PASS
- Regression verification: PASS
- Static and diff verification: PASS
- Review: APPROVED
- Commit: not required by task scope
- Completed: 2026-09-20
- All acceptance criteria, AC-1 through AC-8, passed.
- Focused workflow verification passed.
- Cross-document regression verification passed.
- Static and diff verification passed, including `git diff --check`.
- Protected `docs/plans/current-task.md` SHA-256 verification passed with `636602A28EE8E1877EBCF450140BBAC8C14F66D9A14C7A01C0C7161EC36D43ED`.
- Independent re-review result: `APPROVED`; no blocking finding remains and all previous findings are addressed.
- Commit, push, and pull request creation were not performed, per task scope and authorization.
