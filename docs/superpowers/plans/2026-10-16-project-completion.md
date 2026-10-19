# Smart Warehouse Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (with the user's single reusable native implementer and main review) or superpowers:executing-plans when implementation is explicitly authorized. Instructions below describe planned work, not actual progress; the selected task file alone owns state/evidence/completion.

**Goal:** Complete the approved thesis scope without weakening the working warehouse platform or claiming research effectiveness from software tests.

**Architecture:** Retain the layered modular FastAPI/PostgreSQL application and current React router/layout/shared UI. Add domain modules through reviewed compatible contracts; execute model preparation/training/evaluation outside HTTP requests. AI stays advisory, with role-authorized read tools and versioned data/model/prediction provenance.

**Tech Stack:** Python >=3.12, FastAPI, PostgreSQL, SQLAlchemy, Alembic, React/TypeScript/Vite, npm and plain CSS; add reviewed ML/GIS/LLM dependencies only inside the milestone that needs them, not during M1.

**Spec:** docs/superpowers/specs/2026-10-16-project-completion-design.md

## Plan authority and execution boundary

The human approved the high-level twelve-milestone roadmap on 2026-10-16 and creation of `docs/tasks/define-completion-baseline.md`. This plan is M1's stable roadmap output, not twelve concurrent execution instructions. Only M1 has been created/selected. Other task paths below are proposals, not existing/routable tasks; never discover a next task by scanning statuses or the row order.

M1's executable documentation steps and actual evidence are in its embedded plan/ledger. Each M2-M12 task must be explicitly selected/authorized, exist, reference this stable design and a milestone-specific detailed implementation plan, validate DONE dependencies and freeze its baseline before code. Those detailed plans supply exact schemas/signatures/status codes, per-file create/modify/test lists and RED/GREEN cases; the directory boundaries below do not grant authority to invent unsettled APIs now.

## Global Constraints

- Preserve Python >=3.12, FastAPI, PostgreSQL, SQLAlchemy, Alembic and the current layered router/service/repository architecture.
- Preserve React/TypeScript/Vite, npm, plain CSS and the existing Inter/design-token/shared-component foundation; do not add a UI framework or change package manager.
- Preserve existing API contracts, POST /api/v1/auth/login, GET /api/v1/auth/me, smart-warehouse-token, logout and invalid-auth cleanup. New contracts are additive and explicitly reviewed.
- Backend remains the authority for RBAC; frontend permissions control visibility only. Do not silently widen existing grants or introduce unreviewed stock-publication rules.
- Visible UI text is Vietnamese; code identifiers remain English. Reuse shared React components and styles.
- AI is advisory only: no autonomous purchasing, outbound, transfer or inventory correction. No arbitrary model-generated SQL or shared-admin authorization bypass.
- Distinguish real data, synthetic fixtures and demo records. Do not replace live API integrations with mocks or use synthetic performance as real-world research evidence.
- Protect credentials, customer data and unknown local files. Do not read .env, commit datasets/model binaries/secrets, reset volumes or mutate development/demo data for verification.
- Execute one explicitly selected docs/tasks/ task at a time, one executable task per milestone; dependencies must be explicit task paths and DONE before execution.
- No automatic stage, commit, push, PR, merge, deployment or history rewrite. Existing milestones are not reopened by routing to this design.

## Review Focus

| Failure/input class | Expected result | Owning acceptance checks |
| --- | --- | --- |
| Missing, future-derived or stockout-censored data | Unknown/limited states and no leakage or false research claim | M5 data semantics; M6 temporal leakage; M7 calibration/policy simulation; M8 held-out SKU |
| Repeated/concurrent stock or fulfillment requests | Exactly-once linked effects, conservation and rollback without overselling | M3 replay/concurrency/failure injection; M4 fulfillment replay/ownership |
| Client ID guessing or retrieval prompt injection | Backend denies cross-user/private results, including LLM tool/retrieval paths | M2 route/API matrix; M4 IDOR; M11 adversarial corpus/tool tests |
| Disconnected road graph, missing coordinates or unavailable inference | Honest unavailable/fallback state, no fabricated routes/answers | M10 graph/stock cases; M11 timeout/unavailable/no-evidence cases |
| Existing API/auth consumers or unapproved UI changes | Backward compatibility, same session behavior and real visual approval | M2 active-app browser tests; M3/M4 contract regression; M12 end-to-end/design gate |

## Milestone task mapping

The M1 dependency is an existing DONE task. All other dependencies below are explicit proposed task paths, not shorthand state-routing instructions. Default execution order is M1 to M12; a dependency edge does not authorize parallel execution.

| Milestone | Unique executable task path | Depends on |
| --- | --- | --- |
| M1 | docs/tasks/define-completion-baseline.md | docs/tasks/fix-compose-seed-ci.md |
| M2 | docs/tasks/complete-core-management-ui.md | docs/tasks/define-completion-baseline.md |
| M3 | docs/tasks/implement-stock-transfers.md | docs/tasks/define-completion-baseline.md |
| M4 | docs/tasks/implement-b2b-purchase-requests.md | docs/tasks/complete-core-management-ui.md; docs/tasks/implement-stock-transfers.md |
| M5 | docs/tasks/build-demand-data-pipeline.md | docs/tasks/define-completion-baseline.md; docs/tasks/implement-stock-transfers.md; docs/tasks/implement-b2b-purchase-requests.md |
| M6 | docs/tasks/implement-demand-forecasting.md | docs/tasks/build-demand-data-pipeline.md |
| M7 | docs/tasks/implement-replenishment-policy.md | docs/tasks/implement-demand-forecasting.md |
| M8 | docs/tasks/implement-product-cold-start.md | docs/tasks/build-demand-data-pipeline.md; docs/tasks/implement-demand-forecasting.md |
| M9 | docs/tasks/implement-anomaly-explanations.md | docs/tasks/build-demand-data-pipeline.md |
| M10 | docs/tasks/implement-warehouse-gis.md | docs/tasks/implement-stock-transfers.md; docs/tasks/implement-b2b-purchase-requests.md; docs/tasks/implement-replenishment-policy.md |
| M11 | docs/tasks/implement-rbac-ai-assistant.md | docs/tasks/implement-b2b-purchase-requests.md; docs/tasks/implement-replenishment-policy.md; docs/tasks/implement-product-cold-start.md; docs/tasks/implement-anomaly-explanations.md; docs/tasks/implement-warehouse-gis.md |
| M12 | docs/tasks/validate-project-completion.md | docs/tasks/complete-core-management-ui.md; docs/tasks/implement-stock-transfers.md; docs/tasks/implement-b2b-purchase-requests.md; docs/tasks/build-demand-data-pipeline.md; docs/tasks/implement-demand-forecasting.md; docs/tasks/implement-replenishment-policy.md; docs/tasks/implement-product-cold-start.md; docs/tasks/implement-anomaly-explanations.md; docs/tasks/implement-warehouse-gis.md; docs/tasks/implement-rbac-ai-assistant.md |

## File and interface boundaries

Existing integration points are app/main.py, app/models/domain.py, app/auth/dependencies.py, app/inventory/service.py, app/inventory/repository.py, client/src/App.tsx, client/src/app/router.tsx, client/src/api.ts, client/src/shared/layout/Sidebar.tsx and existing shared UI/styles. Modify only those explicitly named in the later selected task; a master-plan mention alone is not a source-edit allowlist.

Proposed new module directories are app/transfers/, app/purchase_requests/, app/analytics/, app/forecasting/, app/replenishment/, app/cold_start/, app/anomalies/, app/gis/ and app/assistant/, with corresponding client/src/features/ UI directories. They do not exist by virtue of being listed. Keep concerns within their modules; app/main.py registers routers, App.tsx stays composition-only. Migrations are additive new files under alembic/versions/, never rewrites of applied migrations.

Shared contracts to freeze in each owning detailed plan: movement purpose/provenance and transfer linkage (M3); request ownership/transitions/fulfillment linkage (M4); dataset manifest and daily observation semantics (M5); forecast run schema with cutoff/horizon/model/data version and predictions (M6); policy run parameters/uncertainty/inputs/output rationale (M7); cold-start provenance (M8); alert/explanation schema (M9); graph snapshot/ranking/route response (M10); authorized tool input/output with freshness/source fields (M11). Later plans consume these exact approved contracts rather than redefining them.

## M1 — Define completion baseline

Files created only: docs/tasks/define-completion-baseline.md, docs/superpowers/specs/2026-10-16-project-completion-design.md and this plan. No source, test, package or old document edit. Consumes the approved roadmap, supplied-outline fingerprint, code baseline and declared CI-task evidence. Produces the requirement matrix, scope/contract guardrails, data/resource admission gates and exact milestone map.

Acceptance is documentation coverage, factual provenance and human review, not successful model training or all future prerequisites becoming available. Missing datasets/rights/resources are explicitly NOT VERIFIED. M1 may be approved with those limitations documented; downstream research cannot bypass them.

Document checks: resolve the three outputs and declared existing references, validate twelve unique mapped task paths and acyclic explicit dependencies, compare global constraints across spec/plan, reject conflict markers/trailing whitespace, confirm no tracked/index change and preserve unselected files. No new backend/frontend/browser/model result is asserted for Markdown-only work.

## M2 — Complete active management UI

Reuse existing users/categories/suppliers/audit/transactions modules in client/src/features/ and real APIs. Proposed modifications are the active router, sidebar/permissions and the relevant feature pages/styles/tests; no wholesale switch to the competing legacy AuthProvider/AppShell/Providers tree. Exact integration adapters are determined by its reviewed detailed plan.

Consumes existing API/RBAC/session contracts; produces active Vietnamese management destinations and validated real-user workflows. Preserve backend-granted actions rather than extending admin creation/permissions to satisfy an invented UI.

Acceptance cases: authorized versus direct forbidden URLs/actions for all three roles; unauthorized API rejection; preserved login/hydration/logout/invalid-token behavior; management form validation/conflict handling; loading/empty/error; keyboard/focus and responsive layout; approved new-screen design plus actual browser evidence. No Figma claim for an undefined frame. Password recovery is separate scope/design, not silently activated.

## M3 — Atomic stock transfers

Propose app/transfers/ and client/src/features/transfers/, additive models/migration, explicit inventory integration and focused PostgreSQL/E2E cases. Preserve existing inbound/outbound request/response shapes and consumer handling.

Consumes stock identities, server permissions and current atomic write services; produces linked transfer provenance for both warehouses and movement-purpose semantics used by M5/M10. Specify whether a transfer is immediate or staged before freezing its schema; do not accidentally claim in-transit inventory for an immediate atomic model.

Acceptance cases: positive quantity, distinct existing source/destination, sufficient stock, paired effects/history, total conservation, deterministic lock ordering, first destination-stock creation races, rollback after each failure point, duplicate/replayed idempotency key and concurrent conflicting transfers/outbounds. Declare key ownership/payload conflict handling and deadlock retry behavior in the detailed contract. Existing tests continue to pass.

## M4 — B2B purchase requests

Reuse app/models/domain.py PurchaseRequest with reviewed additive migration; add app/purchase_requests/ and client/src/features/purchaseRequests/, ownership/role dependencies, active routes and real flow tests.

Consumes live products/warehouses/stock and M3 inventory provenance; produces customer-owned request history and exactly-once outbound fulfillment linkage. Freeze PENDING/APPROVED/REJECTED/FULFILLED transition and conflict semantics against the existing enum; customer requests are not supplier purchase orders. An approved request alone does not reserve or decrement stock unless an explicit reservation design is approved.

Acceptance cases: owner-only list/detail, cross-client IDOR, forbidden transitions/roles, invalid stock publication access, payload validation and competing/replayed fulfillment. Approval without fulfillment leaves stock unchanged; fulfillment uses the transaction-safe outbound boundary. Snapshot/public-stock policy must be explicitly approved, not inferred from frontend visibility.

## M5 — Demand data pipeline

Propose app/analytics/ preparation/validation/export interfaces, privacy-safe fixture tests and ignored/versioned-manifest artifact storage. Do not commit admitted raw datasets or silently add import routes to production.

Consumes M3 purpose/linkage and M4 fulfillment semantics; produces a dataset manifest plus daily SKU/warehouse observations with source/cutoff/timezone/units, missingness and stockout-censoring flags. Existing demo records remain a separate dataset class.

Acceptance cases: duplicate imports, unknown SKU/warehouse, invalid/nonpositive quantities, timezone/day boundaries, missing observation versus observed zero, transfers/returns/adjustments/test exclusions, inactive/new SKU periods, leakage-causing dates and insufficient history. Re-running the same source yields the same version/hash/results or a reviewed update. Admission requires rights, provenance and reviewed quality; no numerical minimum history/horizon is invented before seeing data. Fixture-only implementation does not satisfy research-data acceptance.

## M6 — Forecasting and temporal evaluation

Propose app/forecasting/ CLI/service/read API/persistence, client/src/features/forecasting/, frozen ML dependencies and dataset/run fixtures. Training is not an HTTP-request side effect.

Consumes M5's admitted manifest/observations; produces versioned forecast runs keyed by data/model version, SKU/warehouse, training cutoff, horizon and generation time. Baselines and XGBoost use identical temporal splits and declared target semantics. No final-test tuning or random row split substitutes for out-of-time evaluation.

Acceptance cases: future-feature/target leakage, preprocessing fit outside training, deterministic reproducibility/config/seed, all-zero/short series, nonnegative prediction policy, missing/stale/incompatible artifacts and failed-job UI/API states. Report MAE plus agreed zero-safe metrics and per-series/aggregate results; undefined denominators remain explicit. Do not require XGBoost to win; explain observed results/limitations and preserve the final holdout. Real dataset validation and operational forecast UI are distinct ACs.

## M7 — Uncertainty and replenishment

Propose app/replenishment/ and client/src/features/replenishment/, uncertainty/policy-run persistence and formula/simulation tests. Consume versioned forecasts and reviewed lead-time/cost/on-order inputs; produce Safety Stock, ROP, EOQ or an explicit unavailable/scenario result with rationale.

Freeze nominal interval/service targets and calibration protocol before final evaluation. Do not derive inventory position from customer purchase requests as if they were inbound supply. If the supplier-order pipeline is absent, document the resulting availability restriction or design its minimal additive input inside the task before implementation.

Acceptance cases: missing/zero/invalid ordering/holding costs, mixed currency/time units, missing/stochastic lead time, stale forecast, pending supply/allocations, all-zero demand and insufficient calibration data. Test formula boundaries and held-out interval coverage. Compare baseline/proposed inventory policies under identical initial state, warm-up, lead-time assumptions and evaluation periods; report shortages/service, average inventory and only supported costs. No future realized demand is used for historical decisions; no automatic order is placed.

## M8 — Product cold-start

Propose app/cold_start/ and client/src/features/forecasting/ cold-start presentation or a focused new feature directory as approved in its detailed plan. Consume M5 metadata/history and M6 run contracts; produce cluster assignment, reference-product provenance and clearly labeled initial forecasts.

Acceptance cases: held-out SKU evaluation with temporal cutoff, categorical encoding/scaling fitted only on training products, missing price/weight/category/supplier, insufficient/completely empty reference cluster and reproducible assignment. Document fallback and reduced confidence. Never borrow the withheld product's future sales or treat cluster similarity as validated forecast accuracy.

## M9 — Explainable anomalies

Propose app/anomalies/ Isolation Forest scoring/explanation services, versioned alert persistence and client/src/features/anomalies/. Consume M5 validated movement features; produce reviewable alerts with model/input versions and SHAP-compatible feature attribution.

Acceptance cases: contamination/threshold selected outside final test, feature-order mismatch, constant/missing features, known curated normal/anomalous examples, injected anomalies explicitly labeled synthetic, reviewer feedback and unavailable explainer. Validate score/explanation consistency for the chosen library/model pipeline before promising compatibility. Explain attribution as model behavior, not causal truth; no stock is corrected automatically. No production precision/recall claim without qualified labels.

## M10 — GIS

Propose app/gis/ and client/src/features/gis/, geospatial/road snapshot adapters and graph/spatial tests. Consume coordinates, M3 transfer semantics, M4 fulfillment needs and M7 recommendations; produce stock-feasible warehouse ranking, real road routes and period-labeled heatmaps.

Acceptance cases: missing/out-of-range coordinates, disconnected directed graph, nearest warehouse without stock, multiple stock-feasible choices, stale road snapshot and unit/CRS mismatch. Compare A* path costs with a reference shortest-path oracle on controlled graphs; validate the heuristic for the chosen weights. Straight-line distance remains a ranking metric only if labeled, never presented as a road route. Preserve source/license/attribution and unavailable states.

## M11 — Authorized RAG assistant

Propose app/assistant/ retrieval/model/tool adapters and client/src/features/assistant/, role-labeled corpus ingestion and adversarial evaluation fixtures. Consume approved M4/M7/M8/M9/M10 read interfaces using the caller's current backend identity; produce grounded Vietnamese responses with source/freshness/limitation context.

Acceptance cases: document prompt injection, unauthorized/cross-client chunks, caller token invalidation, invented tool names/parameters, arbitrary-SQL requests, stale operational facts, empty retrieval, hallucinated references, tool timeout and model unavailability. Stock/request state comes from authorized live APIs; the RAG index is not operational truth. First release is read-only and refuses unsupported mutations. Admit corpus/model rights, select and benchmark an approved Llama execution strategy before claiming local capability; no unsolicited model download, license agreement or cloud transfer.

## M12 — Integrated acceptance and thesis evidence

Propose additions to existing tests/postgres/, client/e2e/, research-evaluation artifacts/manifests and a specifically authorized operations/report deliverable. Do not write unknown docs/report/ contents or personal DOCX files by convenience; choose exact new paths in its selected task first.

Consumes all completed module contracts/evidence; produces requirement-level acceptance, reproducible evaluation, a clearly labeled demo dataset, operations/backup-restore evidence and the thesis report. Validate all three roles, denied paths, real writes, browser refresh/session expiry, rollback/concurrency, job/data/model failure and reporting lineage. Record browser/Figma evidence separately from builds and research metrics separately from E2E counts.

Acceptance requires review of findings and known limits, no unresolved critical/high defect within agreed scope, exact CI commit/run association and successful safe restoration exercise on disposable resources. Research results may be negative; reproducibility and honest conclusions are mandatory. Do not mark the entire project DONE when any mandatory module or research evidence is NOT VERIFIED.

## Per-milestone implementation cycle

These are instructions for later explicitly authorized tasks, not progress checkboxes to tick in this shared plan.

- [ ] Read the single selected task, explicit DONE dependencies, this design and its exact detailed implementation plan; approve unresolved security/data/UI decisions before freezing IN_PROGRESS.
- [ ] Write named failing regression/acceptance tests for the owning negative and success cases; verify the failure is behavioral, not a missing environment.
- [ ] Implement only the task allowlist, preserving existing uncommitted files and contracts. Use one reusable native implementer for code; main independently reviews the full diff and AC evidence.
- [ ] Run targeted GREEN and relevant full regression, role/API/browser/research verification against guarded disposable resources. Record unavailable checks as NOT VERIFIED.
- [ ] Follow VERIFYING -> REVIEWING -> DONE only with the required evidence; required findings return to IN_PROGRESS first, at most three correction rounds before material-blocker escalation.
- [ ] Present exact diff/evidence for separately authorized logical commit/publication. Never infer Git authority or authorization to start the next task from completing the current one.

## Verification commands and safety

For backend changes use the verified task environment and an explicitly guarded disposable PostgreSQL URL: `python -m pytest -q` and `python -m ruff check app tests alembic`. Never print credential values or use the development DB. For frontend changes run in client/: `npm.cmd run test:all`, `npm.cmd run typecheck`, `npm.cmd run build`. Where relevant run `npm.cmd run e2e` only after proving the configured isolated stack/database/loopback target. Never run fixture suites that truncate the same DB concurrently.

Run `git diff --check` and inspect actual status/unstaged/staged diffs before any approved commit. Do not compile unknown untracked LegacyProductsPage or treat its exclusion as proof of a dirty-checkout build. Prefer a clean tracked-source verification context when appropriate.

Research CLI commands/signatures are frozen by each later detailed plan once dataset/model contracts exist; none is presented as an available executable here. Dataset snapshots, model/run config, software versions, splits, seeds, metrics, runtime and limitations are required experiment outputs, not new tests/build results from this roadmap.

## Handoff

M1 hands the stable specification and this roadmap to the human for review; its selected task stays REVIEWING until that approval. Full detailed implementation plans for M2-M12 are authored only under their own explicit task selection, not guessed globally. No calendar guarantee is made before data access and Llama feasibility are resolved. The 04/12/2026 outline target is not silently revised; infeasibility requires an explicit human decision about schedule/resources/scope.
