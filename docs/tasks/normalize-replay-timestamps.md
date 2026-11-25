# normalize-replay-timestamps — Chuẩn hoá timestamp response replay về UTC

## Metadata

- Status: DONE
- Phase: P1
- Plan: Báo cáo P0.2 `P0_RUNTIME_VERIFICATION.md` §6 (RT-01) và §4.1
- Depends on: docs/tasks/implement-inventory-idempotency.md
- Created: 2026-11-25
- Started: 2026-11-25
- Completed: 2026-11-25

## Goal

Chuẩn hoá timestamp trong response replay về UTC nhất quán, để response ban đầu và response replay tuân thủ cùng hợp đồng API bất kể timezone của database session.

## Context

- Repo: https://github.com/tonazario08/smart-warehouse, branch `feat/figma-ui-v2`, baseline `7b332d231fad49dcd89f2f3254e1502321087650`.
- RT-01 (mới, Low, P0.2): replay của purchase request / operational anomaly trả timestamp khác định dạng bản gốc khi timezone của DB session ≠ UTC (`+07:00` thay vì `Z`), cùng một instant nhưng chuỗi khác nhau → test so sánh JSON tuyệt đối fail. Nguyên nhân: replay đọc lại timestamptz từ DB theo session timezone, không chuẩn hóa về UTC.
- Đã chứng minh trong P0.2: 5 test fail trên cluster timezone `Asia/Ho_Chi_Minh`; sau `ALTER DATABASE ... SET timezone TO 'UTC'`, 4/4 test PR replay pass, test worker thứ 5 pass trong batch M7.
- Không chỉ thay đổi timezone của database để test PASS — phải sửa code để response tuân thủ cùng hợp đồng API.

## In Scope

- Chuẩn hoá timestamp response replay về UTC (chuỗi `Z`) cho purchase request và operational anomaly (và mọi đường replay khác có cùng cơ chế, nếu phát hiện trong phạm vi task).
- Kiểm tra trên PostgreSQL timezone UTC và Asia/Ho_Chi_Minh.
- Xác minh response ban đầu và response replay tuân thủ cùng hợp đồng API.

## Out of Scope

- Thay đổi timezone của database dùng một lần để test PASS (chỉ dùng làm đối chứng, không phải giải pháp).
- Thay đổi logic nghiệp vụ, thuật toán AI, kiến trúc hệ thống.
- Sửa các test để hạ assertion hoặc bỏ qua so sánh timestamp.

## Acceptance Criteria

- [x] AC-1 — 5 test replay fail trong P0.2 pass trên DB timezone `Asia/Ho_Chi_Minh` mà không cần `ALTER DATABASE ... SET timezone TO 'UTC'`.
- [x] AC-2 — 5 test replay pass trên DB timezone UTC.
- [x] AC-3 — Response ban đầu và response replay có cùng định dạng timestamp (chuỗi `Z`) cho `created_at`/`updated_at`/`fulfilled_at`/`decided_at`.
- [x] AC-4 — Không đổi hành vi khác của purchase request / operational anomaly (regression pass).

## Verification Commands

### Focused

- `python -m pytest -q tests/postgres/test_purchase_requests_api.py tests/postgres/test_operational_anomaly_worker.py`

### Regression

- `python -m pytest -q -m postgres`
- `python -m pytest -q -m "not postgres"`

### Static and Diff

- `git status`
- `git diff`
- `git diff --staged`
- `ruff check app tests`

## Progress Log

- 2026-11-25 — READY -> IN_PROGRESS. HEAD đã xác minh: `522b087` (Task 1), `git status` sạch trừ 2 file task chưa tới lượt (untracked). Dependency Task 11 và Task 1 đều DONE.
- 2026-11-25 — Cơ chế gốc đã xác minh bằng đọc code: mọi cột timestamptz dùng `default=utc_now` (in-memory UTC → serialize `Z`); khi load lại từ DB, psycopg gắn timezone của session → serialize `+07:00`. `PurchaseRequestService._project` dựng `PurchaseRequestResponse` trực tiếp từ ORM row nên replay (đọc lại từ DB) khác chuỗi với bản gốc (in-memory). Cùng cơ chế ở `ReviewView.model_validate(replay)` (`operational_reviews.py:141`), `TransferResponse` (`from_attributes`, `created_at`), và các read model inventory (`InventoryMovementReadResponse`/`TransactionResponse`/`StockResponse`).
- 2026-11-25 — Tái hiện trên DB timezone `Asia/Ho_Chi_Minh` (`ALTER DATABASE smart_warehouse_p0_pg_test SET timezone TO 'Asia/Ho_Chi_Minh'`, đã xác minh qua `pg_settings` source=database): `pytest -q tests/postgres/test_purchase_requests_api.py tests/postgres/test_operational_anomaly_worker.py` với role `p0test` → **7 failed / 70 passed**. Đúng 5 test RT-01 fail: `test_pending_create_replay_conflict_other_actor_and_inactive_policy`, `test_create_replay_after_each_terminal_state[approved|rejected|fulfilled]` (3), `test_atomic_enqueue_after_commit_replay_and_no_model`. 2 fail còn lại là `test_exact_model_scoring_and_controlled_voucher[valid-flagged|threshold_tie-normal]` — worker subprocess exit 1 do Settings guard yêu cầu role kết thúc `_test` (role `p0test` vi phạm), lỗi môi trường đã biết từ P0.2, không phải RT-01. Thử role `rt01_test` (kết thúc `_test`) thì 146 errors do `TRUNCATE ... RESTART IDENTITY` yêu cầu quyền owner sequence — không dùng role này; giữ `p0test` và ghi 2 test worker scoring là fail môi trường đã biết, so sánh trước/sau để chứng minh không regression.
- 2026-11-25 — Thiết kế bản sửa: chuẩn hoá ở tầng response model (không sửa timezone DB, không đổi assertion test). Thêm helper dùng chung `to_utc()` trong `app/models/domain.py` (cạnh `utc_now`), áp `field_validator(..., mode="before")` cho các trường datetime của `PurchaseRequestResponse` (+ nested decision/fulfillment), `ReviewView`, `TransferResponse`, `InventoryMovementReadResponse`, `TransactionResponse`, `StockResponse`. Lý do chọn tầng schema thay vì set session timezone ở `app/db/session.py`: test postgres dùng engine riêng trong `tests/postgres/conftest.py` (bypass engine của app) nên set session timezone ở app không làm 5 test pass; chuẩn hoá ở schema đảm bảo hợp đồng API bất kể session/engine timezone nào.
- 2026-11-25 — **Đã sửa xong:** `app/models/domain.py` (+13 dòng: `to_utc()`), `app/purchase_requests/schemas.py` (+17: validator cho `created_at`/`updated_at`/`decided_at`/`fulfilled_at`), `app/anomalies/operational_reviews.py` (+8: validator `reviewed_at` của `ReviewView`), `app/transfers/schemas.py` (+6: validator `created_at` của `TransferResponse`), `app/inventory/schemas.py` (+16: validator `created_at` của `InventoryMovementReadResponse`/`TransactionResponse`/`StockResponse`). Không sửa test nào, không sửa migration, không đổi logic nghiệp vụ. `ruff check app tests`: All checks passed. Import kiểm chứng OK. Chuyển IN_PROGRESS -> VERIFYING.
- 2026-11-25 — Verification: 5 test RT-01 pass trên cả 2 timezone (Asia/Ho_Chi_Minh: 75 passed/2 failed; UTC: 75 passed/2 failed; 2 failed còn lại là worker scoring do role guard, đã có từ trước). Regression postgres đầy đủ: 20 failed — trùng khớp tập đã giải thích ở P0.2 trừ 5 RT-01; non-postgres giống hệt baseline P0.2 (3 failed RT-02 / 1222 passed / 302 errors). AC-1..AC-4 đều đạt.
- 2026-11-25 — Self-review (người thực hiện): đọc lại `git diff` — chỉ 5 file trên thay đổi, mỗi validator chỉ chuyển aware datetime về UTC và để nguyên giá trị naive/khác; không test nào bị vô hiệu hóa, không assertion nào bị hạ, không chạm logic nghiệp vụ/RBAC/AI, không có secret nào trong diff. Chuyển VERIFYING -> REVIEWING. Lưu ý: đây là self-review của người thực hiện, review độc lập và commit vẫn do parent xử lý.

## Verification Evidence

### Focused

- DB timezone `Asia/Ho_Chi_Minh`, trước khi sửa: `pytest -q tests/postgres/test_purchase_requests_api.py tests/postgres/test_operational_anomaly_worker.py` → **7 failed / 70 passed** (5 test RT-01 + 2 test worker scoring do role guard).
- DB timezone `Asia/Ho_Chi_Minh`, sau khi sửa: cùng lệnh → **2 failed / 75 passed** (chỉ còn 2 test worker scoring do role guard; 1 ERROR `test_owner_scoped_reads_counts_and_recovery` xuất hiện 1 lần, không lặp lại ở 2 lần chạy sau, test pass khi chạy riêng — nhiễu teardown, không phải regression). Chạy lại lần 2: **2 failed / 75 passed, 0 error**.
- DB timezone UTC, sau khi sửa: cùng lệnh → **2 failed / 75 passed** (chỉ 2 test worker scoring do role guard). 5 test RT-01 pass trên cả 2 timezone.
- 5 test RT-01 đã pass: `test_pending_create_replay_conflict_other_actor_and_inactive_policy`, `test_create_replay_after_each_terminal_state[approved|rejected|fulfilled]`, `test_atomic_enqueue_after_commit_replay_and_no_model`.

### Regression

- `pytest -q -m postgres` (TEST_DATABASE_URL=p0_pg_test, DB timezone UTC): **20 failed / 331 passed / 21 errors**. Toàn bộ 20 failed trùng khớp tập đã giải thích ở P0.2 trừ 5 test RT-01 (nay đã pass): M5 guarded identity ×14 (`test_demand_data_snapshot.py`, `ValueError: A guarded snapshot database is required`), demo identity ×2 (`test_anomaly_outbound_link.py`, `test_b2b_outbound_anomaly_demo.py`, `ValueError: dedicated loopback PostgreSQL demo database and role required`), worker subprocess role guard ×4 (`test_operational_anomaly_reviews.py` ×2, `test_operational_anomaly_worker.py` scoring ×2). 21 errors là các test migration cần `TEST_MIGRATION_DATABASE_URL` (cùng loại với P0.2; số lượng tăng do Task 1 thêm test migration). Không có failure mới nào liên quan timestamp hay module đã sửa.
- `pytest -q -m "not postgres"` (không set TEST_DATABASE_URL, như P0.2): **3 failed / 1222 passed / 16 skipped / 302 errors, 938.61s** — giống hệt baseline P0.2. 3 failed là RT-02 (Task 10); 302 errors là thiếu `TEST_DATABASE_URL` (lỗi môi trường đã biết).
- Lưu ý môi trường: các cluster m4/m5/demo đã bị tạo lại trống sau lần thay VM (không còn role/DB guarded); chỉ cluster m7 còn DB. Điều này không ảnh hưởng kết luận regression vì mọi failure đều đã được xác minh nguyên nhân guard/role bằng thông báo lỗi cụ thể.
- DB `smart_warehouse_p0_pg_test` đã trả lại timezone UTC sau khi kiểm chứng xong (trạng thái cuối giống P0.2).

### Static and Diff

- `ruff check app tests`: **All checks passed!**
- `git rev-parse HEAD`: `522b087bee702326748301f90bb27fba16ad5527` (khớp Task 1).
- `git status --short`: chỉ 5 file sửa + 2 file task mới (untracked). Không có thay đổi nào khác.
- `git diff --stat`: 5 file, 58 insertions, 2 deletions.
- `git diff --staged`: trống (không stage gì).

## Review Result

- Result: PASSED (independent review by parent)
- Findings: Diff tối thiểu và đúng phạm vi — 5 file, 58 insertions. Helper `to_utc()` chỉ chuyển aware datetime về UTC, để nguyên naive; validators chỉ áp cho các trường datetime của response model trên đường replay/read; không test nào bị vô hiệu hóa, không assertion nào bị hạ, không đổi logic nghiệp vụ/RBAC/AI, không sửa migration, không có secret trong diff. Parent đã đọc lại toàn bộ `git diff` và task file, chạy ruff (All checks passed) và kiểm chứng độc lập 2 file focus trên cả 2 timezone: Asia/Ho_Chi_Minh **75 passed / 2 failed**, UTC **75 passed / 2 failed** (2 failed còn lại đều là worker scoring do role guard, đã biết từ P0.2). DB đã trả lại timezone UTC. Không có finding bắt buộc nào.

## Completion Evidence

- Independent verification by parent: `pytest -q tests/postgres/test_purchase_requests_api.py tests/postgres/test_operational_anomaly_worker.py` → **75 passed / 2 failed** trên cả DB timezone Asia/Ho_Chi_Minh và UTC (2 failed là worker scoring do role guard, ngoài phạm vi Task 9); `ruff check app tests` → All checks passed.
- Executor verification: 5 test RT-01 pass trên cả 2 timezone; regression postgres 20 failed / 331 passed / 21 errors (đều đã giải thích, không failure mới); non-postgres giống hệt baseline P0.2.
- AC-1..AC-4 đều đạt. REVIEWING -> DONE ngày 2026-11-25.
