# Biểu đồ đóng góp SHAP trên màn hình chi tiết bất thường

- Status: DONE
- Phase: Hoàn thiện giao diện demo
- Plan: docs/tasks/implement-shap-explanation-chart.md#implementation-plan
- Depends on: docs/tasks/implement-anomaly-explanations.md, docs/tasks/integrate-full-system-demo.md
- Created: 2026-11-16
- Started: 2026-11-16
- Completed: 2026-11-16

## Goal

Hiển thị đóng góp SHAP bằng thanh hai chiều quanh mốc 0 trên màn hình chi tiết bất thường. Người xem đọc được tên đặc trưng, chiều đóng góp và giá trị có dấu trên desktop và điện thoại.

## Context

API chi tiết đã trả thứ tự đặc trưng, giá trị đặc trưng, đóng góp SHAP, giá trị nền và sai số đối chiếu. Màn hình hiện hiển thị các đóng góp dạng danh sách. Demo 58082 đã có một cảnh báo tổng hợp có giải thích.

## In Scope

- Giữ phần giải thích trong panel hiện tại, dùng React và token CSS của dự án. Mốc 0 ở giữa; giữ cùng thang đo cho mọi hàng. Dấu và giá trị vẫn đọc được dưới dạng văn bản.
- Giữ trạng thái chưa có giải thích và kiểm tra dữ liệu không hợp lệ trước khi vẽ. Giữ thông tin giá trị nền, điểm mô hình và sai số đối chiếu.
- Kiểm thử frontend, review và kiểm tra giao diện thật trên demo 58082. Dựng lại web tại stack này khi có bản build mới.

## Out of Scope

- API, mô hình, RBAC, lưu dữ liệu, phiếu đánh giá và triển khai Render.
- Thêm thư viện biểu đồ, thay thiết kế toàn trang, sửa stack 58080 hoặc stage/commit/push.

## Acceptance Criteria

- [x] AC-1. Data hợp lệ hiển thị thanh dương về phải, âm về trái, 0 không có thanh. Cùng độ lớn dùng cùng chiều dài. Hiển thị tên, đóng góp có dấu và giá trị đặc trưng từ API.
- [x] AC-2. Dữ liệu không có giải thích hoặc thiếu/không hợp lệ hiển thị trạng thái phù hợp. Dữ liệu hợp lệ vẫn có giá trị nền, sai số và điểm được giải thích.
- [x] AC-3. Biểu đồ dùng được bằng văn bản, giữ cảnh báo giới hạn SHAP và đọc được tại 390 px và desktop.
- [x] AC-4. Test frontend, typecheck, build, kiểm tra diff và trình duyệt 58082 đạt. Review độc lập hoàn tất và ghi bằng chứng trong task.

## Verification Commands

- `npx.cmd --no-install vitest run src/features/anomalies/AnomalyDetailPage.test.tsx`.
- `npm.cmd run test:all`, `npm.cmd run typecheck`, `npm.cmd run build` tại client, và `git diff --check`.
- Dựng image web từ worktree, kiểm tra biểu đồ bằng Chromium tại 390 và 1440 px với cảnh báo có dữ liệu SHAP của stack 58082.

## Implementation Plan

Plan cho `implement-shap-explanation-chart`. Chỉnh trang chi tiết, CSS và test hiện có. Tiêu chuẩn hiển thị ở Goal, In Scope và Acceptance Criteria của task này.

1. Thêm ca kiểm thử dương, âm, bằng 0 và số liệu không hợp lệ; tái hiện chứng cứ thiếu biểu đồ trước khi sửa.
2. Giữ summary điểm, vẽ trục và thanh theo tỷ lệ tuyệt đối lớn nhất, giữ giá trị đọc được bằng chữ. Dùng layout tự co theo chiều rộng.
3. Chạy kiểm thử, dựng lại riêng web demo, đo ở hai kích thước và review diff. Ghi đường dẫn cảnh báo để quay.

## Progress Log

- 2026-11-16. READY. Người dùng chỉ định tạo và triển khai chính xác task này. Hai dependency đã DONE.
- 2026-11-16. READY -> IN_PROGRESS. Baseline `3f905bb` với các thay đổi hiện có. Không có diff trước đó trong feature bất thường. Demo giữ nguyên API và dữ liệu SHAP, chỉ dựng lại web sau khi có build.
- 2026-11-16. IN_PROGRESS -> VERIFYING. Bốn assertion mới thất bại trên giao diện cũ vì thiếu biểu đồ và thông báo dữ liệu lỗi. Đã thêm biểu đồ, kiểm tra dữ liệu đầu vào và CSS trong feature bất thường.
- 2026-11-16. VERIFYING -> IN_PROGRESS. Review sớm phát hiện tên đặc trưng ngoài hợp đồng có thể làm lỗi render thay vì hiện thông báo. Lần chạy regression đầu cũng có lỗi ở các suite khác khi chạy song song với khởi động Docker; sẽ kiểm tra lại với ít worker hơn.
- 2026-11-16. IN_PROGRESS -> VERIFYING. Đã tái hiện ba ca lỗi tên đặc trưng, gồm render lỗi với `__proto__`. Biểu đồ nay kiểm tra tập tên theo hợp đồng đặc trưng cố định hiện tại trước khi tra nhãn.
- 2026-11-16. VERIFYING -> IN_PROGRESS. Kiểm tra cùng dạng lỗi trên lý do không có giải thích, để mã lý do ngoài hợp đồng vẫn hiện thông báo dự phòng.
- 2026-11-16. IN_PROGRESS -> VERIFYING. Tái hiện lỗi render với lý do ngoài hợp đồng và bổ sung tra cứu an toàn trong nhánh không có giải thích.
- 2026-11-16. VERIFYING -> REVIEWING. Test tập trung, regression, typecheck, build, kiểm tra diff và Chromium với API thật đã đạt trên bản sửa cuối.
- 2026-11-16. REVIEWING -> DONE. Reviewer độc lập xác nhận finding đã sửa và không còn finding cần xử lý. Đã đối chiếu bốn acceptance criteria, diff và bằng chứng.
- 2026-11-16. Người dùng xác nhận chốt commit local riêng cho biểu đồ SHAP. Checkpoint gồm trang chi tiết bất thường, CSS, test và tài liệu này.

## Verification Evidence

- RED với Vitest theo file: 4 thất bại, 6 đạt trên giao diện cũ. RED theo tên đặc trưng: 3 thất bại. RED lý do ngoài hợp đồng: 1 thất bại. GREEN với `npx.cmd --no-install vitest run src/features/anomalies/AnomalyDetailPage.test.tsx --maxWorkers=1`: 14 đạt.
- Lần đầu `npm.cmd run test:all` có 480 đạt, 6 thất bại trước bước host test. Sáu lỗi nằm ở integration router, GIS, danh sách và form yêu cầu mua, chuyển kho, kho hàng. Với 2 worker, cả sáu đã đạt lần chạy sau (49/50 file, lỗi duy nhất là ca RED mới về lý do ngoài hợp đồng). Chạy lại bản cuối với 3 worker, giữ nguyên timeout và assertion.
- Bản cuối `npm.cmd run test:all` với `VITEST_MAX_WORKERS=3`: 490/490 Vitest trên 50 file và 88/88 host test.
- `npm.cmd run typecheck`, `npm.cmd run build`, `git diff --check` đạt trên bản sửa cuối. Build còn cảnh báo chunk trên 500 kB, diff chỉ có cảnh báo CRLF sẵn có.
- Dựng image `sw-full-demo-web:shap-chart` và tạo lại service web trên `58082` dùng API/database hiện có. Chromium đăng nhập quyền thủ kho, đọc chi tiết qua API thật, khớp cả 6 hàng (dương, âm và 0), kiểm tra vị trí, độ dài cùng thang đo, summary điểm và cảnh báo SHAP trong viewport 1440 px và 390 px.
- Cảnh báo demo: `http://127.0.0.1:58082/anomalies/alv1-003389fcf28308f7e6a1b6d1f9061b80507c007aff1567e2a49e3963404bc1b4`. Dữ liệu đầu vào là fixture tổng hợp, đóng góp do mô hình tính.
- Trước checkpoint, chạy lại `npx.cmd --no-install vitest run src/features/anomalies --maxWorkers=1` đạt 18/18 trên 2 file. Typecheck và build đạt, vẫn còn cảnh báo kích thước chunk.

## Review Result

- Result: APPROVED
- Review sớm: phát hiện P2 do tra nhãn tên đặc trưng ngoài hợp đồng. Đã sửa và kiểm thử ba trường hợp tên trước khi xác minh lại.
- Reviewer độc lập `shap_review` kiểm tra diff cuối so với `3f905bb`, xác nhận tập tên khớp hợp đồng, kiểm tra an toàn mã lý do và đối chiếu bằng chứng AC. Findings: không còn finding cần xử lý.

## Completion Evidence

DONE ngày 2026-11-16. AC-1 đến AC-4 đã xác minh. Vitest tập trung 14/14, regression 490/490, host 88/88, typecheck, build, diff và Chromium 1440/390 px đạt. Review độc lập APPROVED. Checkpoint local `feat: add SHAP explanation chart` chứa tài liệu này.
