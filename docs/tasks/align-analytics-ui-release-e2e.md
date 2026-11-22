# align-analytics-ui-release-e2e — Đồng bộ kiểm thử với giao diện đã duyệt
- Status: DONE
- Phase: Release verification
- Plan: docs/superpowers/plans/2026-11-23-analytics-ui-release-e2e.md
- Depends on: docs/tasks/polish-anomaly-score-display.md; docs/tasks/polish-frontend-navigation-and-status.md; docs/tasks/polish-replenishment-comparison-display.md
- Created: 2026-11-23
- Started: 2026-11-23
- Completed: 2026-11-23

## Goal
Các kiểm thử browser kiểm đúng nội dung và hành vi mới đã được duyệt.

## Context
Baseline c76b745 có ca thất bại do test còn dò chuỗi/tác vụ giao diện cũ.

## In Scope
Các tệp kiểm thử E2E Forecasting, Replenishment, helper logout.

## Out of Scope
Code sản phẩm, model/dữ liệu/API, dependency, cấu hình/guard CI, giảm mức bao phủ, sửa runtime.

## Acceptance Criteria
- [x] AC-1 Assertions mới xác nhận kho/SKU/nguồn, mã đầy đủ, fixture không bị gọi là vận hành, logout đúng màn hình.
- [x] AC-2 Giữ 53 ca/9 tệp, không bỏ assertion nghiệp vụ/mức bao phủ và không chỉnh guard.
- [x] AC-3 RED/GREEN browser độc lập Windows trên fixture thật; không ghi dữ liệu nghiệp vụ hoặc thay mã sản phẩm.

## Verification Commands
- Playwright collection 53/9, scoped cases qua Windows fixture cô lập và git diff --check.

## Progress Log
- 2026-11-23: READY → IN_PROGRESS; đúng task duyệt, dependency DONE, baseline c76b745d8ce104eeeff30d0ddbb701d379ced454.
- 2026-11-23: IN_PROGRESS → VERIFYING; khóa chính xác ba tệp E2E để kiểm thử độc lập.

- 2026-11-23: VERIFYING → REVIEWING; kiểm thử Windows độc lập đạt.
- 2026-11-23: REVIEWING → DONE; delta hoàn tất chỉ là hồ sơ task.

## Verification Evidence
- Baseline `c76b745d8ce104eeeff30d0ddbb701d379ced454`: RED do selector và kỳ vọng giao diện cũ trên fixture, không đổi logic ứng dụng.
- Bản `bcbde89f21346e96066c47051b59470062738689`: 112 Vitest liên quan đạt. Playwright collection vẫn đúng 53 ca / 9 tệp; tên, thứ tự và tệp giống baseline. Kiểm tra khoảng trắng đạt; không sửa guard hoặc cấu hình CI.
- Windows độc lập qua môi trường thử hỗ trợ 58081/58082: 6/6 ca thật trên trình duyệt đạt, gồm 2 ca Dự báo và 4 ca Bổ sung hàng. Phạm vi này không thay thế toàn bộ CI hosted.
- Backend immutable so với baseline có 1861 test đạt trên PostgreSQL cô lập; 16 ca Compose và 3 ca Windows xác minh riêng. Không sửa mã sản phẩm hoặc dữ liệu để làm test qua.

## Review Result
- Result: APPROVED
- Findings: none

## Completion Evidence
- AC-1…AC-3 đạt. Chỉ 3 tệp E2E và 2 tài liệu; cây cuối chỉ cập nhật hồ sơ khác bản browser đã kiểm. Chưa có kết quả CI hosted trong bước này.
