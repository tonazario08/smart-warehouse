# use-leaflet-for-b2b-delivery-map — Bản đồ nền OSM Leaflet cho khách B2B

- Status: DONE
- Phase: B2B / bản đồ điểm giao
- Plan: docs/superpowers/plans/2026-11-22-b2b-delivery-leaflet.md
- Depends on: docs/tasks/geocode-b2b-delivery-address.md
- Created: 2026-11-22
- Started: 2026-11-22
- Completed: 2026-11-22

## Goal
Khách có bản đồ giao hàng quen thuộc với tên đường, địa danh thật và thao tác kéo/phóng/chạm rõ ràng, không tiết lộ vị trí ra ngoài.

## Context
Bản trước chỉ hiển thị đường thưa từ snapshot định tuyến; BBBike Saigon OSM đã xác minh có nhãn thật nhưng không đảm bảo phủ mọi địa chỉ.

## In Scope
Leaflet trên màn chọn điểm giao khách, bản nền vector OSM cùng origin ghim digest, đặt/đổi ghim rõ ràng, attribution, GPS/thủ công, giữ xác nhận lưu.

## Out of Scope
Tiles/tra cứu ngoài, lấy cache tile công cộng, A*/tìm kho/ETA/luồng hàng, geocoder/storage/0012, phân quyền staff, main/GitHub/DB/deploy.

## Acceptance Criteria
- [x] AC-1 Nền Leaflet ghi công OSM, đường/địa danh có tên thật từ artifact đã tái tạo và xác minh; không dùng dataset giả hoặc tile ngoài.
- [x] AC-2 Khách pan/zoom không tự đặt ghim, đặt bằng click/tap/kéo ghim hoặc nhập/GPS; xác nhận/acknowledgment, gõ địa chỉ, tìm kho, lưu đơn vẫn đúng.
- [x] AC-3 Dữ liệu không hợp lệ/thiếu/outside hiển thị rõ, không đồ họa giả hoặc tự gọi provider. Không tọa độ/query/cache bên ngoài, staff GIS giữ nguyên.
- [x] AC-4 Test compiler/index/RBAC, quy trình trước/tiếp theo và browser desktop/mobile cô lập trên artifact thật; không thay mã/DB ngoài scope.

## Verification Commands
- `python -m pytest -q tests/test_b2b_leaflet_map.py tests/test_b2b_leaflet_import.py tests/test_b2b_delivery_geocode.py tests/test_gis_api.py`
- Client `npm run typecheck`, `npm run build`, `npm run test:all`; exact browser cô lập trên Windows.

## Progress Log
- 2026-11-22: READY → IN_PROGRESS, Toàn duyệt task/plan; predecessor DONE; baseline 644afa4 + cumulative geocode final SHA 39d3a95cfa663ecbc5acb142ef9a0cc297e22de706b2316897a2ddcfd2504cd0.

- 2026-11-22: IN_PROGRESS → VERIFYING; đóng băng candidate với bản nền BBBike Saigon đã tái tạo khớp byte, mới chạy browser Windows độc lập.

- 2026-11-22: VERIFYING → REVIEWING; API, frontend và browser Windows độc lập trên candidate đã đóng băng đạt.
- 2026-11-22: REVIEWING → DONE; kiểm lại phạm vi và chứng cứ AC-1…AC-4, không có lỗi chặn demo cô lập.

## Verification Evidence
- Bản nền SHA-256 `40131bfcd20ccf1cc43970f05102a2dce9548300a7ccb17176d1c403597032c2`, 3.252.994 byte. 8.000 đường (1.489 tên khác nhau), 400 địa danh, 500 vùng công viên/nước; API client no-store xác minh đúng Lý Tự Trọng và Dinh Độc Lập. Rebuild khớp byte.

- Backend compiler/API/RBAC + hồi quy GIS/B2B/kiến trúc: 217 pass, 1 cảnh báo Starlette đã có. Artifact rebuild khớp byte, admission kiểm SHA/giới hạn; artifact thiếu hoặc không hợp lệ không giả nền. Ruff và scoped diff check đạt.
- Frontend exact: typecheck/build đạt, 575 Vitest và 88 host test pass (45 ca form B2B).
- Windows desktop/mobile độc lập dùng bản cumulative freeze `23317acbcdb0f5d854b64c3bcf0ce0e38bce9e014cfaf7a87e0e0f230c33f7f3`, backdrop thật `40131bfc…`: tên Nam Kỳ Khởi Nghĩa trên Canvas; pan/zoom giữ xác nhận; kéo ghim/click/phím đổi tọa độ và thu hồi xác nhận; mobile chạm ghim khi GPS bị từ chối mô phỏng. Không request ra ngoài. Đơn cô lập #2 lưu/đọc điểm Dinh Độc Lập; GIS / A* đã có trả 368,805 m.

## Review Result
- Result: APPROVED
- Findings: none
- Phạm vi: PASS cho demo nội bộ; không xác lập độ phủ địa chỉ, bộ tuyến hoặc sẵn sàng production.

## Completion Evidence
- Đạt AC-1…AC-4 trên nền vector có nhãn được tái tạo từ dữ liệu công khai; sử dụng khung phụ thuộc phạm vi bản đồ. Không phủ mọi đường, không đối chiếu cổng giao, không ETA.
- Từ freeze đã kiểm đến bản cuối chỉ đổi ledger này. Không triển khai xa, sửa main/DB/runtime, chép dữ liệu khách, merge hoặc push.

### Handoff dùng trong demo cô lập
- Nguồn bản đồ: [BBBike Saigon XML](https://download.bbbike.org/osm/bbbike/Saigon/), bản raw đã xác minh SHA-256 `887697a4910ec563ded90d4fae40764d27acd559c5b6b68ef5bc4f7a11a1dffd`. Lưu checksum do nguồn công bố. Không upload điểm khách/dữ liệu dự án lên BBBike.
- `python tools/build_b2b_leaflet_map.py /path/Saigon.osm.gz /outside-repo/leaflet-map.json --source-sha256 887697a4910ec563ded90d4fae40764d27acd559c5b6b68ef5bc4f7a11a1dffd`; đặt `B2B_DELIVERY_MAP_PATH` và `B2B_DELIVERY_MAP_SHA256` của file JSON sinh ra. Không trộn với chỉ mục địa chỉ. Artifact dẫn xuất nằm ngoài Git, dữ liệu © OpenStreetMap contributors/[ODbL](https://www.openstreetmap.org/copyright); giữ provenance và compiler nếu chia sẻ.
- Không dùng tile bên ngoài. Đây là tập con vector và nhãn OSM, không phải phủ mọi đường/ảnh vệ tinh/địa chỉ hay dữ liệu dẫn đường. Không ảnh hưởng catalog riêng A*. Thiếu artifact, digest lệch hoặc điểm ngoài biên có thông báo; dùng GPS/nhập tọa độ nếu cần.
