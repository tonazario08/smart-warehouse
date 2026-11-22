# add-gis-landmark-picker — Chọn điểm đến theo tên địa danh

- Status: DONE
- Phase: M10, hoàn thiện trải nghiệm GIS
- Plan: docs/superpowers/plans/2026-11-22-gis-landmark-picker.md (đã duyệt cho demo cô lập)
- Depends on: docs/tasks/polish-gis-warehouse-map.md
- Created: 2026-11-22
- Started: 2026-11-22
- Completed: 2026-11-22

## Goal
Nhân viên tìm địa danh theo tên, chọn kết quả để thấy tên và ghim xác nhận, rồi chủ động bấm tìm kho. Không cần biết tọa độ trước. Tên/mã kho hiện trực tiếp trên bản đồ.

## In Scope
- Danh sách địa danh công cộng gọn, chỉ trong phạm vi bản đồ, tên/tọa độ/nguồn đã kiểm, attribution. Tìm theo tên hoặc tên thường gọi; chỉ chọn từ danh sách, nhập tay hoặc bấm bản đồ còn dùng được.
- Chọn không tự gửi yêu cầu. Đổi/xóa điểm hủy kết quả trước và bỏ phản hồi muộn; sửa tọa độ thủ công bỏ tên đã chọn. Cảnh báo rõ khi không có tên, vùng phủ hoặc nguồn thật; không bịa tên và không vẽ địa danh thật trên mạng đường giả.
- Nhãn kho dễ thấy và không che toàn bộ tuyến, hỗ trợ bàn phím và màn hình hẹp. Giữ trạng thái đủ/thiếu/không biết và cơ chế xem gần/về vùng.

## Out of Scope
Không geocoder địa chỉ, định vị trình duyệt, gọi tiles/OSM/Google tự động, backend/API/DB, A*, quyền, B2B/Haversine, tọa độ phiếu chuyển kho, mô hình. Không sửa runtime/main cũ, migrate, commit/push/merge hoặc công bố.

## Acceptance Criteria
- [x] AC-1: Tìm có dấu/không dấu, thấy gợi ý đúng nguồn; bàn phím chọn được; xác nhận tên và ghim cùng tọa độ hợp lệ, chưa gọi tìm kho trước khi bấm.
- [x] AC-2: Sửa bằng tay, đổi cách nhập hoặc xóa không giữ nhãn/ghim/kết quả cũ, không để phản hồi đến muộn xuất hiện lại. Tên không tìm được không biến thành tọa độ đoán.
- [x] AC-3: Dữ liệu địa danh kiểm được nguồn, giới hạn vùng; không làm giả OSM hoặc xuất thông tin người dùng. Tên kho nhìn thấy khi phù hợp, một số hẹp dùng mã ngắn; tooltip/lời đọc có tên đầy đủ.
- [x] AC-4: Frontend typecheck/build/test và kiểm trình duyệt cô lập desktop/mobile có nguồn công cộng. Không gọi mạng ngoài và không đổi tuyến hoặc quyền cũ.

## Verification Commands
- Client: npm run typecheck; npm run build; npm run test:all. GIS Playwright kiểm desktop/mobile với nguồn đã kiểm.
- git diff --check và rà chỉ frontend/dữ liệu công cộng được duyệt/tests/docs.

## Progress Log
- 2026-11-22: Người dùng chọn chính xác task này. DRAFT → READY → IN_PROGRESS. Dependency DONE. Baseline isolated exact 644afa4a71bcdc20616028c9023049c58cb48340 + verified cumulative GIS polish patch b26fa632d433ff0b77c2477efe6852756ae52ce0343c5785c323902d1b25d11a. Không thay runtime thật.
- 2026-11-22: Review nguồn độc lập: xác minh sáu đối tượng công cộng OpenStreetMap trong vùng phủ TP.HCM và giữ liên kết way riêng; đây là ghim đại diện/điểm bản đồ, không xác minh lối vào. Dữ liệu đính kèm trong frontend, runtime không gọi Nominatim. Ghi công OpenStreetMap và ODbL 1.0, không công bố trong lượt này.
- 2026-11-22: Đưa ba điểm đã đối chiếu tuyến A*/Dijkstra từ hai kho thử vào danh sách: Dinh Độc Lập (way 39598493), Bưu điện Trung tâm Sài Gòn (39514793), Nhà hát Thành phố (801710792). Ba địa danh khác không vào danh sách bản này vì hai tuyến thử không có đường trong đồ thị. Không cam kết mọi điểm/kho đều có tuyến.
- 2026-11-22: RED tái hiện không có tìm địa danh. Client đã bổ sung tìm tên, ghim xác nhận, tọa độ thủ công và nhãn kho. IN_PROGRESS → VERIFYING; product/test đóng băng. Typecheck/build, 31 test GIS và 558 Vitest đạt. Playwright khám phá 8 ca; browser Windows còn chờ chạy độc lập.


- 2026-11-22: VERIFYING → REVIEWING. Đối chiếu kiểm thử frontend và nghiệm thu độc lập trên trình duyệt thật Windows với bản vá đã đóng băng.
- 2026-11-22: REVIEWING → DONE. Đạt AC-1–4 trong bản cô lập và không còn vấn đề cản trở.

## Verification Evidence

- Client: 558/558 Vitest, 88/88 Node host, 31 kiểm thử GIS tập trung; typecheck/build/diff check đạt. Playwright tìm thấy 8 ca; việc liệt kê không đại diện cho việc chạy cả bộ.
- Chromium thật trên Windows: desktop và mobile, API/DB chỉ của demo, lớp OSM đã xác minh; bản vá gộp đúng SHA-256 5a7ceceaaabdb72e988125646f7ea1dca2ae2e67869cd001b2ba9616a8588267. Cả ba địa danh hoạt động với danh sách nội bộ. Desktop dùng bàn phím và tên không dấu chọn Dinh Độc Lập, tuyến A* 0,368805 km. Mobile chạm chọn Bưu điện Trung tâm Sài Gòn, tuyến 4,224398 km. Xác minh nhãn kho, ghim, tên xác nhận, nhập tay và xóa. Tìm tên và chọn gợi ý không gửi POST tìm kho trước khi bấm; không có request bên ngoài.
- Tọa độ là vị trí đại diện cho đối tượng OSM, không phải lối vào. Các tuyến đo chỉ áp dụng cho điểm/kho thử; không tuyên bố hỗ trợ tìm mọi địa chỉ, thời gian đến hoặc mọi tuyến có thể đi.

## Review Result

- Result: APPROVED trong bản sao cô lập, không có finding cản trở.

## Completion Evidence

- AC-1–4 đạt. Chỉ task ledger đổi so với bản sản phẩm đã kiểm thử; backend/A*/B2B và hệ thống chính không đổi.
- Không commit, merge, push, migrate hay thay đổi cấu hình/runtime trong bước nghiệm thu này.
