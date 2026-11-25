# Verified Integration Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Repository Model A and the user's single-native-agent preference override extra task identifiers/reviewer agents; main performs independent review. Only `docs/tasks/adopt-verified-integration.md` is an executable task and execution ledger.

**Goal:** Adopt verified integration `2abdabe` into `feat/figma-ui-v2` with exact preservation of its dirty historical-plan draft and independent adopted-tree verification.

**Architecture:** No architecture change. Preserve current Figma runtime and backend contracts through a normal local ancestry-preserving merge; isolate the existing document draft into its own approved recoverable checkpoint before resolving that document to the integration version. Do not use unknown local files as build inputs or commit content.

**Tech Stack:** Existing Git/PowerShell, FastAPI/PostgreSQL/Alembic, React/TypeScript/Vite/npm/plain CSS and Playwright; no installations/upgrades beyond the existing lockfile.

**Spec:** User-approved adoption brief, 2026-10-16, and `docs/tasks/adopt-verified-integration.md` for the exact ownership, policy, constraints, ACs and verification commands. Retained runtime behavior/evidence is defined by dependency `docs/tasks/integrate-phase1-backend-with-figma-ui.md` at verified `2abdabe`. Executable task identifier: `adopt-verified-integration`.

## Global Constraints

- One executable task: `docs/tasks/adopt-verified-integration.md`; only it receives new execution/review history.
- Local only: no push, PR, deployment, rebase/amend/reset, automatic stash, deletion or source-data migration.
- Preserve exact dirty document bytes and all unknown/local files; no secret values in logs or commits.
- Exclude `.env`, `.docx`, local editor configuration, reports, generated artifacts/dependencies/environments and unknown files.
- No feature, framework, package-manager, auth/RBAC/API or Figma behavior changes.
- Use exactly one existing native implementer for required file corrections, with main independent review; maximum three correction rounds.
- Approval of this preservation policy is required before a draft checkpoint or merge. User approval of the general goal is not permission to choose historical document contents silently.

## Review Focus

- Dirty plan changes after preflight: compare its exact recorded blob before checkpoint; stop on drift rather than checkpoint new unreviewed content.
- Unknown/untracked incoming-path overlaps: check exact path sets; do not stage, overwrite or read unrelated legacy task/report content.
- Historical document conflict mistaken for runtime regression: preserve draft in ancestry and choose only approved current-document resolution; runtime must match verified integration.
- Development environment or PostgreSQL accidentally selected for write tests: validate exact container, database suffix, loopback port, Compose project/volume and E2E origin before execution.
- Green test counts mistaken for complete adoption: require actual ancestry, recoverable draft, runtime equivalence, fresh real isolated E2E, exclusion checks and independent AC review as separate gates.

## File responsibilities

Create only this plan and `docs/tasks/adopt-verified-integration.md` for new task authority. The existing `docs/superpowers/plans/2026-09-04-phase-1-production-ready.md` is the sole pre-existing tracked draft requiring preservation and approved conflict resolution. Existing backend/frontend/config/test files travel through the already verified integration merge, not new feature implementation. All other historical task/state files remain unchanged from their merge parent. Unknown files remain untouched.

## Single milestone: preserve, adopt, verify and review

**Consumes:** target HEAD `1cba4cb`, integration HEAD `2abdabe`, dirty plan blob `a01e78aecfc230e2d31d98b1f1624b8d3e31453b`, incoming plan blob `4e4ed99cd50872e42fdcfab8f27d8091386b2587`, dependency DONE/APPROVED evidence.

**Produces:** ancestry-preserving adopted target, a dedicated recovery commit for the original draft, actual fresh verification and the sole task's accurate completion record. No new runtime interfaces.

- [ ] Obtain explicit approval for the detailed plan: checkpoint the exact existing draft separately, then use the integration's historical-plan content as the current document while preserving the original draft in commit history. If policy differs, update READY baseline first.
- [ ] Recheck branch/HEAD/source immutability, dependency DONE/APPROVED, exact dirty-plan blob and incoming-path/untracked overlaps. Record READY -> IN_PROGRESS and freeze the selected task baseline only after authority/dependencies/policy pass.
- [ ] Save a scoped local task/plan documentation checkpoint after diff/exclusion/secret checks. Separately checkpoint only the exact reviewed dirty historical plan with a subject describing preservation, not a newly implemented feature. Record its hash and prove its plan blob matches the original. Never stage all files or unknown drafts.
- [ ] Run a normal non-squashing, non-rewriting local merge of `2abdabe` into target. If Git reports the expected historical-plan conflict, use the integration version only after the draft recovery checkpoint has been proven. Preserve current task/plan. Stop on unexpected source/config conflicts or file drift; no blanket resolution.
- [ ] Verify actual target ancestry includes source integration plus original frontend/backend; current historical-plan blob matches the approved integration version and original draft remains recoverable. Prove runtime/config/lockfile equivalence against `2abdabe`; inspect any delta. No product changes are expected, so TDD production-code changes are not applicable unless a separately approved defect changes scope.
- [ ] Record IN_PROGRESS -> VERIFYING. Run the exact full backend/frontend/lint/type/build/audit commands in the task against the adopted checkout using guarded disposable resources. Do not copy the dependency's passing counts or silently skip PostgreSQL gates. On failure, return to IN_PROGRESS before any permitted correction.
- [ ] Validate isolated production runtime equivalence or rebuild adopted sources, then run fresh eight-scenario real E2E. Record actual statuses/counts and UI/API coverage boundaries; no fake success, auth capture or development writes. Browser verification unavailable means NOT VERIFIED where mandatory.
- [ ] Enter REVIEWING. Main independently reviews full adoption/conflict-resolution diff, all AC evidence, source preservation and bounded local-history secret scan. Delegate necessary in-scope file corrections only to the single native implementer after REVIEWING -> IN_PROGRESS; at most three rounds. Unexpected feature work needs a new user decision.
- [ ] Inspect status/unstaged/staged diffs and exact allowlist before every local commit. Record final hashes/subjects, changed files, recovery reference, actual target status, excluded unknown files and limitations only in the selected task. Mark DONE/APPROVED only after every AC has evidence; no historical phase completion changes or push.

## Plan self-review

All seven ACs map to explicit steps; preservation policy is intentionally unapproved, not inferred. Tests validate adopted runtime while Git/blob assertions validate preservation and ancestry. Task creation is approved; implementation waits for detailed-plan/policy approval. Existing single-agent execution method is retained, no new architecture or second milestone is introduced.
