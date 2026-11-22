# improve-replenishment-readability — Biết có cần xem xét đặt thêm hay không

- Status: DONE
- Phase: Replenishment UX
- Plan: docs/superpowers/plans/2026-11-23-replenishment-readability.md
- Depends on: docs/tasks/pilot-warehouse-forecast-replenishment.md; docs/tasks/extend-forecast-chart-window.md; docs/tasks/implement-replenishment-alerts.md
- Created: 2026-11-23
- Started: 2026-11-23
- Completed: 2026-11-23

## Goal
Đọc kết luận mô phỏng và căn cứ trước; demo trực tiếp 13, 14, 15 mà không lẫn với số kho.

## Context
Chuỗi fixture đã xác minh M6→M7 có ROP14, vị thế mô phỏng thật của artifact 9.986. Không gán lại số này để tạo cảnh báo giả.

## In Scope
UI Bổ sung: kết luận, công thức mô tả kết quả hiện có, link nguồn, EOQ fail-closed; danh mục bốn khái niệm riêng; ba phép đối chiếu minh họa không thay dữ liệu.

## Out of Scope
Không đổi backend/API/DB/mô hình/dataset/công thức, không tạo đơn nhập/mua/chỉnh tồn, không chỉnh runtime/push/main.

## Acceptance Criteria
- [x] AC-1 — Kết luận mô phỏng ở đầu. Cặp xác minh đúng nguồn/kho/SKU/đơn vị, ngày, horizon; ROP và EOQ giải thích dễ đọc, EOQ không có số nếu thiếu/bất hợp lệ đầu vào.
- [x] AC-2 — Ba phép minh họa 13 < 14, 14 = 14, 15 > 14; bằng/dưới gợi ý xem xét, trên báo chưa chạm. Giữ 9.986 của artifact, không kích hoạt workflow.
- [x] AC-3 — Phân biệt vị thế tồn mô phỏng, tồn thực, đơn khách chờ giao, hàng nhà cung cấp đang về; không nhập nhằng giữa pipeline mô phỏng và số thật.
- [x] AC-4 — Hồi quy UI focused/full, giữ role/links/nguồn dữ liệu; browser Windows độc lập; không thay API/CI/main/dataset.

## Verification Commands
- `npm run typecheck`, `npm run build`, `npm run test:all`; focused ReplenishmentRunPage / alert.
- Windows browser cô lập dùng artifact pilot đã xác minh; read-only, không tạo đơn.

## Progress Log
- 2026-11-23: READY → IN_PROGRESS; Toàn duyệt task và scope, dependency DONE; base c660c4f + chart-window final `a37061cea0b4c9b4e12620648da7faf4caacf07f`.

- 2026-11-23: IN_PROGRESS → VERIFYING; đóng băng source frontend, nghiệm thu trên browser độc lập.

- 2026-11-23: VERIFYING → REVIEWING; kiểm thử tự động và Windows Chromium độc lập đã đạt trên bản đóng băng.
- 2026-11-23: REVIEWING → DONE; chấp nhận bản demo theo phạm vi đã duyệt, chỉ cập nhật hồ sơ.

## Verification Evidence
- Frontend: RED tái hiện thiếu so sánh/ví dụ. `npm run typecheck`, `npm run build`, `npm run test:all` đạt (599 Vitest / 55 tệp, gồm 56 test liên quan; 88 host). Các ca thiếu/không hợp lệ chi phí không hiển thị số EOQ.
- Windows Chromium độc lập, cây `43ef94cba2eef2337cd582d0806020879414bf60`, preview cô lập 15915: vị thế tồn mô phỏng trong artifact 9.986 > ROP 14, XGBoost 7 ngày = 14 và tồn an toàn = 0; EOQ 86 khi đủ chi phí. Link mở đúng dự báo nguồn. Bốn khái niệm tồn/nhu cầu được tách, không gán số cho hàng nhà cung cấp chưa xác minh.
- Bàn phím desktop và chạm mobile 390 px: 13 < 14 và 14 = 14 → xem xét; 15 > 14 → chưa chạm ngưỡng. Đổi ví dụ không gửi yêu cầu, không đổi số mô phỏng đã lưu. Không có ghi dữ liệu nghiệp vụ hay request bên thứ ba.

## Review Result
- Result: APPROVED
- Findings: none

## Completion Evidence
- AC-1…AC-4 đạt. Ví dụ minh họa không phải tồn kho hay khuyến nghị vận hành. Delta hoàn tất chỉ thay hồ sơ task; không thay đổi source đã kiểm, backend, dữ liệu, runtime, main hoặc đẩy Git.
