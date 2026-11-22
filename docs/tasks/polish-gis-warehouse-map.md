# polish-gis-warehouse-map — Chú giải, điều khiển và chỉ đường cho bản đồ kho

- Status: DONE
- Phase: M10, hoàn thiện trải nghiệm GIS
- Plan: docs/superpowers/plans/2026-11-22-gis-warehouse-map-polish.md (đã duyệt)
- Depends on: docs/tasks/improve-gis-route-usability.md, docs/tasks/open-gis-in-google-maps.md
- Created: 2026-11-22
- Started: 2026-11-22
- Completed: 2026-11-22

## Goal
Nhân viên nhanh chóng phân biệt điểm đến, kho đủ/thiếu tồn và tuyến A*, có thể dọn điểm hoặc đưa bản đồ về khung vùng, xem thông tin snapshot gọn và mở Google Maps riêng cho kho đã định tuyến.

## Context
Trang GIS đã có lớp OSM cùng nguồn, chọn vị trí, API warehouse-options và geometry tuyến. Server phân biệt ranked, geographic_only và excluded; chỉ insufficient_stock là có bằng chứng thiếu tồn. Dữ liệu thiếu không phải tồn bằng 0. Tồn đủ không có nghĩa tìm thấy đường.

## In Scope
- Chú giải và trạng thái kho trên cả bản đồ (tọa độ hợp lệ và trong khung) và thẻ kết quả. Dùng hình/mẫu và chữ, không chỉ màu. Dùng ngay payload hiện có.
- Hiển thị tóm tắt snapshot (nguồn, ngày/độ sẵn sàng, lớp mô phỏng nếu có); ID đầy đủ, profile/giấy phép để trong mục chi tiết, giữ attribution nhìn thấy.
- Hai hành động riêng: “Xóa điểm đến” bỏ tọa độ nhập/chọn và kết quả liên quan trong chế độ Tọa độ; “Về khung vùng” đưa viewport từ khung tuyến/zoom về vùng hiện tại, không đổi điểm, kho, tuyến hoặc gọi API lại.
- Link Google Maps theo từng lựa chọn ranked có hai endpoint hợp lệ. Giữ link trong chi tiết tuyến đã xác minh; không tự mở, không thêm link cho phương án khoảng cách địa lý, bị loại hoặc không có tuyến. Google tính tuyến riêng khi bấm.

## Out of Scope
Không đổi API/backend, stock, B2B/Haversine, A*, snapshot hoặc dữ liệu dựng tuyến, heatmap, geocoding/ETA/xe tải, tile/SDK ngoài, quyền. Không sửa hệ thống đang chạy, không merge/push/migrate. Không mở Google Maps với tọa độ người dùng để thử.

## Acceptance Criteria
- [x] AC-1: Điểm đến, kho đủ tồn, kho thiếu tồn và tuyến A* phân biệt bằng ký hiệu/chữ và còn đọc được khi hẹp. geographic_only ghi đủ tồn nhưng chỉ có khoảng cách địa lý; missing_stock ghi chưa có dữ liệu, không hiện như kho thiếu tồn. Điểm không có tọa độ hợp lệ không được vẽ. Chỉ geometry server vẽ tuyến; không tạo đường khi không tìm được.
- [x] AC-2: Snapshot tóm tắt gọn, giữ nhãn OSM hoặc mô phỏng phù hợp, chi tiết mở được, nguồn không phơi đường dẫn cục bộ. Không bỏ cảnh báo stale/invalid và attribution.
- [x] AC-3: Về khung vùng có thay đổi khung hiển thị sau khi chọn khung tuyến/zoom, không sửa trạng thái truy vấn hoặc gửi lại; xóa điểm bỏ marker/latitude/longitude và toàn bộ kết quả cũ, hủy/loại response muộn. Tra phiếu chuyển kho chỉ đọc, không xóa kho lưu trong phiếu.
- [x] AC-4: Hai hàng ranked dùng đúng hai origin khác nhau và cùng destination; href đúng lat,lng, có no-referrer, không truy cập tự động. Bỏ link khi thiếu tọa độ hoặc kết quả không có tuyến. Các quyền hiển thị cũ không đổi.
- [x] AC-5: Kiểm frontend đầy đủ và smoke desktop/mobile trên bản cô lập; phân biệt OSM thật/fixture và đường A* với đường Google. Chỉ kiểm href fixture, không điều hướng ra ngoài.

## Verification Commands
- Trong client: npm run typecheck; npm run build; npm run test:all. Thêm ca Vitest kho đủ/thiếu/không dữ liệu và geographic_only, 2 chọn đường/URL, clear/race và recenter không thêm API.
- Playwright GIS cô lập khi có; ghi rõ trường hợp browser/OSM nào chưa chạy. git diff --check và audit scope frontend/tests/docs.

## Progress Log
- 2026-11-22: Soạn nháp ngoài repo, chưa đổi dự án.

- 2026-11-22: Người dùng duyệt đúng task và plan, chỉ demo cô lập. Dependency DONE. DRAFT → READY → IN_PROGRESS. Baseline 644afa4a71bcdc20616028c9023049c58cb48340 + bản vá GIS đã nghiệm thu SHA256 7248c57eddf32dd40f1ae733bb53dd84bfcb1afd36d26ff94c9d29661f91ca05. Không chạm hệ thống chính.
- 2026-11-22: RED tái hiện thiếu chú giải và nút xóa. Triển khai trong đúng phần frontend GIS và tests; không đổi backend/contracts. IN_PROGRESS → VERIFYING. Khóa bản vá sản phẩm để chạy kiểm thử browser Windows với catalog OSM thật; bản kết quả còn chờ.


- 2026-11-22: VERIFYING → REVIEWING. Kiểm xong chứng cứ frontend và trình duyệt Windows trên đúng bản vá sản phẩm đóng băng.
- 2026-11-22: REVIEWING → DONE. Review độc lập đối chiếu AC-1–5, không còn vấn đề cản trở. Chỉ nghiệm thu bản cô lập.

## Verification Evidence

- Client: 554/554 Vitest (27 GIS), 88/88 Node host; typecheck, build và diff check đạt. Playwright GIS phát hiện 6 ca; việc liệt kê không phải chạy toàn bộ 6 ca.
- Chromium Windows thật với API/DB thử riêng và snapshot OSM công cộng xác minh ở [task trước](improve-gis-route-usability.md), bản vá gộp đóng băng SHA-256 227f04ebf7ecb64f654828c287ac270df2bbc50ed9d563ce2cf7afd32e660b42. Desktop/mobile: hai kho đủ tuyến có hai href Google Maps khác nhau, không tự mở; kho thiếu tồn 2 đơn vị và kho chưa biết tồn không bị đánh dấu nhầm; metadata mở được. Thu gần tuyến và về vùng giữ lựa chọn, không gọi lại; xóa điểm ngăn phản hồi cũ thực từ backend xuất hiện lại. Không có request ngoài.
- Backend/A*/B2B không thay đổi so với bản GIS trước đã kiểm thử. Không xác nhận ETA/giao thông/xe tải hoặc mở Google Maps.

## Review Result

- Result: APPROVED cho bản chạy cô lập; không có finding cản trở.

## Completion Evidence

- AC-1–5 đạt. Bản vá cuối chỉ cập nhật ledger so với bản sản phẩm đã kiểm thử.
- Không merge/push/triển khai/migrate hoặc thay đổi hệ thống chính.
