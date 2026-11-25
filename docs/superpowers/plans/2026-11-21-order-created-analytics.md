# Plan/Spec — Phân tích tạm tính khi tạo yêu cầu mua B2B

## Metadata

- Trạng thái: **ĐÃ DUYỆT** — plan authority cho task này, trên checkout triển khai độc lập.
- Task identifier: `implement-order-created-analytics`
- Task: `docs/tasks/implement-order-created-analytics.md`
- Loại công việc: tính năng sản phẩm (không phải repository-process)
- Baseline tham chiếu khi soạn: nhánh `feat/figma-ui-v2`, commit `301260fb82afa0008d7ecf6c31512fdacdc30ad9`, qua gói code context. Người dùng đã xác nhận checkout khớp nhánh, SHA và mã trong phạm vi đã kiểm. Mục 12 phân biệt phần đã kiểm trên checkout, phần chỉ kiểm từ mã baseline và phần chưa xác minh.
- Soạn: 2026-11-21
- Chỉnh 2026-11-22 (lần 6): đánh dấu C-6, C-8, C-9, C-12, C-13, C-15, C-19 theo kết quả kiểm tĩnh; worker dùng cấu hình ứng dụng hiện có (catalog root `None` → chưa đủ dữ liệu, không retry); đăng ký model qua `app/models/__init__.py`; thêm test quyền cho ba route; DB thứ hai cho test migration chuẩn bị trước AC-14, không chặn `READY`. Vẫn `DRAFT`.
- Chỉnh 2026-11-22 (lần 5): ghi bằng chứng mục 12 (C-7, C-16, C-19 đánh dấu; C-1, C-13, C-6/8/9/12/15, C-11 ghi chú); màn demo là khối demo sẵn có trên trang Bổ sung hàng; quy tắc chọn run baseline; thử patch chỉ trong worktree riêng. Vẫn `DRAFT`.
- Chỉnh 2026-11-22 (lần 4): chốt D-1 cho bản demo (chỉ đơn có workflow vào lượng chờ giao; đơn legacy giữ nguyên; test bằng dữ liệu giả); 93 test nhóm liên quan là mốc bắt đầu, full backend suite chạy trước khi chấp nhận bản vá. DB test hiện trống (0 đơn) và full backend suite chưa chạy. Vẫn `DRAFT` chờ duyệt mục 13.
- Chỉnh 2026-11-21 (lần 3): kiểm tra lease bằng `clock_timestamp()`; job hết lease ở lần nhận cuối chuyển `failed` (4.2, AC-5); chốt giới hạn `40001` = 3 vòng chung với `row_version` và cửa sổ 180 ngày theo `created_at`. Plan giữ `DRAFT` đến khi C-1…C-19 được kiểm tra trên checkout đích và mục 13 được duyệt.
- Chỉnh 2026-11-21 (lần 2): worker dùng `claim_token` + lease trong cùng transaction ghi, chạy lại khi `40001` (4.2, 4.7, 4.10); mẫu bất thường "đã duyệt" theo `decision_kind`/`decided_at` (4.6, D-3); AC-5, AC-11, AC-12 cập nhật.
- Chỉnh 2026-11-21: D-2 đổi (màn vận hành không dùng ROP fixture; mục 1, 4.2, 4.5, 4.9, 4.10, 4.11, 6, 10, 11). D-1 làm rõ điều kiện chốt.
- Phê duyệt: xem mục 13

## 1. Mục tiêu và nguyên tắc bất biến

Sau khi tạo thành công một yêu cầu mua B2B mới, hệ thống ghi đúng một job bền vững cùng transaction với đơn. Worker chạy sau commit để cập nhật ba nhóm kết quả tạm tính cho đúng cặp (kho, SKU): ngữ cảnh dự báo, kiểm tra bất thường của chính đơn, và tồn dự kiến phục vụ cảnh báo bổ sung.

Các nguyên tắc dưới đây không được vi phạm ở bất kỳ bước nào:

1. Đơn chờ không phải giao dịch kho. Không đổi `stocks.quantity`, không tạo `inbounds`, `outbounds`, `stock_transactions` hay đơn nhập.
2. Phản hồi HTTP tạo đơn không gọi catalog, mô hình hay phép tính phân tích nào.
3. Không huấn luyện lại, không suy luận nặng, không sửa số dự báo nền.
4. Không dùng mô hình, fixture hay catalog xây cho giao dịch xuất thực như thể đã xác thực cho yêu cầu B2B.
5. Mọi kết quả mới mang nhãn tạm tính; dữ liệu fixture/demo luôn mang nhãn demo.
6. Không thêm trigger vào `approve`, `reject`, `fulfill`; không sửa logic xuất kho hiện có.
7. Không đổi `PERMISSION_ROLES`; không cấp quyền cho `client`.
8. Không ghi đè artifact demo; không dán nhãn dữ liệu demo là dữ liệu vận hành.
9. Màn vận hành không dùng ROP fixture để phát cảnh báo; đối chiếu ROP fixture chỉ ở màn demo có nhãn và không phát khuyến nghị vận hành.

## 2. Hiện trạng mã trên baseline (xem mức xác minh trên checkout tại mục 12)

| Chủ đề | Quan sát | Nguồn trong gói |
| --- | --- | --- |
| Transaction | `PurchaseRequestService._write` chạy `operation()` rồi `session.commit()` một lần; lỗi deadlock/serialization (`40P01`, `40001`) rollback rồi chạy lại cả `operation()` tối đa 3 lần | `app/purchase_requests/service.py` |
| Tạo đơn | `create()` lấy `lock_key` (advisory lock), `find_by_key`; nếu đã có thì trả `(…, True)` (replay) hoặc `409 IDEMPOTENCY_KEY_CONFLICT`; ngược lại `_admit`, thêm `PurchaseRequest`, `flush`, thêm `PurchaseRequestWorkflow`, `flush` | cùng file |
| Xuất kho | `fulfill()` giảm `stock.quantity` và đặt `row.status = "fulfilled"` trong cùng một lần commit | cùng file |
| Trạng thái đơn | `pending`, `approved`, `rejected`, `fulfilled`; `approve` không giữ hàng | `app/models/domain.py` |
| Đơn legacy | Đơn không có `PurchaseRequestWorkflow` là legacy, `approve/reject/fulfill` trả `409 LEGACY_PURCHASE_REQUEST_READ_ONLY` | service, migration `0004` |
| Đơn vị | `PurchaseRequestCreate` không có đơn vị; đơn vị là `Product.unit`. `Stock` duy nhất theo (warehouse, product), `quantity >= 0` | `app/models/domain.py`, `schemas.py` |
| Không có ngày cần hàng | `PurchaseRequestCreate` có `extra="forbid"` và chỉ có `warehouse_id`, `product_id`, `quantity`, `note` | `app/purchase_requests/schemas.py` |
| Quyền | `FORECAST_READ`, `REPLENISHMENT_READ`, `ANOMALY_READ` = admin + warehouse; `client` không đọc được; `PURCHASE_REQUEST_CREATE` = client | `app/auth/dependencies.py` |
| Forecast/replenishment | Run đọc từ catalog đã xác minh, có `binding {product_id, warehouse_id, unit}`; service kiểm tra `product.unit == binding.unit`; `mode` là `operational` hoặc `research`; `dataset_class` là `research` hoặc `fixture`; replenishment `operational` bắt buộc `fixture` | `app/forecasting/service.py`, `app/replenishment/service.py`, `schemas.py` |
| Forecast stale | `ForecastService._view` tính `stale` theo `origin_end` và ngày hiện tại | `app/forecasting/service.py` |
| Bất thường | Chấm điểm hiện chỉ có đường fixture: `dataset_class` là `Literal["fixture"]`, import chỉ khi `app_env` là `test`/`integration` và `anomalies_allow_fixture`; nhãn synthetic; xây từ sự kiện `customer_fulfillment` | `app/anomalies/*` |
| Pipeline mô phỏng | Biến `pending` trong simulation/artifacts là pipeline đơn nhập của mô phỏng, **không phải** đơn B2B | `app/replenishment/simulation.py`, `artifacts.py` |
| Hạ tầng nền | Không thấy outbox, worker, scheduler hay `BackgroundTasks` trong `app/` | tìm kiếm toàn gói |
| Alembic | Revision mới nhất trong gói là `20261113_0007` (`down_revision = "20261110_0006"`) | `alembic/versions/` |
| Test | `tests/postgres/` yêu cầu `TEST_DATABASE_URL` là `postgresql+psycopg` và tên DB kết thúc `_test`; `lock_key` dùng `pg_advisory_xact_lock` (chỉ PostgreSQL) | `tests/postgres/conftest.py`, repository |
| Frontend | Scripts: `typecheck`, `build`, `test:all`; `request(...)` + token trong `features/*/api.ts`; `replenishment/alert.ts` đã có logic đối chiếu ROP với guard | `client/package.json`, `client/src/features/*` |

## 3. Sáu hướng thiết kế đã được người dùng đồng ý

1. **Outbox:** một bảng job duy nhất theo `purchase_request_id`, ghi trong `create()` ở nhánh tạo mới, cùng transaction; worker riêng chạy sau commit.
2. **Lượng chờ giao:** tính khi đọc theo `pending` + `approved`, theo (kho, SKU).
3. **Ngày cần hàng:** baseline không có trường này, nên nhu cầu chờ giao hiển thị riêng, không gán vào kỳ dự báo.
4. **Bất thường:** quy tắc định lượng dự phòng có nhãn riêng, lưu riêng khỏi `anomaly_alerts`; không dùng mô hình/fixture hiện có.
5. **Thứ tự đảo ngược:** chống ghi đè bằng kiểm tra phiên bản ngay lúc ghi.
6. **Quyền:** dùng đúng từng quyền đọc hiện có cho từng loại kết quả; không mở cho client.

## 4. Thiết kế

### 4.1 Tạo đơn và ghi job

Trong `PurchaseRequestService.create`, ở nhánh tạo mới, sau khi `PurchaseRequestWorkflow` được `flush` và trước `_project`, thêm đúng một dòng `order_analytics_jobs` với `purchase_request_id = row.id`, `warehouse_id`, `product_id`, `status = 'queued'`. Dùng cùng `session` nên cùng transaction với đơn.

Hệ quả cần kiểm chứng bằng test:

- Replay (`find_by_key` có kết quả) trả về trước khi tới nhánh tạo → không job mới. Ràng buộc `UNIQUE(purchase_request_id)` là lớp chặn thứ hai.
- `_admit` lỗi (404/409), validation 422 và `IDEMPOTENCY_KEY_CONFLICT` xảy ra trước khi có đơn → không job.
- Rollback (lỗi bất kỳ sau khi thêm job) → `_write` rollback, đơn và job biến mất cùng nhau.
- Retry deadlock chạy lại `operation()` sau rollback → đúng một job sau commit thành công.
- Commit không chắc chắn (503 `PURCHASE_REQUEST_RETRY_REQUIRED`): client retry cùng khóa; nếu commit đã thành công thì replay (job đã có), nếu chưa thì tạo mới (job mới). Cả hai đều ra đúng một job.
- `PurchaseRequestResponse` và hợp đồng HTTP của tạo đơn không đổi. Client không nhận thêm trạng thái phân tích.
- Chỉ sửa trong `create`. `approve`, `reject`, `fulfill`, `_locked`, `_project` giữ nguyên (kiểm bằng diff, xem AC).

### 4.2 Worker

Entrypoint `python -m app.order_analytics.worker` (tham khảo mẫu `app/*/cli.py`), có chế độ `--once` và vòng lặp. Không chạy trong tiến trình API. Worker dùng cấu hình ứng dụng hiện có (`Settings`, C-6); không thêm biến môi trường nếu không cần.

**Đồng hồ:** mọi so sánh thời gian của worker (đến hạn `available_at`, hết hạn `lease_expires_at`, đặt lease và backoff mới) dùng `clock_timestamp()` của cơ sở dữ liệu, **không** dùng `now()`: `now()` trả giờ bắt đầu transaction nên một transaction mở trước hạn lease sẽ thấy lease còn hạn dù thực tế đã hết. Không dùng đồng hồ của worker.

- **Dọn job chết (chạy đầu mỗi lượt nhận việc, cả ở `--once`):** job `running` đã hết lease và `attempts >= max_attempts` chuyển `failed` với `last_error_code = 'LEASE_EXPIRED'`, `claim_token = NULL`, `completed_at` đặt; không nhận lại. Nhờ vậy worker chết ở lần nhận thứ `max_attempts` (thứ 5) không để job kẹt `running` và không có lần nhận thứ 6.

```sql
UPDATE order_analytics_jobs
SET status = 'failed', last_error_code = 'LEASE_EXPIRED',
    claim_token = NULL, completed_at = clock_timestamp(), updated_at = clock_timestamp()
WHERE status = 'running' AND lease_expires_at < clock_timestamp()
  AND attempts >= :max_attempts
```

- **Nhận việc:** transaction ngắn, chọn job `queued` đã đến `available_at`, hoặc job `running` đã hết `lease_expires_at` **và** `attempts < max_attempts`, sắp xếp theo `id`, `FOR UPDATE SKIP LOCKED LIMIT 1`; đặt `running`, `attempts + 1`, `lease_expires_at = clock_timestamp() + lease`, và **`claim_token` mới (UUID ngẫu nhiên, mỗi lần nhận một giá trị mới, kể cả khi nhận lại job hết lease)**; commit.
- **Bảo vệ ghi (claim guard):** mọi transaction ghi kết quả (`order_checks`, `key_states`) hoặc đổi trạng thái job (`succeeded`, trả `queued`, `failed`) bắt đầu bằng câu lệnh bảo vệ trong **cùng transaction ghi**:

```sql
UPDATE order_analytics_jobs
SET updated_at = clock_timestamp()
WHERE id = :job_id AND claim_token = :token
  AND status = 'running' AND lease_expires_at > clock_timestamp()
```

  `rowcount = 0` nghĩa là worker không còn là chủ job (lease hết hạn, job đã `failed` do hết lần nhận, hoặc đã có worker khác nhận lại và đổi token): rollback, **không ghi gì**, bỏ job và không tính là lỗi của job. `rowcount = 1` khóa dòng job tới hết transaction, nên worker khác không nhận lại được giữa lúc kiểm tra và commit. Nếu câu lệnh bảo vệ gặp `40001` vì dòng job vừa bị worker khác đổi, xử lý theo mục `40001` bên dưới; lần chạy lại sẽ thấy token không khớp và dừng. Khi trả `queued`, `succeeded` hoặc `failed`, đặt `claim_token = NULL` để token cũ không bao giờ khớp lại.
- **Xử lý:** chạy ba bước độc lập, mỗi bước idempotent: (1) kiểm tra đơn, (2) ngữ cảnh dự báo, (3) ngữ cảnh bổ sung hàng (mục 4.4–4.6). Mỗi bước ghi qua claim guard. Lỗi một bước không làm mất kết quả bước khác.
- **`40001`:** khi PostgreSQL báo `40001` (serialization failure) lúc dùng `REPEATABLE READ`, rollback rồi chạy lại **toàn bộ transaction từ đầu** (claim guard, đọc `row_version`, đọc đầu vào, tính, ghi), không thử vá giữa chừng. Giới hạn chạy lại là 3 vòng chung với mục 4.7 (đã chốt); vẫn lỗi thì tính là lỗi có thể thử lại của bước đó.
- **Kết thúc:** tất cả bước xong → `succeeded`. Có bước lỗi → ghi `last_error_code` (mã ngắn, không stack trace, không dữ liệu khách), trả `queued` với `available_at` lùi theo backoff; đạt `max_attempts` thì `failed`.
- **Khởi động lại:** lease hết hạn và còn lần nhận (`attempts < max_attempts`) thì job được nhận lại với `claim_token` mới; hết lần nhận thì bị dọn sang `failed` như trên. Worker cũ nếu quay lại bị claim guard chặn. Kết quả đã ghi vẫn giữ; chạy lại không ghi trùng nhờ khóa duy nhất và kiểm tra phiên bản.
- Hằng số đề xuất (cần duyệt, mục 11): `max_attempts = 5`, lease 5 phút, backoff 30s·2^(attempts−1) tối đa 10 phút.

### 4.3 Đọc nhu cầu chờ giao và tồn dự kiến

Lượng chờ giao của (kho w, SKU p) = tổng `purchase_requests.quantity` có `status IN ('pending','approved')`, `warehouse_id = w`, `product_id = p`, **và có dòng `purchase_request_workflows`** (đơn legacy bị loại nhưng giữ nguyên, không sửa, không migrate; xem quyết định D-1).

Tồn dự kiến = `stocks.quantity` − lượng chờ giao. Số âm thể hiện thiếu dự kiến; không sửa tồn thực.

**Cùng một snapshot:** tồn thực và lượng chờ giao được đọc bằng **một câu lệnh SQL duy nhất** (hai scalar subquery trong một `SELECT`), nên cùng một snapshot ở cả READ COMMITTED lẫn REPEATABLE READ của PostgreSQL. Vì `fulfill()` giảm tồn và đổi trạng thái trong cùng một commit, một lần đọc chỉ thấy (tồn cũ, đơn `approved`) hoặc (tồn mới, đơn `fulfilled`), không bao giờ thấy trạng thái trộn → không trừ hai lần.

Quy tắc khác:

- Không có dòng `stocks` cho (w, p): `on_hand = null`, trạng thái `insufficient_data` (lý do `STOCK_ROW_MISSING`). **Không mặc định 0.**
- Đơn vị lấy từ `Product.unit`; tồn và đơn cùng SKU nên cùng đơn vị theo cấu trúc dữ liệu. Không quy đổi đơn vị.
- Sau `reject`/`fulfill`, lần đọc kế tiếp tự loại đơn vì đọc theo `status`. **Không thêm trigger, không bộ đếm riêng.**
- Số lượng chờ giao trả về tách `pending_quantity`, `approved_quantity`, `total_quantity`, `order_count`. Không trả ID đơn, ID khách hay ghi chú.

### 4.4 Dự báo

- Số dự báo nền giữ nguyên, đọc từ run hiện có; không đổi, không tính lại, không cộng gộp.
- Màn dự báo hiển thị riêng khối "Nhu cầu chờ giao (tạm tính)" bên cạnh dự báo nền, **không gán vào kỳ nào**, và không có trường tổng hợp "dự báo + đơn chờ" trong schema phản hồi (schema `extra="forbid"`, không khai báo trường đó).
- Worker phân giải baseline cho (w, p): tìm run `operational` có `binding` khớp `product_id`, `warehouse_id` và `unit == Product.unit`, theo quy tắc chọn xác định đã xác minh ở C-7: lọc run đã xác minh theo `product_id`, `warehouse_id`, `unit == Product.unit`, rồi chọn run mới nhất trong tập khớp. Lưu `forecast_run_id`, `dataset_class`, `stale` tại thời điểm phân giải.
- `Settings.forecast_catalog_root` là `None` (mặc định) được coi như không có run khớp (đề xuất, cần duyệt). Không có run khớp → `forecast.state = insufficient_data` (`BASELINE_NOT_FOUND`) và endpoint **không trả số lượng chờ giao** cho màn dự báo (không tạo số khi thiếu baseline).
- `dataset_class = fixture` → nhãn "Dữ liệu demo/fixture". Run `research` không bao giờ được dùng làm baseline vận hành.

### 4.5 Bổ sung hàng và ROP

- Endpoint trả `on_hand`, `open_quantity`, `projected_quantity`, `unit`, thông tin SKU/kho và trạng thái ngữ cảnh bổ sung hàng. Tồn dự kiến luôn hiển thị kèm công thức (tồn thực − lượng chờ), không phụ thuộc có ROP hay không.
- Tham số `view` (`operational` mặc định | `demo`) tách hai cách đọc ROP. Màn demo là khối demo sẵn có trên trang Bổ sung hàng (C-16); `view=demo` hiển thị trong khối đó, không thêm route hay màn mới.
- **`view=operational` (quyết định D-2):** chỉ đối chiếu ROP khi **đồng thời**: run có `mode = operational`; `dataset_class` **không phải** `fixture`; không phải `research` (kể cả `company_aggregate`); `binding.product_id` và `binding.warehouse_id` khớp; `binding.unit == Product.unit`; `reporting_scope == 'warehouse'`; ngày mô phỏng không phải warmup; ROP là số hữu hạn không âm; `projected_quantity` hữu hạn. Đủ điều kiện và `projected_quantity <= ROP` → "Đề xuất xem xét bổ sung". Thiếu bất kỳ điều kiện nào → "Chưa có ROP vận hành" (`OPERATIONAL_ROP_NOT_FOUND`), không khuyến nghị, vẫn hiển thị tồn dự kiến.
- **Hệ quả trên baseline:** replenishment `operational` bắt buộc `fixture`, nên hiện **không có** ROP vận hành hợp lệ nào: màn vận hành sẽ báo "Chưa có ROP vận hành" cho mọi (kho, SKU) cho đến khi tồn tại run vận hành không phải fixture. Việc tạo run đó nằm ngoài phạm vi.
- **`view=demo`:** cùng guard như trên nhưng `dataset_class` phải là `fixture`. Chỉ hiển thị "Tham chiếu demo: tồn dự kiến so với ROP mô phỏng" với nhãn bắt buộc "Dữ liệu demo/fixture; ROP thuộc ngày mô phỏng, không phải ngưỡng vận hành đã phê duyệt". Không dùng câu "Đề xuất xem xét bổ sung" và không phát khuyến nghị vận hành.
- EOQ chỉ hiển thị là tham khảo khi hợp lệ theo quy tắc đã có (số nguyên dương hữu hạn, không có `reason_code` lỗi); ở `view=demo` kèm nhãn demo. **Không tạo đơn nhập.**
- Worker phân giải run vận hành (nếu có) và run fixture khớp dùng cho tham chiếu demo (lưu `replenishment_demo_run_id`); không dùng ROP `research`/`company_aggregate` cho tồn của một kho.

### 4.6 Bất thường: quy tắc "Kiểm tra đơn tạm tính"

Đây là quy tắc thống kê dự phòng, **không phải mô hình đã xác thực** cho yêu cầu B2B. Nhãn cố định: **"Kiểm tra đơn tạm tính"**. Lưu ở bảng riêng `order_analytics_order_checks`; không ghi vào `anomaly_runs`/`anomaly_alerts`, không gọi `app/anomalies/scoring.py`, không dùng fixture.

**Lịch sử được dùng (H):** các yêu cầu mua của **cùng kho và cùng SKU** thỏa tất cả:

- có `PurchaseRequestWorkflow` (đơn quản lý, không legacy);
- `status IN ('approved','fulfilled')` **và** `workflow.decision_kind = 'approved'` **và** `workflow.decided_at` **nhỏ hơn** `created_at` của đơn đang chấm. Điều kiện duyệt dựa trên thời điểm quyết định, không dựa trên trạng thái hiện tại: đơn lịch sử nay đã `fulfilled` vẫn được tính nếu nó đã được duyệt trước lúc đơn đang chấm được tạo; đơn tạo trước nhưng duyệt sau đó **không** lọt vào mẫu, nên chạy lại job lúc nào cũng cho cùng mẫu. Đơn `pending` và `rejected` không dùng;
- `decided_at` thiếu (NULL) → loại khỏi mẫu. **Không** thay bằng `created_at` hay mốc khác;
- `(created_at, id)` **nhỏ hơn** `(created_at, id)` của đơn đang chấm (loại chính đơn đó; kết quả không phụ thuộc thứ tự worker xử lý);
- `created_at` của đơn lịch sử trong 180 ngày trước đơn đang chấm (cửa sổ tính theo `created_at`, đã chốt 2026-11-21);
- tính từ mọi khách hàng, nhưng chỉ lưu thống kê tổng hợp, không lưu hay trả dữ liệu từng đơn của khách khác.

Baseline đã xác nhận `decision_kind = 'approved'` và `decided_at` có thật; luồng duyệt ghi cả hai, ràng buộc yêu cầu timestamp khi đã duyệt (C-19). Vẫn loại bản ghi thiếu `decided_at` như lớp phòng thủ; không kết luận về dữ liệu thật.

**Số mẫu tối thiểu:** `N_min = 8`. Dưới ngưỡng → `insufficient_data`, lý do `INSUFFICIENT_HISTORY`, `flagged = null`. Không giả định bình thường.

**Quy tắc (rule_id `b2b_quantity_robust_zscore`, rule_version `1`)** với số lượng đơn `q`, trung vị `m` của H, `MAD = median(|x − m|)`:

- Nếu `MAD > 0`: `z = 0.6745 · (q − m) / MAD`. `z > 3.5` → cờ `QUANTITY_HIGH`; `z < −3.5` → cờ `QUANTITY_LOW`; ngược lại không cờ.
- Nếu `MAD = 0`: `q ≥ 3·m` → `QUANTITY_HIGH`; `3·q ≤ m` → `QUANTITY_LOW`; ngược lại không cờ.

Kết quả "không cờ" được hiển thị là "Không phát hiện bất thường theo quy tắc tạm tính", không phải "bình thường đã xác thực".

Lưu kèm: `rule_id`, `rule_version`, tham số, `sample_count`, `median`, `mad`, `score`, `computed_at`. Các hằng số (`N_min`, 180 ngày, 3.5, 3) nằm ở một module `rules.py` và được test trực tiếp.

**Vector kiểm thử lọc lịch sử (cố định):** đơn đang chấm Y tạo lúc T.

| Đơn lịch sử X | Có vào mẫu H của Y? |
| --- | --- |
| `decision_kind='approved'`, `decided_at < T`, nay `approved` | có |
| như trên nhưng nay `fulfilled` | có |
| tạo trước T, `decided_at > T` (duyệt sau khi Y được tạo), kể cả khi chạy lại job sau đó | không |
| `decided_at` NULL (dù `created_at < T`) | không, không thay bằng `created_at` |
| `decision_kind` khác `'approved'` (từ chối) hoặc đang `pending` | không |
| `created_at` ngoài 180 ngày trước T, hoặc khác kho/SKU | không |

**Vector kiểm thử quy tắc (cố định):**

| H | q | Kết quả |
| --- | --- | --- |
| `[10,12,11,9,10,13,11,10]` (m = 10.5, MAD = 0.5) | 11 | không cờ (z = 0.67) |
| cùng H | 14 | `QUANTITY_HIGH` (z = 4.72) |
| cùng H | 30 | `QUANTITY_HIGH` (z = 26.31) |
| cùng H | 2 | `QUANTITY_LOW` (z = −11.47) |
| `[5,5,5,5,5,5,5,5]` (m = 5, MAD = 0) | 14 | không cờ |
| cùng tập `[5,5,5,5,5,5,5,5]` | 15 | `QUANTITY_HIGH` (15 ≥ 3·5) |
| cùng tập `[5,5,5,5,5,5,5,5]` | 1 | `QUANTITY_LOW` (3·1 ≤ 5) |
| 7 phần tử bất kỳ | 30 | `insufficient_data` |

### 4.7 Thứ tự xử lý và chống ghi đè

Có hai loại kết quả với cách bảo vệ khác nhau.

**Kết quả riêng của đơn (`order_checks`):** khóa duy nhất `purchase_request_id`. Job của đơn B chỉ ghi dòng của B nên không thể làm mất kết quả của A. Ghi bằng upsert theo khóa này; chạy lại cùng job chỉ ghi đè đúng dòng đó bằng kết quả tính lại, không tạo dòng mới. Vì H chỉ gồm đơn có `(created_at, id)` sớm hơn, xử lý A trước hay B trước đều cho cùng kết quả cho từng đơn.

**Kết quả tổng hợp theo (kho, SKU) (`key_states`):** khóa chính (`warehouse_id`, `product_id`), cột `row_version`. Worker đọc `row_version` rồi đọc đầu vào (cùng transaction REPEATABLE READ trên PostgreSQL), tính, rồi ghi bằng so sánh-và-ghi:

```sql
UPDATE order_analytics_key_states
SET ..., row_version = row_version + 1
WHERE warehouse_id = :w AND product_id = :p AND row_version = :seen
```

`rowcount = 0` nghĩa là có writer khác đã ghi sau khi worker đọc: worker **không ghi đè**, đọc lại và tính lại (tối đa 3 vòng; vẫn xung đột thì trả lỗi có thể thử lại để job được retry). Mã `40001` của PostgreSQL ở `REPEATABLE READ` được xử lý cùng vòng này: rollback và chạy lại toàn bộ transaction từ đầu, dùng chung giới hạn 3 vòng (giới hạn đã được người dùng chốt 2026-11-21). Mọi vòng đều đi qua claim guard của mục 4.2, nên worker mất quyền sở hữu job không ghi được vào `key_states` hay `order_checks`. Job xử lý chậm với dữ liệu cũ vì thế không bao giờ thay được kết quả mới hơn.

**Số liệu hiển thị tức thời** (`open_quantity`, `on_hand`, `projected_quantity`) không lấy từ bảng lưu mà luôn tính khi đọc theo mục 4.3, nên không bao giờ cũ hơn trạng thái đơn. Bảng `key_states` chỉ lưu phần phân giải catalog và trạng thái từng chức năng (mục 4.4, 4.5).

### 4.8 API và quyền

Module mới `app/order_analytics/` với router tiền tố `/order-analytics` (không đụng route của `forecasts`, `replenishment`, `anomalies`), đăng ký trong `app/main.py`. Mỗi endpoint dùng đúng một quyền đọc hiện có qua cơ chế `require_permission`:

| Endpoint (đề xuất) | Quyền | Nội dung |
| --- | --- | --- |
| `GET /order-analytics/open-demand?warehouse_id&product_id` | `FORECAST_READ` | khối nhu cầu chờ giao + baseline + trạng thái dự báo |
| `GET /order-analytics/replenishment-position?warehouse_id&product_id` | `REPLENISHMENT_READ` | tồn thực, lượng chờ, tồn dự kiến, đơn vị, trạng thái ngữ cảnh |
| `GET /order-analytics/order-checks?purchase_request_id=` hoặc `?warehouse_id&product_id&page&page_size` | `ANOMALY_READ` | kết quả "Kiểm tra đơn tạm tính", phân trang |

- `client` nhận 403 trên cả ba; chưa đăng nhập hoặc người dùng không hoạt động nhận 401, theo mẫu hiện có.
- Dữ liệu cách ly theo (kho, SKU) được truyền vào. Payload không có ID khách, tên khách, ghi chú đơn hay chi tiết từng đơn của khách.
- Tham số kiểm tra chặt (số nguyên dương, không lặp tham số) theo mẫu `positive_integer` và `single_query_params` của purchase-requests.
- Không thêm `Permission` mới nên `PERMISSION_ROLES` và ma trận RBAC không đổi.

### 4.9 Giao diện

Chỉ gắn vào màn hình hiện có, không thêm route:

- Trang chi tiết dự báo: khối "Nhu cầu chờ giao (tạm tính)" tách khỏi dự báo nền, kèm nhãn "Chưa gán kỳ".
- Trang chi tiết replenishment (màn vận hành): hiển thị tồn dự kiến và công thức (tồn thực − lượng chờ); cảnh báo chỉ khi có ROP vận hành hợp lệ, nếu không hiển thị "Chưa có ROP vận hành". Đối chiếu ROP fixture chỉ ở khối demo sẵn có trên cùng trang, kèm nhãn demo/fixture, không phát khuyến nghị vận hành (xem 4.5, D-2).
- Trang bất thường: mục "Kiểm tra đơn tạm tính" tách khỏi danh sách cảnh báo mô hình/SHAP.
- Hiển thị bốn trạng thái: Đang tính, Có kết quả, Chưa đủ dữ liệu, Cập nhật lỗi; kèm thời điểm và nhãn "Tạm tính". Đổi bộ lọc hoặc run không giữ kết quả của lượt trước.

### 4.10 Mô hình dữ liệu và migration

Ba bảng (tên đề xuất; kiểm tra xung đột tên trên checkout đích):

- `order_analytics_jobs`: `id` (identity), `purchase_request_id` (FK RESTRICT, UNIQUE), `warehouse_id`, `product_id` (FK RESTRICT), `status` (`queued|running|succeeded|failed`, CHECK), `attempts`, `available_at`, `lease_expires_at`, `claim_token` (UUID, nullable; NULL khi không `running`), `last_error_code`, `created_at`, `updated_at`, `completed_at`; chỉ mục (`status`, `available_at`, `id`) và (`warehouse_id`, `product_id`, `status`).
- `order_analytics_order_checks`: `purchase_request_id` (PK/FK), `status` (`available|insufficient_data|failed`), `flagged`, `reason_code`, `rule_id`, `rule_version`, `sample_count`, `median`, `mad`, `score`, `label`, `computed_at`.
- `order_analytics_key_states`: PK (`warehouse_id`, `product_id`), `row_version`, `forecast_status`, `forecast_run_id`, `forecast_dataset_class`, `forecast_stale`, `forecast_reason_code`, `replenishment_status`, `replenishment_run_id`, `replenishment_dataset_class`, `replenishment_reason_code`, `replenishment_demo_run_id` (nullable), `computed_at`, `updated_at`.

Migration mới đặt tên theo mẫu `YYYYMMDD_0008_order_created_analytics.py`. **`down_revision` phải lấy từ `alembic heads` trên checkout đích** (gói cho thấy `20261113_0007`, nhưng không được mặc định). Phải có `downgrade()` và test migration theo mẫu `tests/postgres/test_purchase_request_migration.py`. Đăng ký model vào metadata mà `alembic/env.py` dùng.

### 4.11 Ma trận trạng thái

| Chức năng | Điều kiện | Trạng thái trả về |
| --- | --- | --- |
| Mọi chức năng | job `queued`/`running` cho đúng đơn hoặc đúng (kho, SKU) | Đang tính |
| Kiểm tra đơn | H ≥ 8 mẫu | Có kết quả (có cờ hoặc không cờ) |
| Kiểm tra đơn | H < 8 mẫu | Chưa đủ dữ liệu (`INSUFFICIENT_HISTORY`) |
| Dự báo | có run `operational` khớp binding | Có kết quả (nhãn demo nếu fixture; cờ stale) |
| Dự báo | không có run khớp | Chưa đủ dữ liệu (`BASELINE_NOT_FOUND`), không trả số |
| Bổ sung (vận hành) | có tồn và ROP vận hành hợp lệ (không fixture/research, khớp SKU, kho, đơn vị) | Có kết quả; khuyến nghị nếu tồn dự kiến ≤ ROP |
| Bổ sung (vận hành) | không có ROP vận hành hợp lệ: chỉ có fixture, run `research`, sai SKU/kho/đơn vị, ROP null/NaN/âm, ngày warmup, thiếu binding | "Chưa có ROP vận hành" (`OPERATIONAL_ROP_NOT_FOUND`); không khuyến nghị; vẫn hiển thị tồn dự kiến |
| Bổ sung (demo) | có run fixture khớp guard | Tham chiếu demo có nhãn; không khuyến nghị vận hành |
| Bổ sung | thiếu dòng tồn | Chưa đủ dữ liệu (`STOCK_ROW_MISSING`) |
| Bất kỳ | bước lỗi hoặc job `failed` | Cập nhật lỗi (mã ngắn) |

## 5. Kế hoạch triển khai (theo TDD của `implementation-rules.md`)

1. Kiểm tra task, dependency, plan authority, baseline và `alembic heads` (mục 12) **trước** khi ghi `READY -> IN_PROGRESS`. Thử hoặc áp patch chỉ trong worktree Git riêng; không stash, không xóa file hiện có trong worktree đang dùng. Mốc bắt đầu: 93 test nhóm B2B/dự báo/bất thường/bổ sung đã pass; DB test hiện trống (0 đơn), nên mọi dữ liệu kiểm thử (kể cả đơn legacy) do test tự tạo.
2. **RED→GREEN, job và transaction:** test PostgreSQL cho 201, replay, rollback, 4xx, retry deadlock; migration `0008`; thêm job vào `create()`.
3. **RED→GREEN, đọc tức thời:** repository đọc một câu lệnh cho tồn + lượng chờ; test tách pending/approved, cô lập kho/SKU, reject/fulfill, đọc đồng thời.
4. **RED→GREEN, bất thường:** `rules.py` thuần hàm với vector ở 4.6; lưu `order_checks`.
5. **RED→GREEN, worker:** nhận việc, lease bằng `clock_timestamp()`, `claim_token` và claim guard, dọn job hết lần nhận, retry, backoff, khởi động lại, `40001`; phân giải catalog; CAS `row_version`; thứ tự đảo ngược.
6. **RED→GREEN, API và quyền:** ba endpoint, ma trận vai trò, cô lập dữ liệu, không lộ định danh khách.
7. **Frontend:** API client, ba điểm gắn UI, test trạng thái và nhãn; cập nhật test của `alert.ts` giữ các ca hiện có.
8. Chạy lệnh xác minh (mục 7), ghi bằng chứng thật vào task; **chạy full backend suite trước khi chấp nhận bản vá**; review độc lập trước `DONE`.

## 6. Kế hoạch kiểm thử và ánh xạ AC

| AC trong task | Test chính |
| --- | --- |
| AC-1 đúng một job khi tạo mới, tồn và lịch sử không đổi | PG API test: 201 → 1 job `queued`; `stocks`, `stock_transactions`, `inbounds`, `outbounds` không đổi; catalog/mô hình bị chặn trong request |
| AC-2 replay không job mới | PG: cùng khóa + cùng body → 200, vẫn 1 job; cùng khóa khác body → 409, vẫn 1 job |
| AC-3 4xx và rollback không job | PG: 404 SKU/kho, 422, 409; lỗi ép sau khi thêm job → 0 đơn, 0 job; deadlock retry → 1 job |
| AC-4 worker hoàn tất ba cập nhật | PG: job → `succeeded`; `order_checks` và `key_states` có dữ liệu; chạy lại không tạo dòng trùng |
| AC-5 worker retry/khởi động lại | lỗi ép ở một bước → job `queued` với `attempts` tăng, các bước khác giữ kết quả; lease hết hạn và `attempts < max_attempts` → nhận lại với `claim_token` mới; đạt `max_attempts` do lỗi xử lý → `failed` với mã lỗi. **Test chủ sở hữu cũ:** A nhận job (token tA), lease hết hạn, B nhận lại (token tB); A quay lại và thử ghi `order_checks`, `key_states` và đổi trạng thái job → cả ba bị từ chối (`rowcount = 0`), không dòng nào đổi, job vẫn của B; B ghi và hoàn tất bình thường. Thêm ca lease hết hạn nhưng chưa ai nhận lại: token còn khớp mà ghi vẫn bị từ chối. **Test đồng hồ:** mở transaction của A khi lease còn hạn (ví dụ đặt `lease_expires_at` cách hiện tại 1 giây), chờ qua hạn rồi chạy claim guard trong cùng transaction → bị từ chối (ca này sẽ lọt nếu dùng `now()`). **Test worker chết ở lần nhận thứ 5:** job `attempts = 5`, `running`, lease hết hạn, không worker nào ghi → lượt nhận việc kế tiếp chuyển job `failed` với `LEASE_EXPIRED`, `claim_token` NULL, `attempts` vẫn 5 (không có lần nhận thứ 6), không còn `running`; worker cũ quay lại ghi bị từ chối; chạy lượt nhận thêm lần nữa không đổi gì. Ca đối chứng: `attempts = 4` hết lease → được nhận lại thành lần thứ 5. **Test `40001`:** hai transaction `REPEATABLE READ` xung đột để PostgreSQL báo `40001` → rollback, chạy lại toàn bộ transaction từ đầu (đọc lại `row_version` và đầu vào), kết quả cuối đúng và một dòng |
| AC-6 nhu cầu chờ giao, không đổi dự báo nền | tổng `pending`+`approved` theo (kho, SKU); loại `rejected`/`fulfilled`; payload run dự báo so sánh trước/sau giống hệt; schema không có trường tổng hợp ; **test dữ liệu giả:** thêm một đơn legacy (không có dòng `purchase_request_workflows`) `pending`/`approved` cùng kho/SKU → không vào `pending_quantity`, `approved_quantity`, `total_quantity`, `order_count`, và dòng đơn legacy không đổi ; `forecast_catalog_root` = `None` → chưa đủ dữ liệu, không retry, không trả số |
| AC-7 tồn dự kiến | tồn 10, pending 5 + approved 3 → dự kiến 2, tồn vẫn 10; âm được giữ nguyên; thiếu dòng tồn → chưa đủ dữ liệu |
| AC-8 từ chối và xuất kho | sau `reject` đọc lại loại đơn; sau `fulfill` tồn giảm đúng một lần, lượng chờ bỏ đơn, tồn dự kiến không trừ lần hai; diff không đổi `approve/reject/fulfill` |
| AC-9 cùng một snapshot | PG đồng thời: vòng lặp `fulfill` song song với đọc, không bao giờ thấy (tồn mới + đơn còn `approved`) hoặc ngược lại |
| AC-10 ROP | vận hành: ROP hợp lệ → cảnh báo khi tồn dự kiến ≤ ROP; chỉ có fixture → "Chưa có ROP vận hành", không cảnh báo; demo: fixture khớp → tham chiếu có nhãn, không khuyến nghị; ROP null/NaN/âm, ngày warmup, run `research`, sai SKU/kho/đơn vị, thiếu binding → không khuyến nghị; không tạo đơn nhập; tồn dự kiến luôn hiển thị ; `replenishment_catalog_root` = `None` → "Chưa có ROP vận hành", không lỗi |
| AC-11 bất thường | vector ở 4.6 (quy tắc và lọc lịch sử); <8 mẫu → chưa đủ dữ liệu; **test lọc:** X tạo trước Y nhưng `decided_at` sau Y → không vào mẫu, kể cả sau khi X được duyệt rồi worker chạy lại job của Y (kết quả của Y không đổi); X nay `fulfilled` nhưng duyệt trước Y → có vào mẫu; `decided_at` NULL → loại, không thay bằng `created_at`; bảng `anomaly_alerts`/`anomaly_runs` không đổi; `scoring.py` không bị gọi |
| AC-12 hai đơn chạy ngược thứ tự | đơn A rồi B; xử lý B trước A: cả hai `order_checks` đúng và không đổi theo thứ tự; chạy lại job sau khi một đơn khác được duyệt muộn hơn hoặc một đơn trong mẫu chuyển `approved`→`fulfilled` → mẫu và kết quả của đơn đã chấm không đổi; X đọc `row_version = v`, Y ghi `v+1`, ghi của X thất bại và tính lại; `40001` → rollback và chạy lại từ đầu; trạng thái cuối là mới nhất |
| AC-13 quyền và cô lập | admin/warehouse đọc được từng endpoint theo đúng quyền; `client` 403 cả ba; 401 chưa đăng nhập/không hoạt động; không lộ định danh khách; kho/SKU khác không lẫn |
| AC-14 migration | nâng từ head đã xác minh lên `0008`, hạ về lại; ràng buộc và chỉ mục tồn tại |
| AC-15 không hồi quy | toàn bộ test hiện có và build/test frontend đạt ; mốc bắt đầu 93 test nhóm liên quan đã pass; full `python -m pytest -q` phải chạy và đạt trước khi chấp nhận bản vá (lỗi có sẵn trên baseline phải tách khỏi lỗi do bản vá) |
| AC-16 phạm vi và an toàn | diff chỉ trong allowlist; không `.env`/token; không sửa artifact demo; không commit/push |

## 7. Lệnh xác minh đề xuất

Chưa chạy lệnh nào. Phải kiểm tra scripts và công cụ trên checkout đích trước khi dùng.

```bash
# Trước khi chọn revision cha
alembic heads
alembic current

# Focused backend (PostgreSQL dùng DB dùng một lần, tên kết thúc _test)
python -m pytest -q tests/test_order_analytics_rules.py tests/test_order_analytics_api.py
python -m pytest -q tests/postgres/test_order_analytics_jobs.py tests/postgres/test_order_analytics_worker.py tests/postgres/test_order_analytics_migration.py

# Regression backend (bắt buộc trước khi chấp nhận bản vá; chưa chạy full suite ở preflight)
python -m pytest -q

# Migration trên DB thử nghiệm dùng một lần (DB thứ hai cho test migration phải chuẩn bị trước)
alembic upgrade head
alembic downgrade -1
alembic upgrade head

# Frontend (Windows: npm.cmd; Linux: npm)
cd client
npm.cmd run typecheck
npm.cmd run test:all
npm.cmd run build

# Static và diff
ruff check .
git diff --check
git status
git diff
```

Baseline không có mypy (C-12), nên không thêm bước kiểm tra kiểu cho Python. CI Quality còn chạy Windows guards và E2E; lệnh cục bộ tương ứng chưa có trong danh sách này, cần xác định khi chuẩn bị chấp nhận bản vá. Tên file test ở trên là đề xuất; không có nghĩa là file đã tồn tại.

## 8. File dự kiến thay đổi (allowlist đề xuất, cần xác minh)

- Mới: `app/order_analytics/{__init__,models,jobs,repository,rules,service,router,schemas,worker}.py`.
- Sửa: `app/purchase_requests/service.py` (chỉ trong `create`), `app/main.py` (đăng ký router), `app/models/__init__.py` (đăng ký model; `alembic/env.py` đã import `app.models` và dùng `Base.metadata`, không cần sửa), `alembic/versions/YYYYMMDD_0008_order_created_analytics.py`.
- Test mới: các file `tests/test_order_analytics_*.py` và `tests/postgres/test_order_analytics_*.py`; thêm ca cho ba route mới vào test ma trận quyền (và test OpenAPI theo nhóm route nếu cần) hiện có, không đổi `PERMISSION_ROLES`.
- Frontend: `client/src/features/orderAnalytics/{api,types}.ts`; điểm gắn trong `forecasting/ForecastRunPage.tsx`, `replenishment/ReplenishmentRunPage.tsx` và `replenishment/alert.ts`, `anomalies/AnomaliesPage.tsx`; test và CSS tối thiểu tương ứng.
- Task file: chỉ `docs/tasks/implement-order-created-analytics.md` được ghi lịch sử, bằng chứng và review.

## 9. Ngoài phạm vi

Deploy, cấu hình container/CI cho worker, nhắn tin/email, sửa workflow hoặc phân quyền, thay mô hình đã công bố, tự tạo đơn nhập, huấn luyện lại, gán đơn chờ vào kỳ dự báo, dùng fixture làm dữ liệu vận hành, hiển thị phân tích cho `client`, thay đổi logic `approve/reject/fulfill`, commit/push/PR.

## 10. Rủi ro

- Không có hạ tầng worker sẵn nên cần thêm entrypoint chạy riêng; việc chạy nó ở môi trường nào nằm ngoài phạm vi, nhưng nếu worker không chạy thì kết quả ở trạng thái "Đang tính" mãi. Cần hiển thị `computed_at` và trạng thái job rõ ràng.
- `FOR UPDATE SKIP LOCKED` và `pg_advisory_xact_lock` chỉ có trên PostgreSQL; test của chúng phải ở `tests/postgres/`.
- Việc dọn job hết lần nhận chạy trong lượt nhận việc của worker; nếu không worker nào chạy, job chết ở lần nhận cuối vẫn ở `running` (ma trận 4.11 hiển thị "Đang tính") cho đến khi có worker chạy lại.
- Schema và luồng duyệt đã được đối chiếu ở C-19 (đơn đã duyệt phải có `decided_at`); chưa kết luận gì về dữ liệu thật. Nếu khi viết test thấy tên cột hoặc giá trị khác 4.6, phải sửa 4.6 và test lọc lịch sử.
- Hằng số của quy tắc bất thường là đề xuất, chưa hiệu chuẩn trên dữ liệu B2B; phải ghi rõ trong UI là quy tắc tạm tính.
- Đơn legacy (nếu có) bị loại khỏi lượng chờ nhưng giữ nguyên; DB test hiện không có đơn nào nên chưa đo được số đơn legacy và nghĩa vụ giao thật. Nếu dữ liệu thật có đơn legacy `pending`/`approved`, tồn dự kiến sẽ thiếu hụt so với thực tế; phải đo lại (C-10) trước khi dùng ngoài bản demo (xem D-1).
- Full backend suite chưa chạy trên baseline, nên chưa biết lỗi có sẵn (nếu có); khi chạy sau bản vá phải phân biệt lỗi có sẵn với lỗi do bản vá.
- Theo D-2, trên baseline màn vận hành luôn báo "Chưa có ROP vận hành" vì không có run vận hành không phải fixture; tính năng cảnh báo bổ sung chỉ có tác dụng đầy đủ khi có run như vậy. Cần người dùng biết trước để không coi là lỗi.

## 11. Quyết định cần duyệt (giá trị mặc định đề xuất)

| Mã | Quyết định | Mặc định đề xuất |
| --- | --- | --- |
| D-1 (đã chốt cho bản demo) | Đơn legacy (không có workflow) trong lượng chờ giao | Bản demo chỉ tính đơn có `purchase_request_workflows` vào lượng chờ giao; đơn legacy giữ nguyên (không sửa, không migrate, không xóa) và không được tính; có test bằng dữ liệu giả. Chưa đo trên dữ liệu thật (DB test trống); trước khi dùng ngoài bản demo phải đo số đơn legacy `pending`/`approved` và nghĩa vụ giao còn lại (C-10) và duyệt lại |
| D-2 (đã đổi) | Khi chỉ có ROP fixture khớp SKU/kho/đơn vị | Màn vận hành **không** dùng ROP fixture: chỉ cảnh báo với ROP vận hành hợp lệ (đúng kho/SKU/đơn vị, không fixture/research); không có thì "Chưa có ROP vận hành". Đối chiếu fixture chỉ ở màn demo có nhãn, không phát khuyến nghị vận hành. Hệ quả: trên baseline màn vận hành luôn báo thiếu ROP. Phương án đã loại: hiển thị đối chiếu demo ngay ở màn vận hành |
| D-3 | Lịch sử chấm bất thường | Đơn cùng kho/SKU có `decision_kind = 'approved'` và `workflow.decided_at` trước lúc tạo đơn đang chấm (kể cả nay đã `fulfilled`), `created_at` trong 180 ngày (đã chốt), `N_min = 8`; `decided_at` thiếu thì loại, không thay bằng ngày tạo |
| D-4 | Ngưỡng quy tắc | `|z| > 3.5` khi MAD > 0; tỉ lệ 3 khi MAD = 0 |
| D-5 | Hằng số worker | `max_attempts = 5`, lease 5 phút, backoff tối đa 10 phút |
| D-6 | Thiếu baseline dự báo | Endpoint dự báo không trả số lượng chờ giao |
| D-7 | Tiền tố API | `/order-analytics/*` (module riêng) thay vì chèn vào router hiện có |

## 12. Checklist xác minh trên checkout đích

Preflight 2026-11-22 (báo cáo của người dùng) đã xác minh một phần trên `feat/figma-ui-v2`, baseline `301260fb`; mục nào có bằng chứng đầy đủ thì đánh dấu `[x]` kèm kết quả, mục còn lại giữ `[ ]` kèm ghi chú phần đã có. DB test hiện trống (0 đơn) và full backend suite chưa chạy; hai điểm này được ghi rõ ở C-10 và C-14. Không đánh dấu khi chưa có bằng chứng thật.

**Baseline và quy trình**

- [x] C-1 Nhánh và commit của checkout đích; đối chiếu với `301260fb82afa0008d7ecf6c31512fdacdc30ad9` (trùng hay là hậu duệ); `git status` sạch. — Preflight 2026-11-22 (báo cáo của người dùng): nhánh `feat/figma-ui-v2` và baseline `301260fb` đã xác nhận; worktree có thay đổi tài liệu (task, plan); mã trong phạm vi đã kiểm không có diff. **Không ghi là worktree sạch**, nên chưa đánh dấu. Checkout triển khai Git riêng đã được xác minh sạch trên đúng SHA trước khi thêm tài liệu được duyệt; worktree Windows không bị sửa.
- [x] C-2 `alembic heads` chỉ có một head; ghi revision đó làm `down_revision` của migration mới (gói cho thấy `20261113_0007`, không mặc định). — Preflight 2026-11-22 (báo cáo của người dùng): một head duy nhất `20261113_0007`; dùng làm `down_revision`.
- [x] C-3 Năm dependency trong `docs/tasks/` đều `Status: DONE` trên checkout đích: `implement-b2b-purchase-requests`, `implement-b2b-nearest-warehouse`, `implement-demand-forecasting`, `implement-anomaly-explanations`, `implement-replenishment-alerts`. — Preflight 2026-11-22 (báo cáo của người dùng): cả 5 dependency vẫn `DONE`.
- [x] C-4 File task được đưa vào repo, đủ metadata và cấu trúc chuẩn, và chính bạn chuyển sang `READY`. — Preflight 2026-11-22 (báo cáo của người dùng): file task đã ở đúng chỗ trong repo; lúc preflight chưa chuyển `READY`. Quyền chuyển và triển khai được người dùng giao; xem mục 13 và log task.
- [x] C-5 Plan này được đặt đúng thư mục theo quy ước repo (`docs/superpowers/plans/` có tồn tại không; không dùng `docs/plans/` vì AGENTS.md cấm routing qua đó) và được duyệt. — Preflight 2026-11-22 (báo cáo của người dùng): plan đã ở đúng thư mục; đã duyệt sau preflight (mục 13).

**Backend**

- [x] C-6 `app/core/config.py` (không có trong gói): cách khai báo `Settings`, đường dẫn catalog forecast/replenishment, biến môi trường cho worker. — Preflight 2026-11-22 (báo cáo của người dùng): kiểm tĩnh (không chạy): `app/core/config.py` có `Settings.forecast_catalog_root` và `replenishment_catalog_root`, mặc định `None`. Chưa có cấu hình riêng cho worker; worker dùng cấu hình ứng dụng hiện có, không thêm biến môi trường nếu không cần.
- [x] C-7 Repository của forecasting/replenishment: cách nạp catalog và liệt kê run theo `binding` mà không qua HTTP; quy tắc chọn run "mới nhất". — Preflight 2026-11-22 (báo cáo của người dùng): lọc run đã xác minh theo kho/SKU/đơn vị, rồi chọn run mới nhất trong tập khớp.
- [x] C-8 Đăng ký model vào metadata Alembic (`alembic/env.py`, `app/models/__init__.py`); không trùng tên bảng. — Preflight 2026-11-22 (báo cáo của người dùng): kiểm tĩnh (không chạy): `alembic/env.py` import `app.models` và dùng `Base.metadata`; model mới đăng ký qua `app/models/__init__.py`. Ba tên bảng `order_analytics_jobs`, `order_analytics_order_checks`, `order_analytics_key_states` chưa xuất hiện trong mã/migration ở baseline.
- [x] C-9 Có test hợp đồng OpenAPI hoặc ma trận RBAC (ví dụ `tests/postgres/test_rbac_matrix.py`) liệt kê route/permission; có cần cập nhật khi thêm router không. — Preflight 2026-11-22 (báo cáo của người dùng): kiểm tĩnh (không chạy): có test ma trận quyền và test OpenAPI theo từng nhóm route. Không đổi bảng `PERMISSION_ROLES`; thêm test quyền cho ba route mới (admin/warehouse được đọc đúng quyền, client nhận 403).
- [ ] C-10 Số lượng đơn legacy (không có workflow) trong dữ liệu thử nghiệm, gồm số đơn `pending`/`approved` và tổng lượng còn phải giao, để chốt D-1. — Preflight 2026-11-22 (báo cáo của người dùng): DB test có 0 đơn tổng cộng, **chưa đủ dữ liệu** để kết luận về đơn legacy; D-1 đã chốt cho bản demo (mục 11), nên mục này không còn chặn `READY` của bản demo; vẫn chưa đo trên dữ liệu thật.
- [x] C-11 Quy tắc audit local cho worker. **Đã kiểm mã baseline `301260fb`:** `app/audit/models.py` yêu cầu `actor_user_id` không null và tham chiếu `users.id`; `app/audit/service.py` chỉ có `record_user_event` cho quản trị người dùng, đặt `target_type = 'user'`. Không có cơ chế actor hệ thống cho worker trong audit hiện có. **Người dùng đã tìm trong quy tắc local và không có kết quả. Xác nhận giữ nguyên audit nghiệp vụ; worker không ghi audit_logs.** Nếu không bắt buộc audit riêng: giữ nguyên audit nghiệp vụ, worker chỉ lưu trạng thái/thời điểm/mã lỗi của job, không ghi `audit_logs`. Nếu bắt buộc: duyệt cách định danh actor hệ thống và loại sự kiện, mở phạm vi và bổ sung test trước `READY`; không gán thao tác của worker cho khách hoặc một admin tùy ý.
- [x] C-12 Cấu hình lint/kiểm tra kiểu trong `pyproject.toml` (gói cho thấy `ruff`, line-length 100); có mypy không. — Preflight 2026-11-22 (báo cáo của người dùng): kiểm tĩnh (không chạy): `pyproject.toml` cấu hình Ruff, 100 ký tự/dòng, target `py312`; không thấy cấu hình mypy trong `pyproject.toml` hoặc workflow Quality.

**Kiểm thử và môi trường**

- [x] C-13 Có `TEST_DATABASE_URL` trỏ tới PostgreSQL dùng một lần, tên kết thúc `_test`, driver `postgresql+psycopg`. — Preflight 2026-11-22 (báo cáo của người dùng): DB chính đã dùng cho 93 test liên quan (PostgreSQL test cô lập). DB thứ hai cho test migration chuẩn bị trước khi chạy AC-14/test migration; **không chặn `READY`**.
- [ ] C-14 `python -m pytest -q` hiện đạt trước khi thay đổi (để có đường cơ sở hồi quy). — Preflight 2026-11-22 (báo cáo của người dùng): **chưa chạy** full backend suite. Chỉ có nhóm B2B/dự báo/bất thường/bổ sung: 93 pass (không thay thế đường cơ sở toàn bộ). Theo quyết định 2026-11-22: 93 test là mốc bắt đầu; full suite phải chạy và đạt trước khi chấp nhận bản vá, không còn chặn `READY`.
- [x] C-15 Workflow CI và Docker/compose (không có trong gói): cách chạy test và có cần khai báo worker hay không (triển khai vẫn ngoài phạm vi). — Preflight 2026-11-22 (báo cáo của người dùng): kiểm tra mã workflow (không phải một lượt chạy CI mới): Quality chạy Ruff, backend, Windows guards, frontend test/typecheck/build và E2E. Bản vá cần test cho worker nhưng không khai báo dịch vụ worker mới trong CI/Compose hay deploy.

**Frontend**

- [x] C-16 Mã hiện tại của `ReplenishmentRunPage.tsx`, `alert.ts`, `ForecastRunPage.tsx`, `AnomaliesPage.tsx`; kiểu `entity` có đủ `product_id`/`warehouse_id` chưa (task cảnh báo trước đó ghi TypeScript thiếu). — Preflight 2026-11-22 (báo cáo của người dùng): dùng khối demo sẵn có trên trang Bổ sung hàng làm màn demo; kiểu `entity` có `product_id` và `warehouse_id`.
- [x] C-17 `client/package.json` scripts (`typecheck`, `test:all`, `build`) và cấu hình `test:host` chạy được trên môi trường của bạn. — Preflight 2026-11-22 (báo cáo của người dùng): `typecheck`, `build`, Vitest và Node host test chạy được.
- [x] C-18 Bộ test frontend hiện đạt trước khi thay đổi. — Preflight 2026-11-22 (báo cáo của người dùng): 492 Vitest + 88 Node host test pass trước thay đổi.
- [x] C-19 Lược đồ `purchase_request_workflows` trên checkout đích: tên cột và kiểu của `decision_kind` và `decided_at`, giá trị `'approved'`, và `decided_at` có bao giờ NULL ở đơn đã duyệt không (đơn nào thiếu thì bị loại khỏi mẫu). — Preflight 2026-11-22 (báo cáo của người dùng): xác nhận cả hai: luồng duyệt ghi `decision_kind = 'approved'` và `decided_at`; ràng buộc không cho workflow đã duyệt thiếu timestamp. Không suy ra tình trạng dữ liệu thật. Quy tắc loại mẫu thiếu `decided_at` vẫn giữ như lớp phòng thủ.

## 13. Duyệt

Trước `READY`, người dùng xác nhận kết luận C-11 và duyệt phạm vi demo. Không yêu cầu worktree hiện tại phải sạch để duyệt tài liệu; điều kiện C-1 về worktree sạch được kiểm ở worktree Git riêng trước khi áp hoặc thử patch. C-10 không chặn bản demo, C-14 vẫn phải chạy và đạt trước khi chấp nhận bản vá; DB thứ hai phải sẵn sàng trước khi chạy test migration ở AC-14. Không đánh dấu các bước đó khi chưa thực hiện.

- Người duyệt: Trương Quốc Toàn.
- Ngày duyệt: 2026-11-22 (giờ Việt Nam).
- Chỉ thị: “bạn cứ tự sửa code”. Duyệt triển khai phạm vi bản demo của task ở trên sau kết quả tìm quy tắc audit local không có kết quả; không thêm audit của worker, không commit/push/deploy.
- Quyết định D-1…D-7: áp dụng đúng bảng ở mục 11; D-2 không dùng fixture ROP cho màn vận hành.
