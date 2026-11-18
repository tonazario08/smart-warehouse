# optimize-render-demo-loading — Giảm thời gian tải trang phân tích

## Metadata

- Status: VERIFYING
- Phase: Render demo
- Plan: docs/tasks/optimize-render-demo-loading.md#implementation-plan
- Depends on: none
- Created: 2026-11-18
- Started: 2026-11-18
- Completed: not completed

## Goal

Giảm thời gian xử lý và hiển thị dữ liệu Dự báo, Bổ sung hàng và Bất thường trên bản demo.

## Context

Trong phiên admin trên Render, nhóm API nghiệp vụ đo được 0,1–0,2 giây, còn danh sách Bất thường mất 7,9 giây và hai API Bổ sung hàng mất 4,8 và 4,7 giây. Phép đo này do chủ dự án thực hiện. Kiểm tra cục bộ với ZIP cùng SHA-256 như Render cho thấy xác minh Bất thường mất 16,0 ms một lần và 368,6 ms cho 20 dòng trong cùng lượt. Dự báo và Bổ sung hàng cùng thực hiện lại bước xác minh dữ liệu giữa trạng thái và danh sách.

## In Scope

- Xác minh payload Bất thường một lần cho mỗi lượt phân tích trong mỗi request danh sách, đồng thời kiểm tra từng bản ghi.
- Hiển thị trạng thái Dự báo và Bổ sung hàng ngay khi có kết quả, tách trạng thái tải danh sách. Giữ điều kiện gọi danh sách Bổ sung hàng và xử lý phản hồi cũ.
- Đo lại bằng cùng fixture; chuẩn bị so sánh trên Render sau khi được phép phát hành.

## Out of Scope

- Thay hợp đồng API, RBAC, dữ liệu nghiệp vụ hoặc điều kiện xác minh dữ liệu.
- Thay gói Render hoặc cấu hình triển khai. Commit, push và deploy cần được duyệt theo quy tắc repo.

## Acceptance Criteria

- [x] AC-1 — Mỗi trang Bất thường xác minh đầy đủ mỗi lượt đúng một lần và vẫn từ chối bản ghi hỏng.
- [x] AC-2 — Dự báo và Bổ sung hàng hiển thị trạng thái sớm, duy trì lỗi/thử lại và loại phản hồi muộn. Bổ sung hàng chỉ gọi danh sách khi trạng thái sẵn sàng.
- [x] AC-3 — Có test hồi quy, build và đối chiếu diff phạm vi task.
- [ ] AC-4 — Sau phát hành, đo lại cùng tài khoản và dữ liệu trên Render và xác nhận hiển thị trình duyệt.

## Implementation Plan

Task identifier: optimize-render-demo-loading. Chủ dự án duyệt xử lý điểm chậm trong phiên hiện tại.

1. Tạo test xác minh theo lượt cho API Bất thường rồi sửa `app/anomalies/service.py`. Tái dùng payload đã xác minh trong request và kiểm tra từng cảnh báo bằng logic hiện hành.
2. Thêm ca kiểm thử với danh sách còn chờ cho hai màn hình phân tích. Cập nhật hai component danh sách để tách kết quả trạng thái khỏi danh sách. Không dùng cache xác minh xuyên request.
3. Chạy kiểm tra đã khai báo, đo lại với artifact demo và ghi việc còn chờ trên Render.

## Verification Commands

- `.venv/Scripts/python.exe -m pytest -q tests/test_anomalies_api.py tests/test_anomalies_catalog.py tests/test_forecasting_api.py tests/test_replenishment_api.py`
- `npm.cmd run test:all`, `npm.cmd run typecheck` và `npm.cmd run build` trong `client`.
- `.venv/Scripts/python.exe -m ruff check app/anomalies/service.py tests/test_anomalies_api.py` và `git diff --check`.
- So sánh thời gian xác minh cục bộ trên cùng fixture Render. Sau khi phát hành, kiểm tra HTTPS bằng phiên admin và ghi thời gian cùng màn hình.

## Progress Log

- 2026-11-18. READY -> IN_PROGRESS. Đã xác định đường dẫn task và phạm vi tối ưu từ yêu cầu được duyệt. Giữ bản sửa tài liệu deploy và uv.lock có trước phiên này.
- 2026-11-18. Ba ca hồi quy thất bại trước khi sửa theo đúng kỳ vọng. Danh sách Bất thường xác minh hai lần cho hai cảnh báo cùng lượt; hai màn hình phân tích chưa hiển thị được trạng thái hoặc liên kết mới nhất khi danh sách còn chờ.
- 2026-11-18. IN_PROGRESS -> VERIFYING. Đã tái sử dụng payload xác minh trong cùng request Bất thường và hiển thị tiến độ tải theo phần ở Dự báo, Bổ sung hàng. Chờ kết quả kiểm tra đầy đủ.
- 2026-11-18. Kiểm tra cục bộ đạt khi dùng môi trường M9 có đủ phụ thuộc. Giữ VERIFYING vì AC-4 cần phát hành và đo trên Render. Chưa stage, commit, push hoặc deploy.
- 2026-11-18. VERIFYING -> IN_PROGRESS. Kiểm tra độc lập trước phát hành phát hiện liên kết kết quả mới nhất trong Bổ sung hàng biến mất khi danh sách tải xong, có thể làm mất focus bàn phím. Sửa trong phạm vi hiển thị tiến độ và thêm test duy trì focus.
- 2026-11-18. IN_PROGRESS -> VERIFYING. Test mới tái hiện mất liên kết. Sau khi sửa, liên kết giữ nguyên trong trạng thái sẵn sàng và reviewer xác minh lại không còn finding chặn phát hành. Chủ dự án duyệt review, commit và phát hành đúng bản tối ưu này trên nhánh Render.
- 2026-11-18. Đã commit bbd413e sau khi kiểm tra đúng phạm vi, bốn test API Bất thường và toàn bộ frontend, rồi push lên origin/codex/render-smart-warehouse-demo. GitHub Quality 44290505947 bắt đầu. Backend đầy đủ đang chạy trên PostgreSQL cục bộ cô lập. Hai dịch vụ Render có cấu hình tắt auto-deploy.
- 2026-11-18. VERIFYING -> IN_PROGRESS. GitHub Quality 44290505947 báo ca kiểm tra tuyến Bổ sung hàng cho warehouse đọc spy fetch ngay sau khi thấy tiêu đề. Tiêu đề không phụ thuộc API. Đồng bộ test theo nội dung do phản hồi trạng thái tạo ra và giữ kiểm tra request cũ.
- 2026-11-18. IN_PROGRESS -> VERIFYING. Reviewer xác nhận cả hai vai trò vẫn kiểm tra route, menu và request. Thay đổi bổ sung chỉ ở test, không ảnh hưởng mã runtime. Toàn bộ frontend test, typecheck và build đạt sau khi đồng bộ.

## Verification Evidence

- Lệnh pytest với bốn file đã khai báo trên Python 3.12 cho 24 pass và 5 lỗi setup vì thiếu SHAP. Chạy lại cùng bốn file từ worktree hiện tại với Python 3.14.2 trong venv M9 có SHAP cho 29 pass và hai cảnh báo deprecation.
- Trong `client`, `npm.cmd run test:all` đạt 492 Vitest trên 50 file và 88 host test. `npm.cmd run typecheck` và `npm.cmd run build` đạt. Vite vẫn báo chunk vượt 500 kB.
- Sau bản sửa focus, cả ba lệnh frontend tiếp tục đạt cùng số lượng test, gồm ca kiểm tra duy trì focus khi danh sách tải xong.
- `ruff check app/anomalies/service.py tests/test_anomalies_api.py` đạt. `git diff --check` đạt và Git báo CRLF sẽ chuyển LF ở tài liệu deploy đã sửa từ trước.
- `python -m pytest -q --tb=short` đạt 1.768 test bằng Python 3.14.2 với đủ phụ thuộc, PostgreSQL 16 riêng trên loopback và Alembic đến revision 20261113_0007. Đã tắt container kiểm thử sau khi chạy. Có hai cảnh báo deprecation.
- Đo cục bộ riêng đoạn xác minh với ZIP Render đã kiểm SHA-256, 20 cảnh báo trong một lượt có 383 cảnh báo. So sánh trung vị bảy lần, xác minh toàn bộ cho từng dòng mất 756,0 ms, xác minh một lần rồi kiểm từng dòng mất 29,0 ms. Hai cách trả cùng danh sách bản ghi đã xác minh.
- Chưa có kết quả đo lại trên Render vì chưa phát hành.

## Review Result

- Result: PENDING
- Findings: not reviewed

## Completion Evidence

Chưa hoàn tất.
