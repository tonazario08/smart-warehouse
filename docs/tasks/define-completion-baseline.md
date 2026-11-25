# define-completion-baseline — Chốt phạm vi và điều kiện hoàn thiện dự án

## Metadata

- Status: DONE
- Milestone: M1, exactly one executable task
- Plan: embedded single-milestone plan below, identifier `define-completion-baseline`
- Specification: human-approved twelve-milestone roadmap in this conversation, 2026-10-16; supplied thesis outline identified below
- Depends on: docs/tasks/fix-compose-seed-ci.md
- Created: 2026-10-16
- Started: 2026-10-16
- Completed: 2026-10-16

## Goal

Lưu baseline có truy vết cho phần còn lại của Smart Warehouse: ma trận yêu cầu, phạm vi từng milestone, điều kiện dữ liệu/nghiên cứu, khả năng tài nguyên và các cổng nghiệm thu. Không triển khai tính năng ứng dụng trong task này.

## Context

- Human requested a completion plan, delegated proposal choices with `tự đề xuất`, then approved the presented roadmap and creation of the unique path `docs/tasks/define-completion-baseline.md` by replying `duyệt`. This is the explicit creation exception for that previously nonexistent path. It does not authorize creating/executing the other eleven tasks or publishing Git changes.
- Approved deliverables for M1 include a stable specification and linked roadmap; only this selected task is the execution/state/evidence ledger. Output specs/plans contain requirements/instructions, not task progress or completion states.
- Code baseline: `feat/figma-ui-v2`, HEAD `d8b3fa82b4b77cba5a3faed49738bf5ebe5c46d6`. Dependency `docs/tasks/fix-compose-seed-ci.md` is DONE/APPROVED. Its verification is historical evidence, not a new M1 test run.
- Supplied outline: `C:/Users/TQUOCTOAN/Downloads/V1_De_cuong_DACN_Truong_Quoc_Toan.docx`; read-only SHA256 observed 2026-10-16: `E1683DB5909F21FA7199026C82E9CBB76F605341656D8C4AE84FB8456BBDA9C9`. The approved roadmap uses the full expected-results scope, including extensions, rather than silently narrowing it to the introductory research focus. Do not copy the DOCX or personal data into Git.
- Existing unrelated untracked editor/report/spec/testing files, the personal DOCX and LegacyProductsPage are preserved and excluded. No legacy shared task under docs/plans/ is read or used for routing.

## In Scope

- Read approved roadmap, declared dependency, actual tracked API/router/model/test structure and stable configuration to distinguish implemented API, active UI, schema-only support and missing capability.
- Create only these stable outputs: `docs/superpowers/specs/2026-10-16-project-completion-design.md` and `docs/superpowers/plans/2026-10-16-project-completion.md`; update only this task ledger for M1 history, evidence, review and completion.
- Record full requirement-to-milestone mapping and explicit dependency task paths. Maintain one executable task per milestone and strict single-task execution.
- Define dataset admission, provenance, privacy, demand semantics, temporal evaluation, replenishment inputs, map/LLM prerequisites and evidence levels. Separate demo readiness from research validity and benchmark availability.
- Perform read-only resource checks and tracked dataset-candidate inventory. Missing datasets/rights/benchmarks remain NOT VERIFIED; no claim that all personal storage has been searched or that model execution is impossible.
- Self-review consistency and document-specific verification, then hand off the baseline for human review. M1 is documentation only; downstream code implementation remains gated.

## Out of Scope

- Application/frontend/backend/API/auth/RBAC/Compose/dependency/test changes, model execution/training, migrations, browser writes, dataset downloads/imports, DB access/writes, software installation or paid/cloud service use.
- Creating the other proposed executable tasks, starting M2 or another milestone, re-running the DONE dependency, editing historical tasks/plans or using unselected files as routing authority.
- Reading .env/secrets, enumerating unrelated Downloads/report content, copying the outline, modifying unknown files or clearing Docker/cache/volume/worktree data.
- Stage, commit, push, PR, deploy, merge or history rewrite without separate explicit authorization.

## Acceptance Criteria

- [x] AC-1 — Authority, exact HEAD, DONE dependency, source outline fingerprint and preserved-file exclusions are recorded; approved scope and author-proposed defaults are distinguished.
- [x] AC-2 — Stable specification maps every approved scope area to current code evidence, a single owning milestone and explicit acceptance evidence, without treating model/table/component presence as complete functionality.
- [x] AC-3 — Roadmap contains exactly twelve distinct milestone/task paths, explicit acyclic dependency paths and staged gates; it preserves the approved order/scope and is not a multi-task execution authorization.
- [x] AC-4 — Dataset/lead-time/cost/privacy and LLM/map prerequisites have explicit admission criteria and observed readiness. Unknowns remain NOT VERIFIED; synthetic data is never evidence of operational/research effectiveness.
- [x] AC-5 — Roadmap defines concrete output/file boundaries and regression/security/browser/research checks per milestone; existing API/auth/token behavior is preserved, with no new framework or autonomous inventory action.
- [x] AC-6 — Document checks pass: required references and real source paths resolve, all proposed dependencies refer to mapped milestones, no duplicate task identifiers/cycles/conflict markers/trailing whitespace, Git HEAD/index and existing files unchanged.
- [x] AC-7 — Main self-review and human review handoff are recorded. Keep REVIEWING until the human approves this written baseline; do not label missing data/model/browser evidence verified or start another task.

## Embedded Implementation Plan

Single executable milestone `define-completion-baseline`; internal steps are not additional executable tasks.

1. Validate unique creation authority, baseline/dependency and three-file allowlist; record READY -> IN_PROGRESS and freeze Goal, Context, In Scope, Out of Scope, Acceptance Criteria and Verification Commands before authoring the stable outputs.
2. Create the stable specification: full requirement matrix, unchanged runtime contracts, recommended defaults, dataset/resource admission decisions, security boundaries and research acceptance gates. Separate observed facts, proposals and NOT VERIFIED prerequisites.
3. Create the linked roadmap: exactly the approved twelve mapped tasks with explicit dependency paths, per-milestone file/interface boundaries, failure-oriented acceptance checks and common verification/handoff instructions. M2 onward require their own detailed approved plans before implementation.
4. Self-review coverage, names/links/dependencies, negative input classes and proportionality. Record VERIFYING before document checks; a required content correction after that must first record VERIFYING -> IN_PROGRESS.
5. Verify only the three new Markdown files, preserved baseline/index/unknown files and referenced code/CI. Do not rerun backend/frontend suites solely for Markdown and claim new runtime evidence.
6. Record VERIFYING -> REVIEWING and hand off the written baseline. Human review acceptance is required before REVIEWING -> DONE; any required correction uses REVIEWING -> IN_PROGRESS. No other milestone or Git publication starts automatically.

## Verification Commands

- Preflight/final: `git status --short`; `git rev-parse HEAD`; `git diff`; `git diff --staged`; `git diff --check`; exact new-file allowlist and no tracked/index drift. Scan the new untracked Markdown directly because git diff --check alone does not inspect untracked files.
- Read-only inventory: `git ls-files app client/src client/e2e tests alembic pyproject.toml`; `git ls-files '*.csv' '*.parquet' '*.ipynb' '*.pkl' '*.joblib'`. No unrelated file/legacy-task scan.
- Resource evidence: read-only Win32_OperatingSystem memory, Win32_Processor and Win32_VideoController names; if available `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader`. No benchmark, driver/tool install or exposure of machine/user identifiers.
- Document checks: in-memory PowerShell assertions over the three explicit files for headings, seven ACs, twelve unique milestone task paths, exact dependency mapping/no cycles, real source references, Markdown conflict markers and trailing whitespace. Proposed future paths are explicitly marked proposed, not required to exist.
- Historical CI lookup only: `gh run view 38878419100 --repo tonazario08/smart-warehouse --json status,conclusion,headSha,url,jobs`. Match the exact baseline SHA and report actual results; do not dispatch/rerun workflows or print raw credentials/logs.

## Progress Log

### 2026-10-16 — Unique M1 creation approved

- Created this sole executable task after explicit approval of the exact path. The other two new files are named M1 documentation outputs, not separate tasks. Existing HEAD/index/tracked code are unchanged; the proposed files did not exist at preflight.
- User-approved execution preference is retained: one reusable native implementer for future code, main-agent review, no parallel executable tasks. M1 authoring/self-review is documentation-only; no native code work or additional agent is needed.

### 2026-10-16 — READY -> IN_PROGRESS

- Validated embedded plan identifier, full approved-roadmap authority, exact baseline, dependency DONE/APPROVED, source fingerprint and three-file output scope. Freeze Goal, Context, In Scope, Out of Scope, Acceptance Criteria and Verification Commands now. No existing task/plan/spec is edited.
- Read-only observations: Windows 11, Intel Core i5-11400H (six physical/twelve logical cores), 15.7 GiB visible RAM with 3.4 GiB free at this instant; NVIDIA GeForce RTX 2050, nvidia-smi reports 4096 MiB. These are capacity observations, not successful Llama inference or a permanent free-memory guarantee. No inference package/model/license acceptance/benchmark is available as verified evidence here.
- Tracked candidate inventory for CSV/parquet/notebook/pickle/joblib returned zero. No qualified research dataset, ownership/license, lead-time series, carrying/ordering costs or demand-observation coverage has been supplied/admitted in this task. This does not establish absence outside the scoped inventory. Seed/demo and old automated test records are not a research dataset.

### 2026-10-16 — Stable outputs authored and self-reviewed

- Created exactly the two declared new stable outputs, with full requirement coverage and twelve uniquely mapped milestones. M2-M12 remain proposals requiring their own task authority and detailed contracts; no other executable task was created. Preserved current architecture/API/auth/token/RBAC behavior and human-only inventory action boundaries.
- Main performed the writing-plans self-review for requirement coverage, file/interface boundaries, negative cases, dependency/name consistency and proportionality. Chose a master roadmap plus later scoped detailed plans rather than inventing final API/model signatures before dataset/security/UI contracts exist. This is a documented planning boundary, not an implementation-ready claim for later milestones.
- Explicit distinctions include active UI versus legacy components/API-only tests, purchase requests versus supplier on-order supply, outbound sales versus transfer/test/censored demand, software correctness versus held-out research effectiveness, and observed hardware versus unbenchmarked inference. No required drafting finding remains before document checks.

### 2026-10-16 — IN_PROGRESS -> VERIFYING

- Documentation is frozen for verification. Run the declared reference/constraint/milestone-graph/whitespace/allowlist checks and historical CI lookup now. No new backend test, frontend build, browser/Figma comparison or model benchmark is performed or claimed by this Markdown-only task.

### 2026-10-16 — VERIFYING -> REVIEWING

- In-memory PowerShell document checks returned exit 0: all three outputs, seven ACs, exactly twelve unique milestone/task identities, exact approved acyclic dependency edges, identical spec/plan Global Constraints, fifteen existing code/dependency references resolved, no trailing whitespace/conflict markers, dependency DONE/APPROVED and unchanged HEAD/index/tracked files/LegacyProductsPage hash. Proposed future paths are not mistaken for existing tasks.
- Read-only Quality lookup confirmed historical run 38878419100 is completed success at exact baseline `d8b3fa82b4b77cba5a3faed49738bf5ebe5c46d6`, all backend/frontend/E2E jobs success. This is provenance only, not a new execution or verification of future features.
- AC-1 through AC-6 now have M1 documentation evidence. AC-7 remains pending human review of the new written baseline; hand off both stable outputs and this task, keep REVIEWING, do not mark DONE or start M2. Human approval may accept the accurately documented NOT VERIFIED prerequisites without asserting those prerequisites are ready.

### 2026-10-16 — REVIEWING -> DONE after human baseline approval

- Approver: human user, replying `duyệt` to the explicit review handoff linking this M1 task, stable specification and twelve-milestone plan and asking approval to close M1. This is approval of the written baseline and its documented assumptions/limits, not authorization for M2, Git publication, model downloads or changed security grants.
- Main reran document-specific checks before closure: all three outputs, seven ACs, exact twelve milestone identities/dependency edges, acyclic graph, matching global constraints, fifteen existing references, DONE dependency, clean tracked/index state and unchanged excluded LegacyProductsPage hash; exit 0. No new backend/frontend/browser/model run is claimed.
- Approved stable specification SHA256: `28339403DB1F3812396E2F7DE5A767072FB73FA54A82273DAE4EF1613EF03B17`; approved plan SHA256: `0563304A518493AA8E27C90950DDD6F71288E30027BD09A1D8541CD8C6D92E5F`. These documents are unchanged by closure. Only this task ledger is updated; AC-7 is now verified and all seven M1 documentation criteria are satisfied.
- Dataset admission/rights, lead-time/cost inputs, spatial/corpus admission and actual Llama inference feasibility remain NOT VERIFIED, as approved and explicitly gated for later milestones. Completing the baseline does not complete those capabilities. No source/dependency edit, other task creation, stage, commit, push or next-milestone execution occurred.

## Verification Evidence

- Document-specific checks: PASS, exit 0; three explicit new files, seven ACs, twelve unique mapped task paths, exact acyclic dependencies, identical ten global constraints, fifteen existing source/dependency references, whitespace/conflict checks and preservation checks.
- Read-only resource/dataset checks are recorded above. Dataset rights/fitness, cost/lead-time inputs, map/corpus admission and Llama inference benchmark remain NOT VERIFIED, not silently counted as delivered functionality.
- Historical hosted CI: https://github.com/tonazario08/smart-warehouse/actions/runs/38878419100, success at baseline HEAD, all three jobs success. No new backend/frontend suite, browser/Figma run or model benchmark was performed for these Markdown changes.
- Exact M1 new files: docs/tasks/define-completion-baseline.md; docs/superpowers/specs/2026-10-16-project-completion-design.md; docs/superpowers/plans/2026-10-16-project-completion.md. No existing tracked changes or staged changes; unrelated untracked files retained, no Git publication.
- Closure verification rerun: PASS, exit 0; human written-baseline approval received and recorded above. AC-7 verified only after that approval. Stable-output fingerprints are recorded for future explicitly authorized tasks.

## Review Result

- Main drafting/self-review: no required finding; coverage, assumptions, boundaries, dependencies and failure-oriented checks verified against the approved roadmap.
- Human written-baseline review: APPROVED on 2026-10-16 by explicit `duyệt` following the linked written-baseline handoff. This is a separate approval from the earlier chat-roadmap/creation approval. The requested single-native-code/main-review method is preserved for future implementation, without dispatching code work in M1.

## Completion Evidence

- DONE / APPROVED. All seven documentation ACs have verification/review evidence; canonical READY -> IN_PROGRESS -> VERIFYING -> REVIEWING -> DONE history is retained above. Scope is the completed planning baseline, not completed application/research features.
- Exact three M1 files remain local/untracked and unpublished; no stage/commit/push or source/dependency change. HEAD remains d8b3fa82b4b77cba5a3faed49738bf5ebe5c46d6, index unchanged; unrelated untracked files are preserved.
- No subsequent milestone is started. M2 path docs/tasks/complete-core-management-ui.md remains a proposal requiring its own explicit creation/selection authority and detailed plan/design review before implementation. Dataset/model prerequisites remain gated as NOT VERIFIED.
