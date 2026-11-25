# score-fulfilled-b2b-anomalies — Tự chấm bất thường sau khi xuất đơn B2B

> Phạm vi duyệt cho bản sao cô lập, không vận hành thật.

## Metadata

- Status: DONE
- Phase: M9 vận hành, tích hợp có điều kiện
- Plan: `docs/superpowers/plans/2026-11-22-fulfilled-b2b-anomaly-scoring.md` (đã duyệt)
- Depends on: `docs/tasks/implement-b2b-purchase-requests.md`, `docs/tasks/build-demand-data-pipeline.md`, `docs/tasks/implement-anomaly-explanations.md`
- Created: 2026-11-22
- Started: 2026-11-22
- Completed: 2026-11-22

## Goal

Sau khi xuất kho thành công từ luồng fulfill B2B, tự động chấm đúng transaction và phiếu xuất bằng Isolation Forest đã được duyệt. Nếu thiếu mô hình thì báo rõ, không suy thành giao dịch bình thường hoặc tạo cảnh báo mẫu. Nếu mô hình gắn cờ và SHAP hợp lệ, nhân viên có quyền xem cảnh báo kèm đúng phiếu.

## Context

Tạo/duyệt đơn chưa phải xuất kho. Luồng B2B hiện commit tồn, phiếu xuất, transaction, provenance và trạng thái trong cùng transaction. Bộ M9 và link hiện tại chỉ phục vụ fixture, không có model vận hành đã duyệt. Kiểm tra đơn tạm tính khi tạo đơn vẫn là một tính năng khác, không dùng lại điểm/ngưỡng của nó.

## In Scope

- Với đúng lần fulfill mới: ghi một job bền trong transaction nghiệp vụ, worker riêng chỉ thấy và chạy sau commit; giữ quy tắc xử lý lại an toàn.
- Đọc dữ liệu theo thời điểm đã biết của lần xuất, phiên bản feature cố định, một artifact đã xác thực nguồn, định danh, digest và ngưỡng; suy luận Isolation Forest và SHAP ngoài API. Không đọc model do client cung cấp.
- Hai chế độ nghiệm thu: (A) chưa có model vận hành hợp lệ: trạng thái có lý do, không verdict/alert; (B) model đã xác thực, đã pin: kiểm luồng thật trên PostgreSQL dùng một lần bằng model tổng hợp do test tạo, không dùng fixture làm kết quả vận hành.
- Hiện kết quả/phiếu bằng đường dẫn đọc đúng quyền, không đổi review/fixture hiện tại.

## Out of Scope

- Không chấm đơn tạo hoặc đã duyệt nhưng chưa xuất, không xét phiếu xuất phi B2B, không backfill phiếu cũ (kể cả #2), không đổi cách trừ tồn/lập phiếu/duyệt đơn.
- Không huấn luyện khi xử lý request, không nhập model demo/ngưỡng mẫu vào vận hành, không dùng z-score thay thế, không phân tích dữ liệu thật hoặc tuyên bố độ chính xác thực địa.
- Không đụng DB thật, migrate hay triển khai máy đang chạy, không commit/merge/push từ lượt này. Backup, duyệt artifact vận hành, migration và chạy worker thật là các bước được phê duyệt riêng.

## Acceptance Criteria

- [x] AC-1 — Tạo/duyệt/từ chối và rollback không sinh job; fulfill mới commit sinh đúng một job theo transaction. Phát lại hoặc chạy đồng thời không tạo trùng phiếu/job; worker không nhìn thấy bản ghi chưa commit.
- [x] AC-2 — Thiếu model: kết thúc với `NO_APPROVED_MODEL` hoặc mã an toàn tương ứng; không retry vô hạn, không điểm/nhãn normal/alert. Artifact fixture/khác digest/khác feature spec không được dùng vận hành.
- [x] AC-3 — Trên DB test cô lập, artifact đúng phiên bản cho điểm thật, ngưỡng pin và SHAP nhất quán từ cùng score; `score > threshold` mới có thể tạo cảnh báo, không gắn cờ ở ngưỡng; vắng dữ liệu đầu vào hợp lệ không thay bằng 0. Retry không đổi phiên bản đã pin, không tạo alert trùng.
- [x] AC-4 — Luôn đúng phiếu theo `transaction.outbound_id` và workflow/provenance; test hai phiếu giống kho/SKU/lượng/thời điểm, một phiếu có ID trùng transaction nhưng không phải nguồn. Link đọc chỉ khi có cả quyền bất thường và lịch sử kho; client/ẩn danh bị chặn, không rò dữ liệu nghiệp vụ khác.
- [x] AC-5 — Worker chạy tiến trình riêng, phục hồi lease/lỗi tạm thời có hạn; migration chỉ thêm bảng mới, không tạo job từ phiếu cũ; kiểm thử snapshot trước/sau xác minh không thay đổi tồn, workflow hay kết quả demo/đánh giá.

## Verification Commands

### Focused

Tên test dự kiến: `python -m pytest -q tests/postgres/test_operational_anomaly_jobs.py tests/postgres/test_operational_anomaly_worker.py tests/postgres/test_operational_anomaly_migration.py tests/test_operational_anomaly_artifact.py`. Smoke API + worker riêng trên PostgreSQL dùng một lần; ghi bằng chứng 0009→head và DB upgrade/downgrade riêng.

### Regression

`python -m pytest -q` theo guard PostgreSQL và điều kiện Docker/Windows của repo. Nếu đổi UI: `npm run typecheck`, `npm run build`, `npm run test:all` ở `client/` và smoke role trên demo test riêng.

### Static and Diff

`python -m ruff check app tests alembic`, `git diff --check`; kiểm allowlist và không chứa model artifact/thông tin riêng.

## Progress Log

- 2026-11-22 — Soạn DRAFT ngoài repo. Chưa đổi code hoặc data.

- 2026-11-22 — Người dùng duyệt và chọn đúng task/plan. Xác nhận ba dependency DONE và quy tắc single-task; tách nhánh cloud, giữ nguyên scope và các task khác. Đã nạp và đối chiếu đúng Git commit 14520ce từ Windows trong bản sao cloud; không sửa Windows. DRAFT → READY → IN_PROGRESS.

- 2026-11-22 — RED/Green hoàn thành phạm vi implementation; queue, pin/digest, hai chế độ, quyền, link đúng và UI đã triển khai trong bản sao. IN_PROGRESS → VERIFYING. Chưa nghiệm thu toàn bộ, không bật vận hành thật.

## Verification Evidence

### Focused

- 123 ca Linux/PostgreSQL đạt gồm rollback, worker riêng, hai chế độ, checksum/giới hạn artifact, bằng ngưỡng không cảnh báo, SHAP cộng đúng, DB 0009→0010→0009 không backfill, drift/source và hồi quy B2B/M9. Một cảnh báo TestClient có sẵn.
- Smoke riêng bằng Uvicorn trên 127.0.0.1 và hai worker tiến trình khác trên DB dùng một lần: không model trả NO_APPROVED_MODEL; ca synthetic test có score thật vượt ngưỡng và mở đúng voucher khác ID giao dịch, client 403, API mặc định 404 với dữ liệu tổng hợp; tồn và bảng M9 giữ nguyên. Không liên quan phiếu #2 trên bất kỳ DB người dùng nào.

### Regression

- Frontend typecheck/build, 532 Vitest + 88 Node host tests đạt. Frontend dùng hợp đồng HTTP mô phỏng trong các test route.
- 1.843 ca Linux riêng biệt đạt qua hai lượt (1.589 + 254); lỗi biến môi trường Docker được xác nhận trên baseline và hết khi chạy tiếp với môi trường sạch. Ba ca riêng Windows không nằm trong tổng. Windows độc lập kiểm thử trình duyệt thật trên API/worker/PG riêng: no-model, flagged synthetic, phiếu đúng và client 403.

### Static and Diff

- Ruff và git diff --check đạt. Đóng gói diff trên đúng commit 14520ce, chưa commit/push/merge/deploy. Không có model, chứng cứ dữ liệu huấn luyện vận hành hoặc thông tin người dùng trong patch.

## Review Result

- Result: APPROVED cho phạm vi kiểm chứng cô lập.
- Findings: Review độc lập không còn finding bắt buộc. Không duyệt artifact vận hành.

## Completion Evidence

- 2026-11-22: VERIFYING → REVIEWING. Đối chiếu AC-1–5 với evidence Linux, Windows/browser và review độc lập. Real API/worker chọn đúng phiếu #400 dù hai phiếu nhiễu giống hình.
- 2026-11-22: REVIEWING → DONE cho phạm vi cô lập đã duyệt, không xác nhận dữ liệu/model vận hành. Bản vá cô lập trên 14520ce được chốt SHA256 f434779db3408ec4721d59328a70a9ba317c04fb83b250c5b63916a1060a0a5e. Không chấm lại lịch sử.
