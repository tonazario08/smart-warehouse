# implement-b2b-outbound-anomaly-review — Kiểm tra bất thường sau khi xuất kho B2B

> Kế hoạch đã duyệt; triển khai demo ngoại tuyến ở bản sao checkout cô lập.

## Metadata

- Status: VERIFYING
- Phase: Mở rộng M9 (demo đồ án)
- Plan: `docs/superpowers/plans/2026-11-22-b2b-outbound-anomaly-review.md` (bản chốt thiết kế đã duyệt)
- Depends on: `docs/tasks/implement-b2b-purchase-requests.md`, `docs/tasks/build-demand-data-pipeline.md`, `docs/tasks/implement-anomaly-explanations.md`
- Created: 2026-11-22
- Started: 2026-11-22
- Completed: not completed

## Goal

Chứng minh có thể đi từ một đơn B2B đã thực xuất trong môi trường demo cô lập tới đúng cảnh báo Isolation Forest và giải thích SHAP của giao dịch xuất đó. Không phân tích yêu cầu chưa xuất như thể đã xuất.

## Context

Đề cương V2 mục 2.9 và 3.5 mô tả mô hình trên giao dịch xuất, ngưỡng chọn trên validation, đánh giá holdout, SHAP và luồng rà soát. Mục 2.10 và 3.7 tách việc Client gửi yêu cầu, Admin duyệt hoặc từ chối, và Admin hoặc Warehouse thực xuất. M5 có bộ trích xuất đọc-only xác minh giao dịch; M9 hiện chỉ đọc và nhập fixture có opt-in. Việc hai thành phần tồn tại chưa chứng minh đã nối được đường đi từ phiếu xuất đến cảnh báo.

## In Scope

- Demo trên PostgreSQL cô lập: đơn và tồn đầu kỳ được tạo bằng dữ liệu giả, nhưng thực hiện đúng luồng tạo, duyệt, thực xuất và commit của hệ thống.
- Batch ngoại tuyến sau commit dùng nguồn M5 đã xác minh và M9 hiện có. Đối chiếu dấu vết từ phiếu xuất đến đúng cảnh báo/giải thích trên màn Bất thường. Giữ nguyên cờ fixture, quyền đọc/đánh giá và nhãn synthetic.
- Ghi quy trình demo tái lập, bằng chứng tập dữ liệu và kiểm thử các trạng thái không có cảnh báo, chưa đủ dữ liệu và lỗi.

## Out of Scope

- Không xóa, đổi tên, đổi ngưỡng hay thay thế **Kiểm tra đơn tạm tính** (Robust Z-score trước phê duyệt). Đây là kiểm tra yêu cầu B2B, riêng với Isolation Forest + SHAP sau thực xuất. Không duyệt/chặn đơn do điểm bất thường hoặc gán giả giao dịch xuất cho đơn mới.
- Tự huấn luyện trong request, trigger tự động, job mới cần chạy trên production, huấn luyện/nhập dữ liệu vận hành, thay đổi Dự báo, Bổ sung hàng/ROP, bộ chọn kho trên UI và kết quả RQ1.
- Thay đổi tồn, phiếu xuất, đơn hay quyền từ bước chấm điểm/nhập/đánh giá. Không tuyên bố precision/recall thực tế hoặc kết luận nguyên nhân nghiệp vụ từ SHAP.

## Acceptance Criteria

- [ ] AC-1 — Chỉ Admin duyệt hoặc từ chối; chỉ Admin hoặc Warehouse thực xuất đơn đã duyệt. Tạo và duyệt chưa cho ra sự kiện xuất; từ chối, rollback và thực xuất thất bại cũng không. Sau commit xuất thành công, M5 đọc được đúng một sự kiện của lần xuất đã chọn; replay không nhân đôi.
- [ ] AC-2 — Dựa trên ID giao dịch đã xác minh cùng provenance, kho, sản phẩm, lượng, đơn vị và thời điểm. Cùng SKU/kho/lượng nhưng khác giao dịch không khớp. Mismatch/thiếu dấu vết/hỏng artifact không tạo link; danh mục công khai không lộ ID gốc hay dữ liệu khách.
- [ ] AC-3 — Fixture tái lập có đủ train/validation/holdout, không dùng nhãn test để chỉnh ngưỡng. Giao dịch demo xác định trước thực sự được Isolation Forest gắn cờ. SHAP hiển thị giá trị nền và đóng góp có dấu, tổng khớp score trong sai số 1e-8. Nếu SHAP lỗi, không tạo giải thích giả.
- [ ] AC-4 — Nhập lại đúng artifact đã xác minh không tạo run/cảnh báo trùng. Bước phân tích/nhập không sửa đơn, tồn, phiếu xuất hoặc giao dịch. Đợt không đủ mẫu không sinh cảnh báo; giao dịch đối chứng bình thường được định trước đủ điều kiện chấm và điểm không vượt ngưỡng. Chỉ admin/warehouse xem/đánh giá theo quyền M9; client bị từ chối. Không bật đường fixture trên môi trường vận hành.
- [ ] AC-5 — Demo màn Bất thường cho đúng cảnh báo và biểu đồ đóng góp có dấu; quản lý đánh giá được và lần đánh giá chỉ thay đổi hồ sơ cảnh báo. Nhãn synthetic và giới hạn phi nhân quả vẫn hiện rõ. Hồi quy chứng minh Dự báo, Bổ sung hàng, bộ chọn kho trên UI và Kiểm tra đơn tạm tính (Robust Z-score trước phê duyệt) vẫn hoạt động như trước; không nhầm kiểm tra tạm tính với cảnh báo sau thực xuất.

## Verification Commands

### Focused

- Có sẵn: `python -m pytest -q tests/test_anomalies_dataset.py tests/test_anomalies_scoring.py tests/test_anomalies_explanations.py tests/test_anomalies_catalog.py tests/test_anomalies_api.py`
- Đề xuất, chưa tồn tại: `python -m pytest -q tests/postgres/test_b2b_outbound_anomaly_demo.py`. Xem plan để biết môi trường và lệnh demo.

### Regression

- Có sẵn: `python -m pytest -q` với cấu hình PostgreSQL test cô lập theo quy tắc repo; xem nhóm B2B và M9 trong plan.
- Có sẵn, thư mục `client/`: `npm run typecheck`, `npm run build`, `npm exec -- vitest run`. Xác minh browser qua profile M9 theo quy tắc repo.

### Static and Diff

- `python -m ruff check .`, `python -m ruff format --check .`, `git diff --check`

## Progress Log

- 2026-11-22 — Soạn task và plan riêng, rà soát thiết kế theo đề cương V2 và mã nguồn hiện có. Chưa xác minh checkout đích, chưa chuyển READY, chưa sửa code hay chạy thử.

- 2026-11-22 — Người dùng chọn task này và cho phép triển khai kế hoạch đã lưu. Xác nhận cả ba dependency DONE, plan độc lập có ID đúng và spec M9; baseline 301260fb cộng bản vá analytics đã có, bản sao cloud tách biệt. PostgreSQL 16 test cô lập nâng schema đến 0008. Preflight ngoài repo: 1.200 giao dịch B2B fixture thật, 240 mẫu/tập, validation có 120 normal; điểm đích 0,7709 > ngưỡng 0,5289; SHAP sai số 2,22e-16; hai lần nhập chỉ có một cảnh báo khớp. Đây là bằng chứng khả thi, chưa phải nghiệm thu triển khai. DRAFT → READY sau khi duyệt, rồi READY → IN_PROGRESS.

- 2026-11-22 — RED: test tích hợp chưa tìm thấy demo runner. GREEN: thêm runner ngoại tuyến + test, không đổi app/client, schema hay dependency. Lệnh CLI và test PostgreSQL đã xác nhận exact link, SHAP và replay trên fixture. IN_PROGRESS → VERIFYING.

## Verification Evidence

### Focused

- PostgreSQL 16 cô lập: nhóm B2B outbound, M5 snapshot, M4 atomicity, M9 API/dataset/scoring/explain/catalog: **109 pass** (một cảnh báo deprecation TestClient). Chạy lại hạng mục mới sau hoàn thiện cổng DB: **5 pass** trên DB demo mới. Runner CLI bản cuối cũng chạy thành công trên DB demo riêng, cờ fixture bật trong integration, đăng nhập qua HTTP thật bằng ba tài khoản demo và từ chối client đọc/đánh giá.
- 1.200 giao dịch tổng hợp, 240 mẫu mỗi tập (240 normal validation). Giao dịch cố định 10.000 each: điểm 0,7708967677 > 0,5921413224; đối chứng 2 each: 0,5508822023 ≤ ngưỡng. SHAP residual 2,22e-16. Holdout tổng hợp: TP 8, FP 0, FN 0, TN 232; không suy rộng ra vận hành.
- Hai lần nhập cùng catalog đã xác minh giữ một cảnh báo đúng nguồn; admin/warehouse được đọc, client bị từ chối. Warehouse lưu đánh giá qua API; các bản ghi nghiệp vụ được đối chiếu trước/sau không đổi.

### Regression

- Frontend: typecheck/build đạt; 498 Vitest và 88 host tests đạt.
- Full backend: đang xác minh ở DB demo riêng. Smoke trình duyệt: **NOT VERIFIED**. Chromium không mở được Unix socket trong môi trường cloud, trước cả điều hướng; không dùng kết quả API để thay cho smoke trình duyệt.

### Static and Diff

- Ruff lint toàn checkout và kiểm tra định dạng hai file Python mới đạt; `git diff --check` sạch. Ruff format toàn checkout báo 61 file baseline chưa đúng định dạng; kiểm tra bản gốc cho cùng 61 file, không sửa ngoài phạm vi.

## Review Result

- Result: Đã có đọc chéo độc lập trong VERIFYING; chưa chuyển REVIEWING/DONE vì smoke trình duyệt chưa được xác minh.
- Findings: Đã sửa địa chỉ đăng nhập demo không hợp lệ, kiểm chứng đăng nhập qua HTTP; không còn phát hiện trọng yếu trong rà soát runner. Tách dữ liệu synthetic, khóa nguồn, vai trò B2B/M9 và bảo vệ DB riêng.

## Completion Evidence

Chưa có.
