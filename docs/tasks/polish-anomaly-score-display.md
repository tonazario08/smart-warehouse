# polish-anomaly-score-display — Trình bày điểm bất thường dễ kiểm chứng
- Status: DONE
- Phase: Frontend UX
- Plan: docs/superpowers/plans/2026-11-23-anomaly-score-display.md
- Depends on: docs/tasks/polish-frontend-navigation-and-status.md
- Created: 2026-11-23
- Started: 2026-11-23
- Completed: 2026-11-23

## Goal
Thấy đúng vì sao cảnh báo, cần kiểm tra gì và đâu là bằng chứng đã xác minh.

## Context
Baseline 404099c: giá trị điểm và ngưỡng rất gần có thể trông bằng nhau sau làm tròn dù quan hệ thô khác nhau.

## In Scope
Trình bày các điểm/ngưỡng và chi tiết Bất thường, demo và vận hành, xếp tóm tắt/việc kiểm tra/phiếu xác minh trước và kỹ thuật sau.

## Out of Scope
Mô hình, ngưỡng/chính sách, dữ liệu, API, RBAC, các luồng nghiệp vụ khác, B2B/GIS, runtime chính, main/push.

## Acceptance Criteria
- [x] AC-1 Quan hệ raw dưới/bằng/vượt rõ ràng; near-tie khác giá trị không hiển thị thành hai số bằng nhau; thiếu đầu vào không tự giả định.
- [x] AC-2 Lý do, việc đối chiếu và liên kết phiếu khi có xác minh ở đầu; giữ phân quyền, fallback và phân biệt demo/vận hành.
- [x] AC-3 Phần kỹ thuật thu gọn, có thể truy cập bằng bàn phím; không đổi diễn giải đóng góp thành bằng chứng nguyên nhân hoặc thay đổi đánh giá.
- [x] AC-4 RED/GREEN, kiểm tra typecheck/build/full frontend, Chromium Windows độc lập; các giả lập ghi rõ, không ghi dữ liệu nghiệp vụ.

## Verification Commands
- Focused Vitest bất thường; npm run typecheck; npm run build; npm run test:all.
- Windows Chromium cô lập, viewport desktop/mobile; không đọc dữ liệu thật hoặc ghi nghiệp vụ.

## Progress Log
- 2026-11-23: READY → IN_PROGRESS; đúng task Toàn duyệt, dependency DONE và baseline 404099c7af91c1dd6435a7c2e5d000c21c5288ff.
- 2026-11-23: IN_PROGRESS → VERIFYING; khóa bản UI để kiểm thử Windows độc lập.

- 2026-11-23: VERIFYING → REVIEWING; tự động và Windows Chromium độc lập đạt.
- 2026-11-23: REVIEWING → DONE; chỉ ghi hồ sơ nghiệm thu.

## Verification Evidence
- RED: 4 ca tái hiện lỗi; GREEN: 65 ca liên quan, 610 Vitest / 55 tệp, 88 host, typecheck/build và kiểm tra khoảng trắng đều đạt. Kiểm thử đơn vị bao phủ fixture và các trạng thái đánh giá; API cũ của bản thử không có endpoint đánh giá và danh sách cảnh báo fixture trống, nên không có bằng chứng Windows trực tiếp cho hai phần đó.
- Chromium Windows độc lập, preview cô lập 15921, cây `33957ce459381fea16d9cb3938cd8cd0cfa700c6`, desktop 1440 px và mobile 390 px: API kịch bản tổng hợp trả giao dịch #2 điểm 0.6314716915037257 > ngưỡng 0.6214716915037257; phiếu #400 đã xác minh mở được. Tóm tắt nghiệp vụ và liên kết trước phần kỹ thuật thu gọn, bàn phím mở được. Giao dịch #3 dưới ngưỡng có kết quả bình thường, còn #1 không có mô hình đã duyệt; cả hai không có liên kết phiếu.
- Mô phỏng GET chỉ trong trình duyệt: 0.592000001, 0.592 và 0.591999999 so với ngưỡng 0.592 hiện đủ chữ số và đúng vượt/bằng/dưới. Đây không phải dữ liệu gốc. Khách bị chuyển hướng, không có GET trang bị cấm; API chi tiết/phiếu trả 403. Không ghi dữ liệu nghiệp vụ hoặc gửi request ngoài.

## Review Result
- Result: APPROVED
- Findings: none

## Completion Evidence
- AC-1…AC-4 đạt; kết luận dựa trên quan hệ thô, không đổi mô hình, ngưỡng, phân quyền, dữ liệu hay chứng từ. Delta cuối chỉ thay hồ sơ task, không sửa mã đã thử, runtime, main hoặc push.
