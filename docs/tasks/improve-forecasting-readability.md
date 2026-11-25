# improve-forecasting-readability — Biểu đồ và thông tin dự báo dễ đọc

- Status: DONE
- Phase: Forecasting UX
- Plan: docs/superpowers/plans/2026-11-22-forecasting-readability.md
- Depends on: docs/tasks/implement-demand-forecasting.md; docs/tasks/pilot-warehouse-forecast-replenishment.md
- Created: 2026-11-22
- Started: 2026-11-22
- Completed: 2026-11-22

## Goal
Giúp người dùng đọc nhanh dự báo/thực tế và giới hạn khi demo, vẫn giữ bằng chứng và không nhầm kết quả giả với thực tế.

## Context
API dự báo có trang 20 dòng, 7 ngày có ngày đích trùng từ nhiều nguồn, actual có thể null. Chuỗi pilot 2 đơn vị/ngày là cố định và thử riêng. Chi tiết hiện có một heading Thông tin kết quả trong mã; không được mọc thêm khối lặp.

## In Scope
`client/src/features/forecasting`: list, detail, CSS và helper/test cục bộ; chart từ dữ liệu đã đọc, mã/copy, thông tin không lặp, ngôn ngữ và giới hạn. Browser cô lập với pilot.

## Out of Scope
Backend/API/dataset/model/mô phỏng/đơn chờ/phân quyền, UI bổ sung hàng, đổi package, mở quyền, chỉnh main/DB/deploy/push.

## Acceptance Criteria
- [x] AC-1 — Chart dự báo đứt/thực tế liền ở trước bảng, đúng run/trang/case/đơn vị/bước, null không thành 0, có trục/chú giải/ngày rõ; bảng vẫn đọc được.
- [x] AC-2 — Mã rút gọn 12–16 ký tự có tooltip và copy toàn chuỗi, link giữ toàn mã; duy nhất một thông tin kết quả, phân biệt nhãn sản phẩm/kho và không lặp tên/mã.
- [x] AC-3 — Nhãn tiếng Việt cho phương pháp, chỉ số; cảnh báo WAPE fixture không chứng minh độ chính xác thật và giải thích chuỗi hằng chỉ khi xác minh; thu gọn giới hạn, giữ toàn nội dung và bàn phím.
- [x] AC-4 — Focused/Regression, desktop/mobile, không sai trang chậm/role/research, không đổi use case hoặc số ca CI chính.

## Verification Commands
- Client `npm run typecheck`, `npm run build`, `npm run test:all`; focused ForecastingPage/ForecastRunPage.
- Browser Windows cô lập chính xác cặp pilot, link/copy, chart hai đường và ngày, toggle, keyboard/mobile; diff/check không chạm API/model.

## Progress Log
- 2026-11-22: READY → IN_PROGRESS, Toàn duyệt đúng task và scope, c660c4f + pilot DONE final SHA b6e6d94143bfe5228813f3f1430474034b506f842a32b2fde8841f9d6546bb01 (tree bf595f45ce6fa44dd504de76eef70f549e56ee6c).

- 2026-11-22: IN_PROGRESS → VERIFYING; đóng băng đúng 7 file UI/kiểm thử và 2 hồ sơ khóa phạm vi; browser Windows và full UI kiểm độc lập.

- 2026-11-22: VERIFYING → REVIEWING; nhận chứng cứ Chromium độc lập từ đúng tree kiểm thử.
- 2026-11-22: REVIEWING → DONE; chấp nhận AC-1…AC-4 ở demo, không thay backend/nguồn.

## Verification Evidence
- RED: biểu đồ chưa có ở màn hình trước triển khai. GREEN: 34 forecast focused, 591 Vitest / 55 file + 88 host, typecheck/build và scoped diff sạch. Giữ nguyên tập E2E/CI, endpoint, role và dữ liệu.
- Frozen tree `8863868728ec7e808812d4103e172ef391684e38` trên Windows Chromium độc lập, frontend preview cô lập 15911 đọc API pilot. Dữ liệu thực trong artifact giả lập: h1 trang 1 ngày 01–20/01/2022; h7 trang 2 ngày 09–11/01/2022 theo nhóm cùng bước đã hiển thị. Đường thực tế nét liền và dự báo nét đứt trùng giá trị 2 một cách trung thực, ghi rõ giới hạn WAPE 0% trên chuỗi giả. Unit test chứng minh actual null không bị chuyển thành 0, không gộp khác lead và bỏ phần xem cũ khi tải lựa chọn mới.
- Một khối thông tin kết quả; Sản phẩm/Kho tách dòng, bỏ mã trùng tên; mã danh sách rút gọn nhưng liên kết và clipboard là đủ chuỗi. Keyboard mở/đóng Lưu ý và sao chép mã; màn 390px biểu đồ không tràn. Không request ngoài hoặc ghi nghiệp vụ (trừ login kiểm thử). Bản đang chạy chính và pilot cũ không thay.

## Review Result
- Result: APPROVED
- Findings: none

## Completion Evidence
- Đạt AC-1…AC-4 trên bản thử cô lập. Biểu đồ chỉ mô tả trang/nhóm dữ liệu đang xem và không suy rộng độ chính xác từ dữ liệu cố định. Bản cuối chỉ sửa ledger so với freeze; không thay mã đã kiểm, API, mô hình, dữ liệu, main, runtime trước đó hoặc GitHub.
