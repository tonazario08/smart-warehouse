# polish-replenishment-comparison-display — Làm gọn đối chiếu bổ sung hàng
- Status: DONE
- Phase: Replenishment UX
- Plan: docs/superpowers/plans/2026-11-23-replenishment-comparison-display.md
- Depends on: docs/tasks/improve-replenishment-readability.md
- Created: 2026-11-23
- Started: 2026-11-23
- Completed: 2026-11-23

## Goal
Đọc kết luận nhanh, không lặp số liệu và không đổi cách tính.

## Context
Bản thử a593411 đã kiểm có vị thế mô phỏng 9.986, ROP 14; cột ROP lấy min/max trong các ngày chấm của kịch bản.

## In Scope
Trình bày mã, định danh, ví dụ, đầu vào và kết luận đối chiếu, min/max ROP.

## Out of Scope
Backend/API, mô hình, dữ liệu, chính sách, vận hành, main hoặc push.

## Acceptance Criteria
- [x] AC-1 Mã rút gọn sao chép đầy đủ, sản phẩm và kho thành hai trường.
- [x] AC-2 Ví dụ 13/14/15 sát kết quả gốc, riêng nhãn minh họa; không có ghi hoặc request khi bấm.
- [x] AC-3 Bộ số tồn ghi một lần; hai phép so sánh có nhãn riêng và giữ guard đã có, thiếu tồn báo một lần không suy đoán.
- [x] AC-4 Bằng số thì một giá trị, khác thì thấp nhất/cao nhất rõ ràng; chú thích không phải (s,S) hay khoảng tin cậy.
- [x] AC-5 RED/GREEN, static và full UI, Windows Chromium độc lập; phạm vi thay đổi chỉ UI/task/plan.

## Verification Commands
- Focused Vitest qua màn chi tiết; npm run typecheck; npm run build; npm run test:all.
- Windows preview cô lập và chỉ đọc; bằng chứng phân biệt kịch bản đóng băng với mô phỏng response.

## Progress Log
- 2026-11-23: READY → IN_PROGRESS; đúng task Toàn duyệt; dependency DONE, baseline a593411b8312b701f5887910e1ff3c110c922073.
- 2026-11-23: IN_PROGRESS → VERIFYING; khóa bản UI để kiểm thử Windows độc lập.

- 2026-11-23: VERIFYING → REVIEWING; kiểm thử và Windows Chromium độc lập đạt trên bản đóng băng.
- 2026-11-23: REVIEWING → DONE; ghi kết quả nghiệm thu, không đổi mã.

## Verification Evidence
- RED tái hiện cách hiển thị ROP bằng nhau; GREEN 60 kiểm thử liên quan, 603 Vitest / 55 tệp, 88 host, typecheck, build và kiểm tra khoảng trắng đạt. Ca mô phỏng có tồn và đơn chờ giao xác nhận chỉ hiện một bộ số liệu; các nguồn không khớp không đưa ra kết luận thiếu căn cứ.
- Windows Chromium độc lập trên `7de8b3aab91487a56d42cdf510322b81771eadce`, preview cô lập 15917: artifact thực của bản thử hiển thị một giá trị 2; mã rút gọn và sao chép nguyên văn, link đi đúng dự báo nguồn, hai trường sản phẩm/kho riêng. Ví dụ đứng ngay sau kết quả gốc; chạm trên mobile 390 px không đổi artifact. API thật trả `STOCK_ROW_MISSING`, UI chỉ báo thiếu tồn một lần, không hiện kết luận. Không ghi dữ liệu nghiệp vụ.
- Kiểm thử riêng trong trình duyệt thay response GET của đúng một hàng từ 2/2 thành 2/5: hiện rõ Thấp nhất 2 / Cao nhất 5. Đây là mô phỏng để kiểm tra hiển thị, không phải dữ liệu của artifact, không sửa nguồn.

## Review Result
- Result: APPROVED
- Findings: none

## Completion Evidence
- AC-1…AC-5 đạt. Bước hoàn tất chỉ đổi hồ sơ task, không đổi mã đã nghiệm thu, runtime, dữ liệu, main hoặc push.
