# polish-frontend-navigation-and-status — Điều hướng, nhãn và trạng thái
- Status: DONE
- Phase: Frontend UX
- Plan: docs/superpowers/plans/2026-11-23-frontend-navigation-and-status.md
- Depends on: docs/tasks/polish-replenishment-comparison-display.md
- Created: 2026-11-23
- Started: 2026-11-23
- Completed: 2026-11-23

## Goal
Vai trò nào cũng tìm đúng trang, hiểu tình trạng và đọc được trên desktop/mobile.

## Context
Baseline d0e11ce: thiếu mục Sản phẩm cho thủ kho, guard ẩn lý do, shell không có bỏ qua menu, Dashboard tổng sai ý nghĩa khi khác đơn vị và fixture Dự báo có thể nhìn thành vận hành.

## In Scope
Shell thật, điều hướng, phản hồi từ chối, tiêu đề/trạng thái/spacing, nhãn Dashboard và Dự báo.

## Out of Scope
Không đổi RBAC, API, runtime chính, dữ liệu, mô hình hoặc công thức; không sửa tác vụ riêng Bất thường/B2B/GIS; không viết đề cương, main hoặc push.

## Acceptance Criteria
- [x] AC-1 Menu đúng quyền của ba vai trò, thủ kho tìm được Sản phẩm; không hiển thị hoặc mở trang trái quyền, phản hồi rõ.
- [x] AC-2 Bàn phím bỏ qua điều hướng/focus, menu có nhãn và breadcrumb dễ đọc; không điều khiển giả, mobile 390px và desktop.
- [x] AC-3 Dashboard không hiển thị tổng khác đơn vị, đúng nguồn ngưỡng tồn thấp; Dự báo phân biệt fixture, nghiên cứu, vận hành.
- [x] AC-4 RED/GREEN, static/full UI và Windows Chromium độc lập theo vai trò; không đổi giao diện nghiệp vụ ngoài scope.

## Verification Commands
- Focused Vitest shell/routes/dashboard/forecast, npm run typecheck, npm run build, npm run test:all.
- Windows isolated read-only Chromium: desktop và 390px, role matrix và representative routes.

## Progress Log
- 2026-11-23: READY → IN_PROGRESS; đúng task Toàn duyệt, dependency DONE và exact d0e11ce061d8e2a1027ab43521d3cd99223365c6.
- 2026-11-23: IN_PROGRESS → VERIFYING; khóa bản UI để kiểm thử độc lập.

- 2026-11-23: VERIFYING → REVIEWING; tự động và Windows Chromium độc lập đạt.
- 2026-11-23: REVIEWING → DONE; chỉ ghi hồ sơ nghiệm thu.

## Verification Evidence
- RED 8 ca thất bại theo hành vi chưa sửa; bản cuối typecheck, build, 604 Vitest / 55 tệp, 88 kiểm thử host và kiểm tra khoảng trắng đạt. Playwright phát hiện 53 ca / 9 tệp; kiểm thử Chromium riêng ghi bên dưới.
- Windows Chromium độc lập trên cây `247de83ef1ea75d66ba7ebc73c6c356607dcb4ed`, preview cô lập 15919: admin, thủ kho, khách hàng × 1440/390/360 px; không tràn ngang toàn trang. Bỏ qua menu nhận focus, Enter/Escape đóng/mở và trả focus, đóng thông báo từ chối đưa focus về nội dung. Thủ kho có Sản phẩm và bị từ chối Dashboard; khách bị từ chối các trang không có quyền; trang bị chặn không gọi API cấm.
- Dashboard không còn tổng kho trộn đơn vị; tồn thấp là ngưỡng danh mục. Biểu đồ truy cập được và fixture Dự báo được gắn nhãn mô phỏng, tách bối cảnh đơn B2B. Không ghi dữ liệu nghiệp vụ và không có chỉnh sửa cấu hình vận hành.

## Review Result
- Result: APPROVED
- Findings: none

## Completion Evidence
- AC-1…AC-4 đạt. Delta cuối chỉ là hồ sơ task; không đổi mã đã kiểm, runtime, main hoặc push.
