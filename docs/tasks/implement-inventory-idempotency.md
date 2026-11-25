# implement-inventory-idempotency — Idempotency cho POST /inbounds và /outbounds

## Metadata

- Status: DONE
- Phase: P1
- Plan: Báo cáo P0.2 `P0_RUNTIME_VERIFICATION.md` §11 (Task 1); báo cáo P0.1 `P0_FINAL_VERIFICATION.md` §11 (Task 1); báo cáo P0 `P0_VERIFICATION.md` §4.1 (BE2-07g)
- Depends on: docs/tasks/fix-frontend-baseline-tests.md
- Created: 2026-11-25
- Started: 2026-11-25
- Completed: 2026-11-25

## Goal

Áp dụng pattern idempotency đã có của `StockTransfer` và `PurchaseRequestWorkflow` cho hai endpoint tạo inbound/outbound, để retry (tuần tự hoặc đồng thời, cùng key) không tạo trùng và không thay đổi stock lần nữa.

## Context

- Repo: https://github.com/tonazario08/smart-warehouse, branch `feat/figma-ui-v2`, baseline `7b332d231fad49dcd89f2f3254e1502321087650`.
- BE2-07g (High, P0): router `app/inventory/router.py` không có `Idempotency-Key`; model `Inbound`/`Outbound` không có cột key/fingerprint; migration `0001` xác nhận bảng `inbounds`/`outbounds` không có cột idempotency.
- P0.2 đã tái hiện bằng runtime: POST `/inbounds` cùng body 2 lần không key → 2× 201, 2 bản ghi, stock 10 → 20.
- Pattern đã có và đã xác minh bằng runtime: transfer (`app/transfers/service.py:66-112`, advisory lock `pg_advisory_xact_lock` theo actor+key, fingerprint SHA256 của body, replay 200 / body khác 409, 503 + `Retry-After: 1` khi chưa chắc chắn) và purchase request (cùng pattern).
- Frontend hiện tại: `src/api.ts` `request()` đã merge header tùy ý; `createInbound`/`createOutbound` không gửi key, chỉ chống bấm đúp bằng cờ `saving`.
- Quyết định đã phê duyệt: D-05 — sử dụng UUID và sessionStorage cho Idempotency-Key của inbound/outbound. D-02 — purchase request là tài nguyên riêng của từng CLIENT (không đổi). D-01/D-04 tạm giữ hành vi hiện tại.

## In Scope

- Backend: `Idempotency-Key` bắt buộc cho hai endpoint tạo inbound/outbound; UUID, actor scope, request fingerprint chuẩn hóa; unique constraint ở database; migration mới, không sửa migration cũ; tương thích với dữ liệu lịch sử và các workflow nội bộ đang tạo inbound/outbound (transfer legs, purchase request fulfillment tạo inbound/outbound nội bộ — phải kiểm tra toàn bộ caller trước khi thay đổi API contract).
- Frontend: sinh UUID bằng cơ chế phù hợp với môi trường runtime; lưu key đang chờ xử lý trong sessionStorage, phân biệt tài khoản và loại giao dịch; giữ nguyên key khi retry sau timeout hoặc mất kết nối; hỗ trợ reload trang khi giao dịch chưa xác định kết quả; không tái sử dụng key cho giao dịch khác; không lưu credential hoặc dữ liệu nhạy cảm không cần thiết.
- Cập nhật API documentation và test liên quan.
- Giữ nguyên transaction atomicity, stock locking và overflow protection.

## Out of Scope

- Không mặc định yêu cầu mọi endpoint nội bộ phải có cùng cơ chế idempotency nếu phá vỡ workflow hiện tại.
- Không thay đổi pattern idempotency của transfer/purchase request (chỉ tái sử dụng).
- Không thay đổi thuật toán AI, kiến trúc hệ thống, logic nghiệp vụ ngoài phạm vi task, chính sách phân quyền (D-01/D-04).
- Không sửa migration cũ.

## Acceptance Criteria

- [x] AC-1 — Cùng key và cùng payload (retry tuần tự): trả lại bản ghi ban đầu, không thay đổi stock lần nữa.
- [x] AC-2 — Hai request đồng thời với cùng một key mới: chỉ tạo một giao dịch.
- [x] AC-3 — Cùng key nhưng payload khác: 409.
- [x] AC-4 — Cùng key khác actor: không trả bản ghi của actor khác (404 hoặc 409 theo đúng pattern transfer/purchase request).
- [x] AC-5 — Khác key cùng payload: tạo giao dịch mới (không chặn nhầm).
- [x] AC-6 — Thiếu key hoặc key không hợp lệ: từ chối request, không ghi dữ liệu.
- [x] AC-7 — Transaction rollback: lỗi giữa chừng không để lại stock/bản ghi dở dang.
- [x] AC-8 — Concurrent inbound tạo stock mới: tổng stock đúng, chỉ 1 dòng `stocks`.
- [x] AC-9 — Concurrent outbound vượt tồn kho: 1× 201 + 1× 409 `INSUFFICIENT_STOCK`, stock cuối >= 0.
- [x] AC-10 — Migration upgrade/downgrade thành công trên DB dùng một lần.
- [x] AC-11 — Regression của transfer và purchase request: retry cùng key vẫn đúng (201→200, replay 200).
- [x] AC-12 — Frontend retry sau timeout và reload trang: giữ nguyên key, không tạo trùng; không tái sử dụng key cho giao dịch khác.
- [x] AC-13 — Toàn bộ caller nội bộ tạo inbound/outbound đã được kiểm tra và tương thích.

## Verification Commands

### Focused

- `python -m pytest -q tests/test_inventory.py tests/postgres/test_inventory_concurrency.py`
- `python -m pytest -q -m postgres tests/postgres/test_inventory_concurrency.py`

### Regression

- `python -m pytest -q -m "not postgres"`
- `python -m pytest -q -m postgres`
- `python -m pytest --cov=app --cov-report=term-missing -q`
- `cd client && npx vitest run`
- `cd client && npm run typecheck`
- `cd client && npm run build`

### Static and Diff

- `git status`
- `git diff`
- `git diff --staged`
- `ruff check app tests`

## Progress Log

- 2026-11-25 — Bắt đầu IN_PROGRESS. HEAD a1d2522, cây sạch trừ 3 task file untracked (đúng kỳ vọng). Dependency fix-frontend-baseline-tests.md DONE.
- 2026-11-25 — Phân tích: pattern transfer đã xác minh (service.py:66-112, advisory lock actor+key, fingerprint SHA256, replay 200 / khác body 409, 503 + Retry-After: 1). Khác actor + cùng key tạo bản ghi riêng, không rò rỉ (test_transfer_concurrency.py:48). Caller nội bộ: transfer legs (repository.add_leg) và PR fulfilment (repository.add_outbound) đi qua repository, không qua InventoryService; các caller qua service (test, prepare_gis_e2e, GIS) sẽ nhận key do server sinh khi không truyền key.
- 2026-11-25 — Backend xong: model Inbound/Outbound thêm idempotency_key + request_fingerprint (nullable) và unique constraint (created_by_id, idempotency_key); migration mới 20261125_0013; repository lock_movement_key/find_by_key/add_* nhận key/fingerprint; service create_inbound/create_outbound trả (record, replay), retry loop mirror transfer, 503 INBOUND/OUTBOUND_RETRY_REQUIRED; router bắt buộc header Idempotency-Key UUID, 200 replay/201 tạo mới, thêm GET by-key; schema trim reference/note để fingerprint chuẩn hóa; docs/api/phase-1-contract.md cập nhật. Test mới: tests/postgres/test_inventory_idempotency.py (32 test) và test_inventory_idempotency_migration.py (3 test) — đều pass. Các call site tuple đã cập nhật (test_inventory_transactions, test_inventory_concurrency, test_transfer_concurrency, test_purchase_request_concurrency, prepare_gis_e2e, test_rbac_matrix).
- 2026-11-25 — Frontend xong (D-05): helper mới client/src/shared/api/movementIdempotency.ts (crypto.randomUUID, sessionStorage theo tài khoản + loại giao dịch, fingerprint chuẩn hóa, chỉ lưu key/input, không credential); api.ts legacy và features/inventory/api.ts đều gửi header Idempotency-Key; MovementPages.tsx (production) và MovementForm.tsx đều có retry cùng key sau timeout/mất kết nối và khôi phục sau reload; thêm GET by-key ở features api. 3 test vitest mới (helper, retry giữ key, reload khôi phục đúng key).
- 2026-11-25 — Sửa do test:host phát hiện — MovementPages dùng useRef nhưng mock React của host test không có useRef, và Node không có sessionStorage: bỏ useRef (dùng state), thêm browserSessionStorage() guard. Sau sửa: test:host 88/88 pass, typecheck pass. Lưu ý: lần chạy test:host đầu tiên sau thay đổi đã fail 3 test (đã sửa, không giấu).
- 2026-11-25 — Batch M7 phát hiện 1 test vỡ do migration mới: test_b2b_delivery_location pin schema ở 0012 (head cũ) rồi chạy app mới → INSERT outbound lỗi UndefinedColumn (cột idempotency_key). Đây là test pin stale, không phải lỗi implementation: deployment sequence luôn migrate trước khi start app. Đã sửa test nâng target upgrade lên 20261125_0013; chạy lại 4 passed. Batch M5 snapshot 17 passed sau khi upgrade DB lên 0013.
- 2026-11-25 — Live server kiểm chứng xong (12/12 check, xem Verification Evidence). Coverage backend đang chạy (P0.2 mất ~1600s).
- 2026-11-25 — Sự cố môi trường (không phải code): runtime/VM bị thay thế giữa chừng — PostgreSQL cài qua apt và toàn bộ cluster/DB dùng một lần biến mất (repo, venv, node_modules trong ~/workspace còn nguyên). Đã cài lại postgresql-16 và tạo lại 5 cluster (main 5432, m4 18545, m5 18546, m7 18547, demo 55432; locale C.UTF-8 vì chỉ có C/C.utf8/POSIX), tạo lại role/DB M7 và migrate lên head 0013, rồi chạy lại batch M7. Evidence số liệu trước đó (coverage, live, M5, M7 lần 1) đã ghi trong task file nên không mất.
- 2026-11-25 — Verification hoàn tất, chuyển IN_PROGRESS → VERIFYING (evidence đã điền đủ: focused, regression, coverage 90%, live server 12/12, M5 17 passed, M7 34 passed + 1 error guard artifact đã giải thích). Self-review đã thực hiện trên toàn bộ diff (service/router/frontend/helper/test migration): không có finding bắt buộc phải sửa code — hai finding trong quá trình làm (pin head migration, pin schema 0012 ở test b2b) đã sửa và kiểm chứng lại. Chuyển VERIFYING → REVIEWING. Không đánh dấu DONE; không commit/push/PR (parent xử lý).

## Verification Evidence

### Focused

- `ruff check app/inventory app/models/domain.py tests/postgres/test_inventory_idempotency.py tests/postgres/test_inventory_idempotency_migration.py alembic/versions/20261125_0013_inventory_idempotency.py` — **All checks passed** (sau khi sửa 2 dòng dài E501 ở router và 1 import thừa F401).
- `python -m pytest -q tests/unit/test_architecture.py` — **20 passed** (ràng buộc 1 commit + 1 rollback trong create_inbound/create_outbound và delegate router đều giữ nguyên).
- `alembic upgrade head` trên DB dùng một lần `smart_warehouse_p0_pg_test` — **20261122_0012 → 20261125_0013 (head)**.
- `python -m pytest -q tests/postgres/test_inventory_idempotency.py` — **32 passed** (replay tuần tự inbound/outbound, 422 thiếu/sai key, RBAC 401/403/201, khác actor cùng key tạo bản ghi riêng không rò rỉ, khác key cùng payload tạo mới, failed attempt không đốt key, concurrent cùng key mới chỉ 1 giao dịch, rollback sau lỗi flush, 503 envelope + Retry-After: 1, mất kết nối sau commit thật rồi replay 200).
- `python -m pytest -q tests/postgres/test_inventory_idempotency.py tests/postgres/test_inventory_concurrency.py tests/postgres/test_inventory_transactions.py tests/postgres/test_rbac_matrix.py tests/postgres/test_transfer_concurrency.py tests/postgres/test_transfer_atomicity.py tests/postgres/test_purchase_request_concurrency.py` — **219 passed, 1 failed** lúc đầu (`test_controlled_overlapping_writers_observed_by_postgres[first_inbound]` dùng `.id` trực tiếp trên tuple — đã sửa call site, xem Progress Log); chạy lại nhóm transfer/GIS sau sửa: **40 passed**.
- `python -m pytest -q tests/postgres/test_inventory_idempotency_migration.py` với `TEST_MIGRATION_DATABASE_URL=.../smart_warehouse_p0_mig_test` — **3 passed** (upgrade/downgrade 20261122_0012 ↔ head, dữ liệu lịch sử giữ nguyên với key NULL, vi phạm unique constraint đúng tên).
- Frontend focused: `npx vitest run src/shared/api/movementIdempotency.test.ts src/api.integration.test.ts src/features/inventory/MovementForm.test.tsx` — **35 passed** (helper D-05, gửi đúng 1 header Idempotency-Key UUID, retry sau mất kết nối giữ nguyên key, reload khôi phục pending và retry đúng key).
- `npm run typecheck` — **pass** (sau khi sửa 3 lỗi type ở MovementForm/api/helper).
- `npm run build` — **pass** (built 1.42s, JS 975.19 kB; cảnh báo chunk > 500 kB đã có từ trước).

### Regression

- Full `npx vitest run` — **56 files, 621 passed** (baseline P0.2 612/614 + 7 test mới; 2 test fail baseline đã sửa ở Task 11).
- `npm run test:host` — **88 passed** (sau khi sửa useRef/sessionStorage; xem Progress Log).
- `python -m pytest -q -m "not postgres"` — **3 failed / 1222 passed / 16 skipped / 302 errors** — khớp đúng baseline P0.2 (3 failed RT-02 Windows tooling; 302 errors thiếu TEST_DATABASE_URL). Không có failure mới.
- `python -m pytest -q -m postgres` (p0_pg_test + p0_mig_test) — **21 failed / 336 passed / 15 errors**. So với P0.2 (25 failed / 294 passed / 18 errors): tăng 42 passed (35 test mới + pin migration), giảm failed. Phân tích 21 failed: 16 guarded-identity (M5 snapshot 14 + anomaly link 1 + b2b demo 1, có sẵn P0.2); 4 operational worker/review (đã kiểm chứng fail giống hệt ở HEAD khi stash — guard role/host của worker, có sẵn P0.2); 1 test_transfer_migration historical (do migration mới thêm cột — đã sửa test, chạy lại **3 passed**). 15 errors là migration test guard M4 (có sẵn P0.2).
- Batch M7 (guarded identity 18547) — lần 1: 34 passed / 1 failed (test_b2b_delivery_location pin schema 0012 — đã sửa, chạy lại **4 passed**). Sau sự cố VM (xem Progress Log), cài lại PostgreSQL và chạy lại batch M7 lần 3 trên cluster mới: **34 passed / 1 error** — error là test_anomalies_migration (guard "Migration DB must be exclusively reserved": còn 1 connection mở trên migration DB lúc setup, artifact thứ tự chạy; test này không chạm inbounds/outbounds và **pass riêng 1 passed**). Batch M7 coi như 35/35 với 1 artifact môi trường đã giải thích.
- Batch M5 snapshot (guarded identity 18546, DB đã upgrade lên 0013) — **17 passed** (khớp P0.2).
- Coverage backend `python -m pytest --cov=app --cov-report=term-missing -q` (1619.63s) — **TOTAL 90%** (12999 statements, 1293 missed), khớp baseline P0.2 90% (12868 statements); inventory: service 88%, router 98%, repository 93%, schemas 100%. Kết quả chạy: **23 failed / 1861 passed / 16 skipped / 15 errors** — cùng 23 failed như P0.2 (M5 snapshot 14, anomaly link 1, b2b demo 1, worker/review 3, RT-02 3; 15 errors guard M4). Không failure mới. D-06 (mục tiêu 85%) đạt: 90% ≥ 85%.
- Batch M5 snapshot (guarded identity 18546, DB đã upgrade lên 0013) — **17 passed** (khớp P0.2).
- Live server (uvicorn port 8003, DB dùng một lần smart_warehouse_p0_test, script /tmp/p1-live-idempotency.py) — **12/12 check pass**: inbound 201 → replay 200 cùng id, stock không đổi; conflict 409 IDEMPOTENCY_KEY_CONFLICT; thiếu/sai key 422; key mới 201; GET by-key 200/404; actor khác cùng key → 201 bản ghi riêng; outbound đồng thời cùng key mới → [200, 201] cùng id, stock trừ 1 lần; outbound đồng thời vượt stock (key khác) → [201, 409].
- Regression AI (fixture/synthetic, như P0.2) — tests/test_assistant_api.py + tests/test_forecasting_evaluation.py + tests/test_anomalies_scoring.py: **69 passed** (41 + 17 + 11, khớp P0.2).

### Static and Diff

- `git status` / `git diff` cuối phiên sẽ kiểm tra trước khi báo cáo; chưa commit (parent xử lý commit/push).

## Review Result

- Result: PASSED (independent review by parent)
- Findings: Parent đã đọc toàn bộ `git diff` (service, router, repository, schemas, domain, migration, frontend helper/pages, test). Không có finding bắt buộc nào. Pattern tái sử dụng đúng transfer/PR (advisory lock actor+key, fingerprint SHA256, replay 200 / conflict 409 / 503 + Retry-After: 1); RBAC chạy trước kiểm tra key; header bắt buộc đúng 1 giá trị UUID; migration mới duy nhất 20261125_0013, cột nullable nên dữ liệu lịch sử an toàn; không sửa migration cũ; không secret nào trong diff (chỉ fixture test). Lưu ý môi trường: VM bị thay thế giữa chừng làm mất cluster/DB dùng một lần — parent đã tạo lại role `p0test` + DB `smart_warehouse_p0_pg_test` / `smart_warehouse_p0_mig_test` trên cluster main 5432 (mật khẩu dùng một lần chỉ dùng trong sandbox) và migrate lên head 0013 để kiểm chứng độc lập.

## Completion Evidence

- Independent verification by parent (DB dùng một lần mới tạo lại, migrate lên head 0013): `ruff check` All checks passed; `pytest tests/postgres/test_inventory_idempotency.py tests/postgres/test_inventory_idempotency_migration.py` → **35 passed**; frontend focused `vitest run src/shared/api/movementIdempotency.test.ts src/api.integration.test.ts src/features/inventory/MovementForm.test.tsx` → **35 passed**.
- Executor verification: full vitest 621 passed (56 file), host 88/88, typecheck + build pass; non-postgres 3 failed / 1222 passed / 302 errors (khớp baseline P0.2, RT-02); postgres 21 failed / 336 passed / 15 errors (đều đã giải thích: guarded-identity, worker guard, M4 guard); coverage backend TOTAL 90% (D-06 đạt, mục tiêu 85%); live server 12/12 check pass; AI regression 69 passed.
- AC-1..AC-13 đều đạt. REVIEWING -> DONE ngày 2026-11-25.
