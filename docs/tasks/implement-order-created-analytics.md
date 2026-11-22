# implement-order-created-analytics — Phân tích tạm tính khi tạo yêu cầu mua B2B

## Metadata

- Status: VERIFYING
- Phase: Phân tích tạm tính cho yêu cầu mua B2B
- Plan: docs/superpowers/plans/2026-11-21-order-created-analytics.md
- Depends on: docs/tasks/implement-b2b-purchase-requests.md; docs/tasks/implement-b2b-nearest-warehouse.md; docs/tasks/implement-demand-forecasting.md; docs/tasks/implement-anomaly-explanations.md; docs/tasks/implement-replenishment-alerts.md
- Created: 2026-11-21
- Started: 2026-11-22
- Completed: not completed

> **VERIFYING.** Thực hiện trên checkout Git độc lập từ `301260fb`, không thay đổi worktree Windows. Kết quả preflight không phải bằng chứng kiểm thử sau thay đổi.

## Goal

Ngay sau khi tạo thành công một yêu cầu mua B2B mới, ghi đúng một job bền vững cùng transaction với đơn; worker chạy sau commit để cập nhật, cho đúng cặp (kho, SKU), ba kết quả tạm tính: (1) ngữ cảnh dự báo gồm nhu cầu chờ giao hiển thị riêng, (2) kiểm tra bất thường của chính đơn theo quy tắc định lượng có nhãn "Kiểm tra đơn tạm tính", (3) tồn dự kiến (tồn thực − lượng `pending` + `approved`) phục vụ cảnh báo bổ sung theo ROP đúng phạm vi. Đơn chờ không phải giao dịch kho; không đổi tồn thực, không tạo đơn nhập, không đổi số dự báo nền.

## Context

- Task chỉ thực thi theo `docs/superpowers/plans/2026-11-21-order-created-analytics.md`, nơi chốt thiết kế, hằng số, ma trận trạng thái, lệnh xác minh và checklist xác minh trên checkout đích. Plan đó cũng là DRAFT chưa duyệt.
- Quan sát trên gói (chưa xác minh trên checkout đích): `PurchaseRequestService.create` ghi đơn rồi workflow trong một transaction do `_write` commit; replay trả trước nhánh tạo; `fulfill` giảm tồn và đặt `fulfilled` trong cùng commit; `approve` không giữ hàng.
- `FORECAST_READ`, `REPLENISHMENT_READ`, `ANOMALY_READ` chỉ cấp cho admin và warehouse; `client` không đọc được phân tích.
- Run replenishment `operational` hiện luôn là `fixture`, nên trên gói chưa có ROP vận hành hợp lệ nào cho màn vận hành; chấm điểm bất thường hiện chỉ có đường fixture và được xây cho sự kiện xuất; không có outbox/worker trong gói; `PurchaseRequestCreate` không có ngày cần hàng.
- Sáu hướng thiết kế đã được người dùng đồng ý ngày 2026-11-21 để soạn tài liệu; đó chưa phải phê duyệt thực thi.
- **C-11 (audit worker):** ở baseline, `audit_logs` yêu cầu `actor_user_id` là `User` có thật; helper hiện có chỉ ghi sự kiện quản trị người dùng. Đề xuất bản demo giữ nguyên audit nghiệp vụ và chỉ ghi trạng thái/mã lỗi của job, không ghi audit riêng cho worker nếu quy tắc local không bắt buộc. C-11 còn mở đến khi đối chiếu quy tắc local; nếu quy tắc bắt buộc, chốt thiết kế actor/sự kiện, phạm vi và test trong plan trước `READY`.

## In Scope

1. **Job bền vững:** bảng `order_analytics_jobs` (duy nhất theo `purchase_request_id`), ghi trong `PurchaseRequestService.create` chỉ ở nhánh tạo mới, cùng transaction; migration Alembic mới với revision cha lấy từ `alembic heads` trên checkout đích.
2. **Worker** chạy riêng sau commit: nhận việc có lease và `claim_token` mới mỗi lần nhận; mọi lần ghi kết quả hoặc đổi trạng thái kiểm tra token và lease (bằng `clock_timestamp()`) trong cùng transaction ghi; job hết lease ở lần nhận cuối chuyển `failed`, không nhận lần nữa; retry với backoff; khởi động lại an toàn; `40001` ở `REPEATABLE READ` thì rollback và chạy lại cả transaction; ghi trạng thái lỗi bằng mã ngắn.
3. **Đọc nhu cầu chờ giao và tồn dự kiến:** tổng `pending` + `approved` theo (kho, SKU), tách `pending`/`approved`; tồn thực và lượng chờ đọc bằng một câu lệnh SQL (cùng snapshot); sau từ chối hoặc xuất, lần đọc kế tiếp tự loại đơn; không thêm trigger vào `approve`/`reject`/`fulfill`. Bản demo chỉ tính đơn có workflow; đơn legacy (không có workflow) giữ nguyên và không được tính; có test bằng dữ liệu giả.
4. **Dự báo:** hiển thị nhu cầu chờ giao riêng, không gán vào kỳ, không đổi số dự báo nền, không huấn luyện lại; thiếu baseline phù hợp thì trả "chưa đủ dữ liệu".
5. **Bổ sung hàng:** màn vận hành chỉ cảnh báo khi có ROP vận hành hợp lệ (khớp SKU, kho, đơn vị; không `fixture`, không `research`); không có thì hiển thị "Chưa có ROP vận hành" và vẫn hiển thị tồn dự kiến; đối chiếu ROP fixture chỉ ở màn demo, có nhãn demo, không phát khuyến nghị vận hành; không tạo đơn nhập.
6. **Bất thường:** quy tắc robust z-score có thể kiểm thử, lịch sử đơn cùng kho và SKU được duyệt trước lúc tạo đơn đang chấm (`decision_kind = 'approved'` và `workflow.decided_at` trước thời điểm tạo đơn đang chấm, kể cả đơn nay đã `fulfilled`; không thay `decided_at` thiếu bằng ngày tạo), trong 180 ngày, tối thiểu 8 mẫu, ngưỡng `|z| > 3.5` (chưa hiệu chuẩn), lưu ở `order_analytics_order_checks` riêng khỏi `anomaly_alerts`; thiếu mẫu thì báo chưa đủ dữ liệu; MAD = 0 xử lý theo tỉ lệ cố định ghi trong plan.
7. **Thứ tự và phiên bản:** kết quả tổng hợp theo (kho, SKU) ghi bằng so sánh-và-ghi theo `row_version`; kết quả kiểm tra riêng của từng đơn không bị job của đơn khác làm mất.
8. **API và quyền:** ba endpoint đọc dưới `/order-analytics`, mỗi endpoint dùng đúng một quyền đọc hiện có; `client` bị từ chối.
9. **Giao diện:** gắn vào các màn hình dự báo, bổ sung hàng và bất thường hiện có; hiển thị Đang tính / Có kết quả / Chưa đủ dữ liệu / Cập nhật lỗi, thời điểm và nhãn tạm tính.
10. **Test** cho mọi mục trên, và ghi bằng chứng thật vào file task này.

## Out of Scope

- Deploy, cấu hình container/CI cho worker, nhắn tin hoặc email.
- Sửa, di chuyển hoặc xóa đơn legacy (không có workflow); đo đơn legacy trên dữ liệu thật.
- Sửa workflow `approve`/`reject`/`fulfill`, logic xuất kho, `PERMISSION_ROLES` hoặc phân quyền; cấp quyền phân tích cho `client`.
- Thay mô hình, catalog hay artifact đã công bố; huấn luyện lại; ghi đè artifact demo.
- Dùng mô hình/fixture bất thường hiện có cho đơn B2B; ghi vào `anomaly_runs`/`anomaly_alerts`.
- Gán nhu cầu chờ giao vào kỳ dự báo; cộng gộp vào số dự báo nền.
- Tự tạo đơn nhập hoặc đơn đặt mua; trừ tồn thật lúc tạo hoặc duyệt.
- Dùng dữ liệu fixture/demo như dữ liệu vận hành; dữ liệu kho thật, `.env`, token.
- `git commit`, `push`, pull request hoặc đổi lịch sử Git khi chưa có yêu cầu riêng.

## Acceptance Criteria

- [ ] AC-1 — Qua điểm vào tạo đơn thật, một phản hồi 201 sinh đúng một dòng job `queued`; `stocks`, `stock_transactions`, `inbounds`, `outbounds` không đổi; request không gọi catalog, mô hình hay phép phân tích.
- [ ] AC-2 — Replay cùng khóa idempotency và cùng nội dung trả 200 mà vẫn chỉ một job; cùng khóa khác nội dung trả 409 và không thêm job.
- [ ] AC-3 — Phản hồi 4xx (404, 409, 422) và rollback sau khi thêm job không để lại đơn lẫn job; retry deadlock/serialization kết thúc với đúng một job.
- [ ] AC-4 — Worker xử lý job hợp lệ: job `succeeded`, có kết quả kiểm tra đơn và trạng thái ngữ cảnh theo (kho, SKU); chạy lại không tạo dòng trùng.
- [ ] AC-5 — Worker retry và khởi động lại: mỗi lần nhận job cấp một `claim_token` mới; mọi lần ghi kết quả hoặc đổi trạng thái job kiểm tra token và lease còn hạn trong cùng transaction ghi, so lease bằng `clock_timestamp()` (giờ thực lúc kiểm tra, không phải `now()` là giờ bắt đầu transaction); lỗi một bước giữ kết quả các bước khác, job trở lại `queued` với `attempts` tăng; lease hết hạn thì job được nhận lại nếu `attempts < max_attempts`; khi worker A hết lease và B nhận lại job, A quay lại không ghi được kết quả, `key_states` hay trạng thái job và không làm đổi dòng của B; transaction của A mở trước hạn lease nhưng kiểm tra sau hạn vẫn bị từ chối; worker chết ở lần nhận thứ `max_attempts` (thứ 5) thì khi lease hết hạn job chuyển `failed` với mã `LEASE_EXPIRED`, không được nhận lần thứ 6 và không kẹt `running`, worker cũ quay lại cũng không ghi được; PostgreSQL báo `40001` ở `REPEATABLE READ` thì rollback và chạy lại toàn bộ transaction từ đầu; đạt `max_attempts` do lỗi xử lý thì `failed` với mã lỗi ngắn; mỗi chức năng có trạng thái riêng.
- [ ] AC-6 — Nhu cầu chờ giao bằng tổng `pending` + `approved` theo (kho, SKU), tách hai loại, không tính `rejected`/`fulfilled`; số dự báo nền không đổi; phản hồi không có trường gộp dự báo + đơn chờ; thiếu baseline phù hợp thì trả chưa đủ dữ liệu, không trả số. Đơn legacy (không có workflow) được tạo bằng dữ liệu giả trong test (đánh dấu synthetic, không ghi vào dữ liệu dùng chung) không được tính vào lượng chờ giao và không bị sửa, di chuyển hay xóa.
- [ ] AC-7 — Tồn dự kiến = tồn thực − lượng chờ giao: ví dụ tồn 10, `pending` 5, `approved` 3 → dự kiến 2 và tồn thực vẫn 10; số âm được giữ nguyên; thiếu dòng tồn trả chưa đủ dữ liệu, không mặc định 0.
- [ ] AC-8 — Sau từ chối, lần đọc kế tiếp loại đơn khỏi lượng chờ; sau xuất kho, tồn giảm đúng một lần, đơn rời lượng chờ và không bị trừ lần hai trong tồn dự kiến; diff không sửa `approve`, `reject`, `fulfill`.
- [ ] AC-9 — Tồn thực và lượng chờ được đọc cùng một snapshot: kiểm thử đồng thời với xuất kho không bao giờ thấy (tồn mới + đơn còn `approved`) hay (tồn cũ + đơn `fulfilled`).
- [ ] AC-10 — Màn vận hành chỉ cảnh báo khi có ROP vận hành hợp lệ (khớp SKU, kho, đơn vị; không `fixture`, không `research`; không warmup; ROP hữu hạn không âm); ROP fixture không bao giờ tạo cảnh báo vận hành — màn báo "Chưa có ROP vận hành" và vẫn hiển thị tồn dự kiến; đối chiếu fixture chỉ ở màn demo, mang nhãn demo, không phát khuyến nghị vận hành; ROP null/NaN/âm, ngày warmup, run `research`, sai SKU/kho/đơn vị, thiếu binding đều không có khuyến nghị; không tạo đơn nhập.
- [ ] AC-11 — Kiểm tra bất thường dùng quy tắc ở plan với vector kiểm thử cố định, nhãn "Kiểm tra đơn tạm tính"; mẫu lịch sử "đã duyệt" yêu cầu `decision_kind = 'approved'` và `workflow.decided_at` trước lúc tạo đơn đang chấm, kể cả khi đơn lịch sử nay đã `fulfilled`; đơn tạo trước nhưng duyệt sau không lọt vào mẫu, kể cả khi worker chạy lại; `decided_at` thiếu thì loại khỏi mẫu, không thay bằng ngày tạo; dưới 8 mẫu báo chưa đủ dữ liệu; `anomaly_runs`/`anomaly_alerts` không đổi và `anomalies/scoring.py` không bị gọi.
- [ ] AC-12 — Hai đơn A, B cùng (kho, SKU) xử lý theo thứ tự đảo ngược: kết quả kiểm tra riêng của A và B đều đúng và không phụ thuộc thứ tự; chạy lại job sau khi đơn khác được duyệt muộn hơn hoặc một đơn trong mẫu chuyển `approved`→`fulfilled` không đổi mẫu và kết quả của đơn đã chấm; ghi tổng hợp của worker đọc `row_version` cũ bị từ chối và tính lại, không ghi đè kết quả mới; `40001` được xử lý bằng rollback và chạy lại từ đầu; trạng thái cuối là mới nhất.
- [ ] AC-13 — Mỗi endpoint chỉ cho đúng quyền đọc tương ứng (admin, warehouse); `client` nhận 403 trên cả ba; chưa đăng nhập hoặc người dùng không hoạt động nhận 401; dữ liệu cô lập theo kho/SKU; payload không lộ định danh khách.
- [ ] AC-14 — Migration mới nâng được từ head đã xác minh và hạ lại được; ràng buộc duy nhất, khóa ngoại và chỉ mục tồn tại; `down_revision` khớp `alembic heads` của checkout đích.
- [ ] AC-15 — Test tạo đơn, phân quyền, tồn kho, dự báo, bất thường, bổ sung hàng và frontend hiện có vẫn đạt; build frontend thành công. Mốc bắt đầu: 93 test nhóm B2B/dự báo/bất thường/bổ sung đã pass; bộ test backend đầy đủ (`python -m pytest -q`) phải chạy và đạt trước khi chấp nhận bản vá; kết quả full suite trước thay đổi chưa biết nên mọi lỗi full suite phải được xác định là có sẵn trên baseline hay do bản vá.
- [ ] AC-16 — Diff nằm trong allowlist của plan; không có `.env`, token, dữ liệu kho thật; không ghi đè artifact demo; dữ liệu demo luôn có nhãn demo; không commit, push hay deploy.

## Verification Commands

Đề xuất, chưa chạy. Xác minh scripts và công cụ trên checkout đích trước khi dùng.

### Focused

```bash
alembic heads
python -m pytest -q tests/test_order_analytics_rules.py tests/test_order_analytics_api.py
python -m pytest -q tests/postgres/test_order_analytics_jobs.py tests/postgres/test_order_analytics_worker.py tests/postgres/test_order_analytics_migration.py
cd client
npm.cmd run test:all
```

Lệnh PostgreSQL yêu cầu `TEST_DATABASE_URL` trỏ tới DB dùng một lần có tên kết thúc `_test`.

### Regression

Bắt buộc trước khi chấp nhận bản vá; full suite chưa chạy ở preflight.

```bash
python -m pytest -q
alembic upgrade head
alembic downgrade -1
alembic upgrade head
cd client
npm.cmd run typecheck
npm.cmd run build
```

### Static and Diff

```bash
ruff check .
git diff --check
git status
git diff
git diff --staged
```

Kiểm tra thủ công trên diff: chỉ `create` trong `app/purchase_requests/service.py` thay đổi; không có thay đổi trong `approve`, `reject`, `fulfill`, `PERMISSION_ROLES`, `app/anomalies/*`, catalog hay artifact demo.

## Progress Log

- 2026-11-21 — DRAFT (soạn lại theo cấu trúc chuẩn): task được soạn lại từ bản đề xuất ban đầu cùng sáu hướng thiết kế người dùng đồng ý, kèm plan độc lập `docs/superpowers/plans/2026-11-21-order-created-analytics.md`. Chưa chuyển `READY`, chưa có plan được duyệt, chưa sửa mã nguồn, chưa chạy lệnh nào, chưa xác minh trên checkout đích. Mục 12 của plan là checklist cần người dùng duyệt trước `READY -> IN_PROGRESS`.
- 2026-11-21 — DRAFT (chỉnh D-2): màn vận hành không dùng ROP fixture để cảnh báo; thiếu ROP vận hành thì báo "Chưa có ROP vận hành"; đối chiếu fixture chỉ ở màn demo có nhãn. Cập nhật Phạm vi mục 5, ngữ cảnh và AC-10; làm rõ phạm vi quy tắc bất thường (mục 6). Vẫn DRAFT, chưa duyệt, chưa xác minh trên checkout đích.
- 2026-11-21 — DRAFT (chỉnh worker và lịch sử bất thường): thêm `claim_token` + kiểm tra lease trong cùng transaction ghi, rollback và chạy lại khi `40001`; mẫu "đã duyệt" dùng `decision_kind`/`workflow.decided_at` thay vì chỉ `created_at` và trạng thái hiện tại. Cập nhật Phạm vi mục 2 và 6, AC-5, AC-11, AC-12. Tên cột `decision_kind`, `decided_at` chưa xác minh trên checkout đích. Vẫn DRAFT, chưa duyệt.
- 2026-11-21 — DRAFT (chốt mặc định, chỉnh lease): chốt giới hạn chạy lại `40001` dùng chung 3 vòng và cửa sổ 180 ngày theo `created_at` của đơn lịch sử; kiểm tra lease bằng `clock_timestamp()`; thêm ca worker chết ở lần nhận thứ 5 (hết lease → `failed`, không nhận lần thứ 6, không kẹt `running`). Cập nhật Phạm vi mục 2 và AC-5. Giữ `DRAFT` đến khi C-1…C-19 của plan được kiểm tra trên checkout đích và bạn duyệt.
- 2026-11-22 — DRAFT (ghi preflight): ghi bằng chứng preflight trên baseline `301260fb` (một head Alembic `20261113_0007`, 5 dependency `DONE`, backend nhóm liên quan 93 pass, frontend 492 + 88 pass, typecheck/build pass). C-14 (full backend) chưa chạy; C-10 chưa đủ dữ liệu (0 đơn). Vẫn `DRAFT`, chưa duyệt, chưa sửa mã.
- 2026-11-22 — DRAFT (chốt D-1 demo, mốc kiểm thử): chỉ đơn có workflow vào lượng chờ giao, đơn legacy giữ nguyên, thêm test dữ liệu giả (AC-6); 93 test nhóm liên quan là mốc bắt đầu, full backend suite phải chạy trước khi chấp nhận bản vá (AC-15); ghi rõ DB test đang trống (0 đơn) và full backend chưa chạy. Vẫn `DRAFT`, chưa duyệt mục 13, chưa sửa mã.

- 2026-11-22 — DRAFT -> READY. Người dùng tìm quy tắc audit local không có kết quả rồi giao “bạn cứ tự sửa code”; ghi mục 13 plan. Xác minh checkout triển khai sạch tại `301260fb`, năm dependency DONE, Alembic cha `20261113_0007` theo baseline đã xác minh; đối chiếu phạm vi, AC và lệnh kiểm.
- 2026-11-22 — READY -> IN_PROGRESS. Đóng băng scope theo plan đã duyệt; worker không ghi `audit_logs`. Kiểm thử đầy đủ sau thay đổi vẫn bắt buộc.

- 2026-11-22 — IN_PROGRESS -> VERIFYING. Đã ghép migration/ghi job cùng transaction, worker với claim guard và kiểm tra đơn, API đọc tạm tính đúng quyền, và ba khối giao diện. Bản vá chỉ gồm mã; tài liệu duyệt đi riêng. Đang kiểm hồi quy đầy đủ trên DB dùng một lần.

- 2026-11-22 — VERIFYING -> IN_PROGRESS. Full backend phát hiện test ranh giới kiến trúc do router mới import SQLAlchemy trực tiếp; sửa về kiểu dependency như router hiện có.
- 2026-11-22 — IN_PROGRESS -> VERIFYING. Kiểm lại test kiến trúc, API/quy tắc, Ruff và áp patch; không đổi hành vi runtime. Chưa chạy lại full backend trên bản đã sửa, giữ VERIFYING.

## Verification Evidence

### Preflight baseline (trước mọi thay đổi; báo cáo của người dùng 2026-11-22; không phải bằng chứng triển khai)

- Nhánh `feat/figma-ui-v2`, baseline `301260fb`; file task và plan đã ở đúng chỗ trong repo. Mã trong phạm vi đã kiểm không có diff; worktree hiện tại có thay đổi tài liệu. Chỉ áp hoặc thử patch trong worktree Git riêng, không stash hay xóa file hiện tại (C-1).
- Alembic: một head duy nhất `20261113_0007`.
- 5 dependency trực tiếp vẫn `DONE`.
- Backend, nhóm B2B/dự báo/bất thường/bổ sung: 93 pass; dùng làm mốc bắt đầu (quyết định 2026-11-22). **Full backend suite chưa chạy**; phải chạy và đạt trước khi chấp nhận bản vá (C-14).
- Frontend: 492 Vitest + 88 Node host test pass; `typecheck` và `build` pass.
- **DB test đang trống:** 0 đơn tổng cộng; chưa đủ dữ liệu để kết luận về đơn legacy (C-10). Bản demo chốt D-1: chỉ đơn có workflow vào lượng chờ giao, đơn legacy giữ nguyên, kiểm thử bằng dữ liệu giả.

### Focused

- `python -m pytest -q tests/test_order_analytics_api.py tests/test_order_analytics_rules.py`: 12 pass (API 3, quy tắc 9); xác minh quyền, demo ROP không lẫn vận hành, và nguồn ROP theo đúng run được chọn. Có một cảnh báo deprecation TestClient có sẵn.
- PostgreSQL 16 cô lập dùng một lần: bộ worker 9 test pass (lease hết hạn, token cũ, 40001, retry, lỗi từng bước, thứ tự ngược, hàng hết lease bị khóa không làm chặn job khác và được dọn ở lượt sau); bộ dữ liệu/migration cùng hồi quy PostgreSQL 157 test pass (9 mới, 148 hiện có; 201/replay/rollback, lỗi kết nối trước/sau commit, khóa retry, snapshot một câu lệnh trong xuất kho đồng thời, trạng thái/legacy, lịch sử chọn mẫu, nâng/hạ migration). Tập SQLite/model 71 test pass (không cộng vào tổng các tập).
- Không chạy với dữ liệu thật, không gọi Render và không triển khai.

### Regression

- `npm run typecheck`, `npm run build`, `npm run test:all` đạt: 498 Vitest và 88 Node host tests; có cảnh báo kích thước chunk Vite không chặn build. UI dùng mock tại biên API, không được tính là smoke trình duyệt tích hợp với worker thật.
- Full backend PostgreSQL: baseline UTC 1749 pass, 16 skip (Docker), 3 fail ở các ca dành cho Windows theo danh sách của workflow Quality. Bản vá trước sửa lỗi ranh giới router: 1777 pass, 16 skip, 4 fail (3 như baseline và 1 test kiến trúc của router mới). Đã sửa lỗi router và chạy lại test kiến trúc + API + quy tắc: 32 pass, Ruff và kiểm áp patch đạt. Chưa chạy lại toàn bộ backend sau sửa; không đánh dấu DONE.

### Static and Diff

- `python -m ruff check app tests alembic` và `git diff --check` đạt.
- `git apply --check Smart_Warehouse_Order_Analytics.patch` đạt trên checkout sạch tại `301260fb82afa0008d7ecf6c31512fdacdc30ad9`. Patch chỉ mã nguồn, không ghi đè task và plan local; hai tài liệu được cung cấp riêng.

## Review Result

- Result: PENDING
- Findings: not reviewed

## Completion Evidence

Chưa hoàn thành.
