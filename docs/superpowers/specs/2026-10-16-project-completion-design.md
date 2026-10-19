# Thiết kế phạm vi hoàn thiện Smart Warehouse

## Authority and purpose

This is the stable design output of `docs/tasks/define-completion-baseline.md`, based on the twelve-milestone roadmap explicitly approved by the human on 2026-10-16. It is not an executable task or a progress ledger. All M1 state, evidence, review and completion belong only to that selected task.

The goal is a unified warehouse system with reliable operational records, demand forecasting, uncertainty-aware replenishment, cold-start support, explainable anomaly detection, GIS, B2B and an RBAC-controlled assistant. Software correctness and research effectiveness require different evidence; neither an attractive UI nor passing CI proves a forecasting or replenishment advantage.

The supplied thesis outline is `C:/Users/TQUOCTOAN/Downloads/V1_De_cuong_DACN_Truong_Quoc_Toan.docx`, read-only SHA256 `E1683DB5909F21FA7199026C82E9CBB76F605341656D8C4AE84FB8456BBDA9C9`. Use the complete expected-results scope, including extensions. A narrower introductory research-focus sentence does not authorize deleting K-Means, Isolation Forest/SHAP, GIS or RAG/Llama from the approved scope. Do not commit the DOCX or personal metadata. If the source changes, reconcile the revision explicitly rather than silently changing this baseline.

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

## Current capability and requirement matrix

Code baseline is `d8b3fa82b4b77cba5a3faed49738bf5ebe5c46d6`. The matrix distinguishes source inspection from runtime/research evidence; absence means not found in the reviewed tracked application, not a claim about all disks/branches.

| Requirement | Observed implementation boundary | Owner | Required acceptance evidence |
| --- | --- | --- | --- |
| Architecture, JWT/RBAC and existing working flows | app/main.py registers the current operational modules; app/auth/dependencies.py owns server permissions. client/src/App.tsx uses client/src/app/router.tsx and the current auth provider. | M1 preservation; all future milestones | Contract/role regression plus real login, hydration, invalid-token/logout evidence when touched. |
| Users, categories, suppliers, audit and full transaction management UI | APIs/modules and legacy feature components exist, but active client/src/app/router.tsx does not mount those management routes. Existing E2E explicitly uses real API coverage for management/audit, not invented approved Figma screens. | M2 | Active Vietnamese routes, supported actions, role matrix and real browser evidence; design approval for screens without an approved reference. |
| Atomic stock transfers | app/inventory/service.py coordinates inbound/outbound with commit/rollback; app/inventory/repository.py uses row locks. Existing transaction enum models inbound/outbound, not a complete transfer workflow. | M3 | Conservation, same-source/destination rejection, rollback, idempotency, deterministic lock order and PostgreSQL concurrency tests. |
| B2B purchase requests | Client read access and app/models/domain.py PurchaseRequest schema exist. No registered purchase-request service/router or active request UI. | M4 | Ownership/IDOR tests, request transitions, publication-policy tests, linked fulfillment and replay protection. |
| Traceable demand data | Timestamped movements, actor/reference information and seed/test records exist. No admitted research dataset or versioned preparation pipeline identified. | M5 | Licensed source manifest, rejected-row/missingness report, reproducible daily SKU/warehouse series and demand-semantics checks. |
| XGBoost forecasting | No forecasting module, evaluation artifacts or ML dependency found in reviewed runtime/pyproject.toml. | M6 | Temporal held-out comparison to baselines, leakage tests, versioned predictions and usable API/UI with unavailable-data states. |
| Uncertainty, Safety Stock, ROP and EOQ | Product.reorder_level and low-stock comparison are static thresholds; app/dashboard/repository.py does not implement a learned replenishment policy. | M7 | Unit-consistent calculations, lead-time uncertainty treatment, interval calibration and out-of-sample inventory-policy simulation. |
| New-product cold-start | Category/supplier metadata exist; no K-Means fitting, assignment or cold-start evaluation found. Price/weight are not assumed available. | M8 | Held-out SKU evaluation, training-only preprocessing, insufficient-feature fallback and explicit confidence/provenance. |
| Isolation Forest with SHAP | No anomaly training/scoring/explanation workflow found. | M9 | Curated/injected test cases clearly labeled, reviewer-assessed alert results and noncausal feature-attribution explanation checks. |
| Warehouse GIS | Warehouse coordinates and a map link exist; Region/RouteLog are schema-level foundations, not operational A*, nearest-stock selection or heatmap. | M10 | Spatial data provenance, missing/unreachable cases, stock-feasible ranking and A*/reference shortest-path agreement. |
| RAG plus Llama 3.1 8B Instruct | No assistant retrieval/tool/inference integration identified. | M11 | Authorized retrieval/tool calls, fresh operational API answers, prompt-injection/IDOR/refusal tests and measured resource behavior. |
| Integrated experiments, demonstration and thesis report | Current software tests are useful foundations; no complete research experiment/report evidence admitted. | M12 | Full requirement traceability, reproducible experiments and honest limitations; browser/design evidence and safe operations/backup restoration. |

Read-only reference files also include client/e2e/admin-management.spec.ts, tests/postgres/test_inventory_concurrency.py, tests/postgres/test_inventory_transactions.py and pyproject.toml. Historical hosted Quality run 38878419100 is associated with the baseline commit; this design does not claim to have run a new backend/frontend suite.

## Recommended decisions and boundaries

The human approved the high-level roadmap. Details below marked as proposed defaults are engineering recommendations for baseline review, not proof of data availability or permission to execute dependent tasks.

Keep the modular monolith. Operational writes stay inside transaction-aware services. Start training/evaluation with explicit CLI jobs outside HTTP request handling; persist run metadata/results and expose authorized read endpoints. Do not introduce queues, microservices or a model-serving platform before a measured need and scoped approval.

Proposed daily series key: product/SKU, warehouse and business date in a declared timezone. Preserve original timestamps/timezone and conversion policy. Choose forecast horizon from the admitted history and lead-time needs, not an arbitrary globally fixed number. Training consumes only information available at the cutoff; scaling, encoding, imputation and cluster fitting must be training-only. Freeze splits, baselines, metrics and policy parameters before inspecting the final test set.

New management screens reuse current tokens/layout, not a competing legacy auth/shell tree. Existing approved Figma screens remain visual authority. Screens without approved frames need an approved design/interaction description; do not claim an unreviewed layout is Figma-verified.

Retain the existing PurchaseRequest schema when designing its additive API; do not create a competing second request model without a justified migration. Approval alone does not decrement stock. Fulfillment links to real outbound records exactly once. Purchase requests are not supplier replenishment purchase orders; inventory-position/on-order semantics must be designed explicitly for M7 rather than counting customer requests as inbound supply.

For transfers, maintain linked source/destination movements under one atomic boundary and distinguish them from sales demand. Do not redefine old inbound/outbound response contracts or add a transaction enum value without a compatible migration/consumer review. Exclude transfers from demand targets using explicit provenance, not fragile note-text matching.

## Dataset admission and research gates

| Input | Observed readiness | Admission requirement and behavior when absent |
| --- | --- | --- |
| Historical SKU/warehouse demand | NOT VERIFIED; zero tracked CSV/parquet/notebook/pickle/joblib candidates in scoped inventory; no dataset supplied/admitted | Source owner/license, coverage dates, SKU/warehouse identifiers, units, timezone, collection process and exclusion policy must be recorded. Do not infer that no external dataset exists. |
| Outbound versus actual demand | NOT VERIFIED | Separate customer fulfillment, transfers, corrections, returns/cancellations and test data. Flag stockout-censored sales; observed outbound cannot automatically be treated as unconstrained demand. |
| Missing dates and zero-demand days | NOT VERIFIED | Establish whether the business was observed on each date. Missing observation stays unknown; zero demand is recorded only with support. Preserve inactive/new SKU boundaries. |
| Lead time and supply pipeline | NOT VERIFIED | Record order/receipt dates or an explicitly labeled scenario assumption, units and variability. Supplier replenishment on-order data is not assumed to exist. |
| EOQ cost parameters | NOT VERIFIED | Ordering and holding costs with currency/time basis and owner/source. Missing cost means EOQ unavailable, or a clearly labeled scenario, not fabricated production recommendations. |
| Product features | Category/supplier/unit/static reorder metadata present; feature quality not verified | Validate completeness/encoding. Optional price/weight are used only if genuinely collected and governed. Cold-start fallback is explicit. |
| Anomaly labels and review | NOT VERIFIED | Define curated examples/reviewer protocol. Synthetic anomalies establish test behavior, not production precision/recall. Report validation limits if real labels are absent. |
| Spatial road network and map data | NOT VERIFIED | Source/license/attribution, coordinate reference system, graph extent, routing weights and snapshot/version are required. Do not count a straight-line map link as road routing. |
| RAG corpus/model access | NOT VERIFIED | Authorized source documents and sensitivity/role labels; rights to use model/weights and resource benchmark before deployment. No cloud upload/payment/license acceptance is inferred. |

Data can be developed in two clearly separated modes. Fixture/demo mode supports software correctness and demonstrations. Research mode requires an admitted dataset, documented limitations, temporal evaluation and reproducible artifacts. Never promote fixture-mode metrics to a thesis effectiveness claim.

M1 can be approved as a complete baseline with prerequisites explicitly NOT VERIFIED. That approval does not make the prerequisites true: M5 research-data acceptance and M6/M7 research conclusions remain gated. Where data is inadequate, report the limitation or seek an explicit scope amendment; do not silently remove requirements or claim success.

## Resource feasibility

Read-only capacity observed 2026-10-16: Windows 11, Intel Core i5-11400H, six physical/twelve logical cores, 15.7 GiB visible RAM, NVIDIA GeForce RTX 2050 with 4096 MiB reported by nvidia-smi. Free RAM was 3.4 GiB at observation and is transient.

Llama 3.1 8B Instruct inference throughput, model fit, context limit, supported Vietnamese answers and concurrent operation alongside Docker are NOT VERIFIED. CPU/offload/quantized execution is only a candidate for a later authorized benchmark; no configuration is promised to work from hardware names alone. Do not accept a model license, download weights or provision paid/cloud infrastructure in M1. Failure of feasibility requires a reviewed execution alternative or scope decision, not an unannounced model substitution.

The outline's target date 04/12/2026 is a planning constraint to confirm, not a guaranteed delivery commitment. No milestone start dates or durations are invented. M1 review should establish dataset access and resource alternatives before calendar scheduling is presented as feasible.

## Evaluation and failure behavior

Forecast evaluation uses temporal holdouts/rolling-origin comparisons with justified horizons; compare simple baselines and XGBoost under the same data/splits. MAE and an agreed zero-safe scaled/aggregate metric are primary candidates. An all-zero denominator produces an explicit undefined/not-applicable result, not an artificial percentage. No acceptance criterion requires XGBoost to beat a baseline.

Uncertainty output must record its nominal coverage/quantiles and actual held-out calibration. Replenishment simulation uses a consistent initial state, lead-time/ordering assumptions, warm-up and identical evaluation periods; report fill/service rate, shortage quantity/events, average inventory and costs only where supported. Include sensitivity/scenario labeling. No future demand or test-set tuned policy may leak into decisions.

Cold-start evaluation holds out products, not just random rows, and preserves temporal cutoffs. K-Means similarity and SHAP attributions are not causal or optimality proofs. Absence of input, stale artifacts, incompatible model schema or failed jobs produces a visible unavailable/limited state rather than invented numbers.

Spatial ranking must combine the reviewed distance metric with stock feasibility. A* routing weights/heuristic must be consistent; compare paths/costs with a reference algorithm and include disconnected graphs. Heatmaps disclose aggregation period, quantity/demand meaning and missing data.

The assistant initially offers read-only allowlisted tools. Every query/retrieved chunk is constrained to the caller's backend authorization, including client ownership and publication policy. Dynamic stock/request status comes from live authorized APIs, not stale text embeddings. Treat retrieved documents as untrusted data; test malicious instructions, hidden-role data, stale answers, unavailable tools and questions with no evidence. Show source/time context or abstain.

## Evidence and review contract

Each downstream task declares exact file changes, approved interfaces, failing regression cases, verification commands and evidence-specific ACs before IN_PROGRESS. API tests prove backend behavior; component tests prove bounded frontend behavior; real E2E proves the exercised integrated paths; browser/design checks prove only the inspected screens/states; research runs prove only their dataset/protocol/results.

Screens require loading/empty/error/forbidden states, keyboard/accessibility checks, active-route behavior and evidence at the relevant desktop/mobile sizes. Passing npm build is not browser or Figma verification. Unknown/unavailable checks remain NOT VERIFIED.

Use one reusable native implementer for code and main independent review, at most three correction rounds before escalating material blockers. Execution remains single-task. Human approval of this design/roadmap does not approve all future tasks or any Git publication. Password recovery, new tenant/publication rules, automated inventory actions and paid/cloud inference are not quietly added; they require specific scope/design approval where applicable.
