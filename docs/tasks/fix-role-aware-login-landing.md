# fix-role-aware-login-landing — Trang đích đăng nhập theo vai trò
- Status: DONE
- Phase: Release verification
- Plan: docs/superpowers/plans/2026-11-23-role-aware-login-landing.md
- Depends on: docs/tasks/align-analytics-ui-release-e2e.md; docs/tasks/polish-frontend-navigation-and-status.md
- Created: 2026-11-23
- Started: 2026-11-23
- Completed: 2026-11-23

## Goal
Đăng nhập hợp lệ không hiện từ chối giả; giữ phản hồi thật khi cố truy cập trang trái quyền.

## Context
Cây b35fe2f (hosted 042473f) còn default /dashboard trong AuthPages; khách/thủ kho đi qua guard admin và lưu cảnh báo. Hosted 35 pass/17 skip/1 fail; test no-alert đúng.

## In Scope
Đích mặc định LoginPage thực tế và hồi quy trực tiếp liên quan.

## Out of Scope
Thay đổi quyền/guard, API, dữ liệu, CI, test counts, tích hợp tự động, môi trường chính, push.

## Acceptance Criteria
- [x] AC-1 Đăng nhập bình thường admin /dashboard, thủ kho /inventory, khách /products mà không có cảnh báo từ chối.
- [x] AC-2 Giữ đích nội bộ được yêu cầu; đích bị cấm vẫn báo đúng sau đăng nhập, không mount trang hoặc gọi API bị cấm.
- [x] AC-3 RED từng ghi nhận; 53/9 nguyên vẹn, scoped/full frontend và Windows Chromium thật đạt.

## Verification Commands
- Focused Vitest, npm run typecheck, npm run build, npm run test:all, Playwright scoped auth và collection.

## Progress Log
- 2026-11-23: READY → IN_PROGRESS; task duyệt đúng, dependency DONE, baseline b35fe2fefbefd2ab37aa016ab0f4ed79fa86927a.
- 2026-11-23: IN_PROGRESS → VERIFYING; khóa bản sửa để kiểm thử độc lập.

- 2026-11-23: VERIFYING → REVIEWING; bộ tự động và Chromium Windows độc lập đạt.
- 2026-11-23: REVIEWING → DONE; chỉ cập nhật hồ sơ nghiệm thu.

## Verification Evidence
- RED trên bản trước: hosted 042473f và Windows Chromium độc lập tái hiện test auth-client trả 1 cảnh báo thay vì 0; Vitest có hai trạng thái từ chối sai, với thủ kho và khách.
- GREEN trên `46d8fca1ef967c00083f56abc156743b35cc6c2f`: cửa sổ Windows Chromium với API/DB thử biệt lập chạy lại ca auth-client nguyên bản đạt 1/1 và sáu kiểm tra vai trò/đích riêng đạt. Đăng nhập thông thường đến đúng trang mà không bị báo từ chối; đích nội bộ hợp lệ giữ nguyên, yêu cầu Dashboard trái quyền vẫn báo từ chối và không gọi API bị cấm.
- 24 test router liên quan đạt, 614 Vitest / 55 tệp, 88 host, typecheck, build và diff check đều đạt. Playwright inventory vẫn đúng 53 ca / 9 tệp và bất biến về nội dung. Không có tuyên bố hoàn thành CI hosted cho bản sửa.

## Review Result
- Result: APPROVED
- Findings: none

## Completion Evidence
- AC-1…AC-3 đạt. Delta cuối chỉ thay hồ sơ task; không đổi mã đã kiểm, guard, RBAC, dữ liệu, main hoặc push.
