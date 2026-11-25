# improve-gis-route-usability — Chọn điểm và đọc tuyến A* trên sơ đồ GIS

- Status: DONE
- Phase: M10, trải nghiệm bản đồ kho
- Plan: docs/superpowers/plans/2026-11-22-gis-route-usability.md (đã duyệt)
- Depends on: docs/tasks/implement-warehouse-gis.md, docs/tasks/open-gis-in-google-maps.md
- Created: 2026-11-22
- Started: 2026-11-22
- Completed: 2026-11-22

## Goal
Nhân viên chọn điểm đến trực quan trong GIS và đọc rõ tuyến A* tham khảo. Tuyến chuyển kho giữ điểm đi/đến từ phiếu. Google Maps là liên kết tùy chọn, tính tuyến riêng.

## Context
GIS đã có nhập tọa độ, lựa chọn kho/đơn, A* và sơ đồ SVG tự căn, kèm Google Maps. Đề cương V2 tách A* trên đồ thị đường khỏi xếp kho đủ tồn theo Haversine trong B2B. Phạm vi này không sửa luồng B2B.

## In Scope
- Điểm chọn trên sơ đồ nội bộ ở nhánh “Tìm theo tồn kho” / “Tọa độ”; đồng bộ tọa độ, fallback nhập tay và UI touch/keyboard.
- Nền đường tham khảo: một API cùng nguồn, chỉ đọc và có quyền GIS_READ, giới hạn dưới 2.500 đoạn từ snapshot OSM công cộng đã kiểm; không phát sinh dữ liệu khác. Không có nền thật thì giữ sơ đồ, không vẽ đường giả.
- Làm rõ tuyến A*, marker, chú giải, đường nối snap, chiều dài và nguồn snapshot trong cả hai chế độ GIS. Nhãn phân biệt OSM với dữ liệu tổng hợp.
- Giữ liên kết Google Maps bấm chủ động, nhắc tuyến bên đó tính riêng từ hai tọa độ. Kiểm tra URL với tọa độ fixture, không mở link chứa tọa độ thật.

## Out of Scope
Không sửa B2B/Haversine, A*/API định tuyến/migration, tọa độ gốc phiếu, quyền, geocoding/định vị, SDK/tiles/call bên ngoài, ETA/giao thông/xe tải, nhiệt dự báo hay runtime chính. Không gọi sơ đồ không nền đường là bản đồ đường phố. Không commit/push/merge/triển khai.

## Acceptance Criteria
- [x] AC-1: Click/tap trong bounds cho vị trí đúng, marker và hai trường đồng bộ; nhập tay dùng được. Không gửi trước khi bấm tìm. Sửa điểm xóa kết quả cũ và bỏ phản hồi đến muộn.
- [x] AC-2: Tuyến đúng hình học server, thứ tự GeoJSON kinh/vĩ độ, vừa khung; giữ điểm trùng nút và chiều dài 0; nét đứt nối snap không cộng vào chiều dài đường. Không vẽ đường giả khi không route được; lý do rõ.
- [x] AC-3: OSM ghi nguồn/giấy phép/ID; fixture ghi mô phỏng. Nền chỉ dùng nếu ID snapshot khớp tuyến/trạng thái và không có fixture đường. Google Maps chỉ gửi hai tọa độ khi bấm link, không iframe/preload/request tự động; nhãn phân biệt tuyến bên ngoài với kết quả A*.
- [x] AC-4: Kiểm thử staff/client, desktop/mobile trên bản sao; đối chiếu A* với Dijkstra test hiện có và với snapshot OSM công cộng nếu có. Không dùng graph giả để tuyên bố đã kiểm OSM thật.

## Verification Commands
- python -m pytest -q tests/test_gis_catalog.py tests/test_gis_osm.py tests/test_gis_routing.py
- Trong client: npm run typecheck; npm run build; npm run test:all. Smoke Playwright riêng, không truy cập Google Maps; kiểm URL bằng fixture.
- git diff --check và kiểm phạm vi chỉ frontend GIS, một endpoint nền chỉ đọc, tests, task/plan.

## Progress Log
- 2026-11-22: Nháp ngoài repo; chưa triển khai.

- 2026-11-22: Người dùng duyệt task và plan, gồm nền OSM công cộng có kiểm chứng, không đổi A*. DRAFT → READY → IN_PROGRESS. Hai dependency DONE. Bản sao dùng exact 4982123 và bản vá review đã kiểm chứng (chờ xác định object Windows 644afa4).

- 2026-11-22: Đối chiếu Git bundle và kiểm đúng commit 644afa4a71bcdc20616028c9023049c58cb48340; bản vá chỉ gồm phạm vi GIS. RED: gọi lớp nền trả 404 trước implementation, kể cả khi API trạng thái chạy.
- 2026-11-22: Rerun backend 97 ca (API, lớp nền, catalog, A*/Dijkstra, parser OSM) và PostgreSQL 76 ca GIS/B2B; mỗi lượt một cảnh báo TestClient có sẵn. PostgreSQL riêng đã dừng. Test metadata nhỏ là test hợp đồng, không phải thực địa.
- 2026-11-22: Đối chiếu độc lập archive OSM thật ở Windows, gsv1-83bb3fea…; CLI kiểm được manifest và graph; tuyến (106.6921,10.7767) → (106.70042,10.78077), A* khớp Dijkstra 4.088267 km. Snapshot quá tuổi sau 2026-12-05 21:23:02 UTC; không tắt kiểm tuổi.
- 2026-11-22: Sắp xếp lại lớp nền và trải nghiệm chọn/đọc tuyến, IN_PROGRESS → VERIFYING. Client: typecheck/build, 548 Vitest, 88 Node host và 21 test GIS tập trung đạt. Playwright GIS phát hiện 6 ca, trình duyệt cloud bị chặn socket trước khi chạy; chờ browser thật Windows và review độc lập.


- 2026-11-22: VERIFYING → REVIEWING. Kiểm thử trình duyệt thật Windows bằng đúng bản vá đã đóng băng trên baseline 644afa4. Phạm vi đã kiểm gồm desktop, mobile, API cùng nguồn và dữ liệu OSM công cộng.
- 2026-11-22: REVIEWING → DONE. Review độc lập xác nhận đạt AC-1–4, không còn vấn đề cản trở. Chỉ nghiệm thu trong bản chạy cô lập.

## Verification Evidence

- Backend: 97 ca GIS và 76 ca PostgreSQL GIS/B2B đạt. Mỗi lượt có một cảnh báo TestClient có sẵn. Client: 548 Vitest, 88 Node, typecheck và build đạt; 21 ca GIS tập trung.
- Windows Chromium thật, exact 644afa4 cùng bản vá đóng băng SHA-256 d3a7798439d67956f6e8bed0e344afddb7bcd527dc759015779165144f03d150: lớp OSM công cộng đúng snapshot hiển thị 2.346 đoạn làm nền. Nhập tọa độ, bấm hoặc chạm chọn điểm đều đạt và không gửi POST trước thao tác tìm. Không có request bản đồ bên ngoài; kiểm href Google Maps mà không điều hướng.
- Tuyến kiểm chứng TP.HCM trong [bằng chứng GIS M10](implement-warehouse-gis.md) và [plan](../superpowers/plans/2026-11-22-gis-route-usability.md): A* và Dijkstra độc lập cùng 4.088.267 mm; trình duyệt vẽ tuyến gồm 124 tọa độ. Ngoài vùng phủ, trả outside_coverage, không hiện polyline hoặc chiều dài đường. Lớp minh họa thưa không phải mạng đường đầy đủ; không có ETA/giao thông/xe tải.
- Không sửa B2B, thuật toán A*, hợp đồng định tuyến, DB chính hay runtime chính. Không mở Google Maps với dữ liệu người dùng, không phát hành lớp nền mới ra ngoài.

## Review Result

- Result: APPROVED cho bản sao cô lập; không có finding cản trở.

## Completion Evidence

- AC-1–4 đạt; bản vá nghiệm thu chỉ thêm bằng chứng vào task ledger so với bản sản phẩm đã kiểm thử.
- Không commit/push/merge hoặc triển khai trong lượt này.
