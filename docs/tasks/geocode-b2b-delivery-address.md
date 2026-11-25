# geocode-b2b-delivery-address — Tìm địa chỉ giao và xác nhận ghim

- Status: DONE
- Phase: B2B / Địa chỉ giao
- Plan: docs/superpowers/plans/2026-11-22-b2b-delivery-geocode.md
- Depends on: docs/tasks/capture-b2b-delivery-location.md
- Created: 2026-11-22
- Started: 2026-11-22
- Completed: 2026-11-22

## Goal
Tìm địa chỉ khách gõ từ OSM vùng TP.HCM thực sự, xem trước ghim, nhận biết xấp xỉ/không khớp và xác nhận hoặc dùng vị trí hiện tại.

## Context
Ba địa danh mẫu và GPS không đủ để tìm nhà khách. Snapshot đường hiện hữu không chứa tên hoặc số nhà.

## In Scope
Tra chỉ mục OSM định danh khu vực ở backend nội bộ, kèm nguồn; bản đồ OSM cùng origin, ghim chọn/đổi được; GPS tự nguyện và nhập thủ công. Không đổi luồng lưu địa chỉ/điểm đã xác nhận.

## Out of Scope
Địa chỉ toàn quốc, gửi truy vấn ra ngoài, theo dõi GPS, thay state đơn cũ/OSM A*/tồn/phân quyền staff, main/merge/deploy/push.

## Acceptance Criteria
- [x] AC-1. Mẫu công khai từ dữ liệu OSM thật minh chứng nhà/đường xấp xỉ, nhiều/không khớp và không bảo đảm mọi địa chỉ.
- [x] AC-2. Chỉ quyền tạo B2B; request POST không có query riêng tư; no-store và không echo lỗi; lớp công cộng không mở API staff.
- [x] AC-3. Khách xem/chọn ứng viên, sửa ghim hoặc GPS thủ công; khóa kết quả muộn; chỉ lưu sau xác nhận.
- [x] AC-4. Test API, frontend, browser thật cô lập; không truy cập ngoài hoặc thay A*/xử lý kho/0012.

## Verification Commands
- `python -m pytest -q tests/test_b2b_delivery_geocode.py tests/test_gis_api.py`; kiểm hồi quy B2B cô lập.
- Client `npm run typecheck`, `npm run build`, `npm run test:all`; browser cô lập với địa chỉ công khai.

## Progress Log
- 2026-11-22: READY → IN_PROGRESS; Toàn duyệt đúng task và scope. Baseline 644afa4 + patch delivery cuối SHA 3b7dd3ac6a3a49101cc6300463c18484eca8d67a3cd395b521b28b9cc2c883ec, dependency DONE, không mở main.

- 2026-11-22: IN_PROGRESS → VERIFYING; đóng băng candidate phục vụ kiểm thử thật trên demo riêng.
- 2026-11-22: VERIFYING → IN_PROGRESS; kiểm chứng holdout độc lập thấy các điểm đường đại diện cách địa chỉ công cộng hơn 1 km; bổ sung xác nhận riêng rằng ghim chỉ là điểm tham chiếu hoặc hiệu chỉnh ghim. Không thay phạm vi.
- 2026-11-22: IN_PROGRESS → VERIFYING; chốt candidate sửa xác nhận điểm đường, không thay chức năng backend.
- 2026-11-22: VERIFYING → REVIEWING; đạt kiểm thử API, frontend và browser Windows độc lập với đúng candidate và chỉ mục OSM thật.
- 2026-11-22: REVIEWING → DONE; kiểm tra lại chứng cứ AC-1…AC-4, không phát hiện lỗi chặn trong phạm vi demo cô lập.

## Verification Evidence
- RED: bài test tra địa chỉ không thể import service trước khi tạo. GREEN: gói pytest geocode/importer/GIS/architecture/schema/models/nearest 212 pass, 1 cảnh báo Starlette có sẵn. Trên predecessor chính xác, riêng assertion Python dump cũ fail vì chưa cập nhật optional `delivery_location=None` từ 0012; sửa kỳ vọng test và xác nhận input JSON omit vẫn nguyên, không đổi production schema/idempotency.
- BBBike Saigon XML gzip công khai xác minh checksum, SHA-256 `887697a4910ec563ded90d4fae40764d27acd559c5b6b68ef5bc4f7a11a1dffd`; chỉ mục đóng băng `601e2237a0e4a6cc820257f6a3c4d15e5cc0096a80aad99e240447783d29b3aa`. 53.693 mục, 21.916 số nhà, 2.479 số có dấu /. Biên [106.5444, 10.6564, 106.8545, 10.8931]. Không phải toàn TP.HCM.
- Holdout công khai cố định: 1/7 địa chỉ khớp tag số nhà (69 Lý Tự Trọng; thêm phường thiếu tag không khớp), 0/2 hẻm khớp số. Các mẫu còn lại chỉ điểm đường; ví dụ cách địa chỉ công cộng ~644–1.111 m, không suy ra độ chính xác chung. Chuỗi giả/địa chỉ Hà Nội không trả ghim. Endpoint thật với index đã ghim SHA trả 69 Lý Tự Trọng một ứng viên số nhà, 65 hai điểm đường, 106 Nguyễn Thị Minh Khai hai ứng viên số nhà, ngoài vùng không khớp. Tất cả no-store.
- Frontend bản chốt: typecheck/build PASS; 574 Vitest + 88 host PASS (44 ca form B2B); scoped diff whitespace sạch.
- Browser desktop/mobile Windows + PostgreSQL cô lập: bản cumulative `379ddde0c51760517cdda775445dd9788430a03a0917ada733752ee48aef81c8`, incremental `672b9d3b169acdd6778d5b2fc84a5fe9741383d7e493d8ca1ced7cb987b79cbe`, index `601e2237…`. 69 Lý Tự Trọng xem trước/lưu/đọc lại đúng địa chỉ và tọa độ; 65 có hai điểm đường, chặn xác nhận nếu chưa sửa hoặc chưa đánh dấu thừa nhận; không khớp không cấp ghim; chạm lớp OSM công cộng và GPS từ chối mô phỏng vẫn có đường dự phòng. Không gửi request ra ngoài. Nhân viên dùng đúng tọa độ đã lưu: điểm 69 trả no_route một cách minh bạch, ca có tuyến trước đây vẫn chạy. Không thay A*, tồn, migration 0012 hoặc luồng đơn cũ.

## Review Result
- Result: APPROVED
- Findings: none
- Phạm vi: PASS cho phạm vi cô lập; không phải nghiệm thu địa chỉ toàn TP.HCM hoặc phê duyệt production. Kết quả giới hạn OSM là lý do phải có bước xác nhận, không phải bằng chứng vị trí cổng.

## Completion Evidence
- Đạt AC-1…AC-4 với data công khai đã xác minh, app demo cô lập và không dùng địa chỉ khách thật. Bản vá cuối chỉ thay ledger so với mã đã kiểm, không merge/push/kích hoạt main, không thay demo cũ.
- Chỉ 1/7 địa chỉ kiểm thử công khai khớp tag số nhà, 0/2 hẻm; không suy rộng tỷ lệ cho toàn thành phố. Kết quả đường có thể cách nơi giao hơn 1 km, ranh giới index/bản đồ khác nhau, ghim không bảo đảm có tuyến. GPS tùy thiết bị/quyền, còn cách chạm ghim hoặc dán tọa độ.

### Handoff vận hành cô lập (không tự bật)
- Tải bằng tay dữ liệu bản đồ công cộng [BBBike Saigon](https://download.bbbike.org/osm/bbbike/Saigon/), giữ chứng từ checksum do nhà cung cấp công bố. Không gửi địa chỉ khách cho BBBike/OSM. © OpenStreetMap contributors, [ODbL 1.0](https://www.openstreetmap.org/copyright). Chỉ mục dẫn xuất không đưa vào Git; khi phân phối, giữ nguồn, checksum/biên, cách tái tạo và ghi công.
- `python tools/build_b2b_address_index.py /path/Saigon.osm.gz /outside-repo/address-index.json --source-format bbbike-osm`. Ghim SHA-256 của **chỉ mục tạo ra**, không phải file gzip, ở `B2B_ADDRESS_INDEX_SHA256` và đường dẫn ở `B2B_ADDRESS_INDEX_PATH`, sau đó khởi động lại API cô lập. Thiếu/sai digest → unavailable. Giá trị gốc ở index là tham chiếu nguồn, không tự xác minh danh tính nhà xuất bản.
- GET lớp đường tái sử dụng snapshot public OSM đã xác minh từ cấu hình GIS; nếu thiếu/bị cũ/là fixture, không giả đường và vẫn dùng GPS/nhập tọa độ. Biên chỉ mục Saigon và snapshot GIS không nhất thiết trùng nhau; ghim địa chỉ ngoài biên lớp hiện tại vẫn có số tọa độ, không hứa tuyến A*.
- Kết quả số nhà là điểm gắn tag số nhà/đường OSM, không đảm bảo cổng giao; thiếu số thì chỉ hiện điểm đường đại diện (xấp xỉ), không nội suy số nhà. Tên và số hẻm thiếu tag, nhiều ứng viên hoặc địa bàn không khớp phải dùng xác nhận tay. Không xuất bản/merge/kích hoạt môi trường khác.
