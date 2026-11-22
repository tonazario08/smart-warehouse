# capture-b2b-delivery-location — Ghi địa chỉ và điểm giao B2B đã xác nhận

- Status: DONE
- Phase: B2B / GIS vị trí giao
- Plan: docs/superpowers/plans/2026-11-22-b2b-delivery-location.md (đã duyệt cho demo cô lập)
- Depends on: docs/tasks/add-gis-landmark-picker.md, docs/tasks/implement-b2b-purchase-requests.md
- Created: 2026-11-22
- Started: 2026-11-22
- Completed: 2026-11-22

## Goal
Khách nhập địa chỉ và xác nhận ghim giao hàng trên đơn mới qua địa danh mẫu nội bộ, GPS chỉ khi bấm và cho quyền hoặc nhập thủ công. Nhân viên xem tuyến riêng từ kho đã chọn tới điểm giao ghi trên đơn.

## Context
Tìm kho B2B dùng Haversine và tồn. Tọa độ trước đây chỉ tạm trong form. Tra đơn trong GIS hiện có nghĩa điểm đến là kho được gắn vào đơn, không phải nhà khách. Đồ thị không có geocoder địa chỉ; demo dùng danh sách địa danh công cộng đã xác minh, không hứa nhận mọi địa chỉ.

## In Scope
- Form địa chỉ chữ do khách nhập, xác nhận vị trí bản đồ rõ ràng; local demo chỉ tìm vài tên nơi công cộng; GPS một lần khi bấm, báo độ chính xác/lỗi và cho fallback. Khi đổi địa chỉ/ghim phải xác nhận lại.
- Snapshot bất biến trong giao dịch tạo đơn; ba trường nullable đồng bộ cho đơn/API cũ, không backfill hoặc bịa vị trí. Hash idempotency cũ giữ nguyên khi thiếu snapshot; thay address/point với cùng key trả 409.
- Đọc snapshot ở endpoint chi tiết riêng người sở hữu đơn hoặc quyền nhân viên đang có; không có gán nhân viên vào kho trong RBAC baseline. Không thêm địa chỉ/điểm vào danh sách, URL, log hay bộ nhớ lưu lâu trình duyệt.
- Nhánh staff “Địa chỉ giao của đơn B2B” riêng: đọc đơn đã cấp quyền, đi từ đúng kho được gán tới tọa độ lưu; không đổi tra đơn→kho cũ. Không mở Google Maps cho điểm giao riêng tư. Tìm kho từ ghim mới dùng body POST nội bộ, cùng quy tắc Haversine như GET cũ; không có địa chỉ trong body tìm kho.

## Out of Scope
Không gọi geocoder ngoài, theo dõi vị trí, dịch vụ bản đồ/Google với địa chỉ riêng tư, thay B2B stock/workflow, backfill, sửa địa chỉ đơn đã gửi, mở quyền mới, triển khai/main/migrate thật/push.

## Acceptance Criteria
- [x] AC-1. Local address/GPS/manual + confirm; quyền từ chối và không có gợi ý không tự đoán. Không truyền địa chỉ/tọa độ ra ngoài, không put địa chỉ/ghim vào URL.
- [x] AC-2. Địa chỉ và điểm được validate, lưu chung với create; no snapshot với đơn cũ; same key replay ổn, changed address/coords hết hiệu lực; rollback không để lại snapshot.
- [x] AC-3. Owner/staff detail riêng no-store, client khác 404 giống đơn không tồn tại; không nằm trong list, by-key, action hoặc log. Chỉ payload của API nội bộ nơi cần thiết.
- [x] AC-4. Nhánh tra địa chỉ giao chọn chính xác kho được gán và điểm đã lưu, không tự đoán cho đơn cũ/không có tuyến; quyền staff, không thay mode cũ/đường A*, không xuất Google link điểm giao.
- [x] AC-5. Migration additive 0011→0012→0011 trên PostgreSQL dùng một lần, test backend, frontend và Windows browser cô lập; không dùng dữ liệu thật của khách.

## Verification Commands
- python -m pytest -q tests/postgres/test_purchase_requests_api.py tests/test_gis_api.py tests/postgres/test_gis_api.py tests/postgres/test_purchase_request_migration.py
- Client npm run typecheck; npm run build; npm run test:all. Browser Windows với dữ liệu giả lập, GPS mô phỏng, không truyền dữ liệu ngoài.
- Ruff và git diff --check.

## Progress Log
- 2026-11-22: Người dùng duyệt đúng đường dẫn task/plan cho bản demo riêng. DRAFT → READY → IN_PROGRESS; dependency DONE. Baseline 644afa4a71bcdc20616028c9023049c58cb48340 + cumulative landmark final SHA256 54abb775f7098198cbca2f270ad48c8e555216a9fdb913c38e5221fe0929cee0; head 0011.
- 2026-11-22: RED trả 422 vì chưa nhận snapshot. Sau implementation, 196 backend được kiểm trên PostgreSQL riêng và suites GIS/model, một cảnh báo TestClient có sẵn. Trước migration tạo một đơn workflow tại 0011 bằng cách băm cũ; ở 0012 GET/approve/fulfill và replay giữ đúng ID và fingerprint gốc. POST lookup thân JSON khớp GET lịch sử nhưng không dùng URL, client khác 404; đường riêng chọn đúng kho và tọa độ, mode cũ còn nguyên. Downgrade từ chối khi đã có snapshot để tránh hỏng fingerprint, và thành công trong DB thử khi không còn snapshot; DB thử đã dừng.
- 2026-11-22: Review độc lập địa chỉ công cộng mẫu theo nguồn chính thức của Dinh, Vietnam Tourism/VNPost và HBSO; tọa độ là điểm đại diện OSM, không phải lối giao. GPS thật không được gọi khi load, chỉ nút bấm; browser test dùng vị trí mô phỏng.
- 2026-11-22: IN_PROGRESS → VERIFYING; đóng băng sản phẩm để kiểm thử Windows cô lập. Backend targeted 196 ca đạt; client đầy đủ đang chạy. Không dùng mẫu tổng hợp để suy luận geocoding địa chỉ thật.


- 2026-11-22: VERIFYING → REVIEWING. Tổng hợp lượt backend/frontend và Chromium Windows thật trên nguồn đã đóng băng.
- 2026-11-22: REVIEWING → DONE. Review độc lập xác nhận đủ AC-1–5 trong demo cô lập; không có vấn đề cản trở. Không thay sản phẩm sau freeze.

## Verification Evidence

- Backend: 196 ca đạt trên PostgreSQL riêng và suites GIS/model, một cảnh báo TestClient có sẵn. Cơ sở dữ liệu thử đã dừng. Migration 0011→0012 không backfill; đơn managed cũ giữ fingerprint, detail/approve/fulfill/replay. Downgrade đã thử khi không có snapshot, bị từ chối khi có dữ liệu mới để tránh mất dữ liệu/khóa idempotency.
- Client: 567 Vitest, 88 Node host, typecheck/build/diff check đạt. Playwright phát hiện 6 ca purchase; việc liệt kê không đại diện cho việc chạy cả bộ.
- Chromium desktop/mobile thật + PostgreSQL 18 cô lập Windows, SHA256 đóng băng 3c11e11335b0cc2725e77518a25d8c4bf9e79d403f30bc27195658bc0a79178f. Đơn managed trước migration giữ trạng thái và replay; khách lưu địa chỉ/điểm đã xác nhận trên đơn thử #2. Cùng key đổi địa chỉ hoặc tọa độ đều 409; khách khác không đọc được, chi tiết no-store. Staff route từ kho thực sự được gán tới đúng ghim đã lưu, 368,805 m trên OSM đã xác minh; không có Google link ở chế độ riêng tư. GPS mobile mô phỏng, từ chối quyền và phản hồi GPS đến muộn đã kiểm; không request ngoài. Không dùng địa chỉ hay vị trí thật của khách.

## Review Result

- Result: APPROVED cho bản sao cô lập; không có finding cản trở.

## Completion Evidence

- AC-1–5 đạt. Bản vá cuối chỉ thay task ledger so với bản sản phẩm đã thử. Tra địa chỉ chỉ phủ mẫu công cộng nội bộ, không phải geocoding mọi địa chỉ. Không tuyên bố kiểm GPS phần cứng hoặc lối giao thật.
- Không commit, merge, push/migrate/triển khai hệ thống chính.
